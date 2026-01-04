//! PostgreSQL state manager

use crate::config::DatabaseConfig;
use crate::coordination::dependency::PendingTransaction;
use crate::error::{RelayerError, RelayerResult};
use crate::events::ContractEvent;

use chrono::{DateTime, Utc};
use sqlx::postgres::{PgPool, PgPoolOptions};
use sqlx::Row;
use tracing::{debug, info};

/// State manager for PostgreSQL persistence
pub struct StateManager {
    pool: PgPool,
}

impl StateManager {
    /// Create a new state manager
    pub async fn new(config: &DatabaseConfig) -> RelayerResult<Self> {
        let pool = PgPoolOptions::new()
            .max_connections(config.max_connections)
            .min_connections(config.min_connections)
            .connect(&config.url)
            .await
            .map_err(|e| RelayerError::Database(e))?;

        Ok(Self { pool })
    }

    /// Run database migrations
    pub async fn run_migrations(&self) -> RelayerResult<()> {
        // In production, use sqlx::migrate!
        // For now, create tables inline

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS chain_checkpoints (
                chain_id BIGINT PRIMARY KEY,
                block_number BIGINT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS pending_transactions (
                tx_id BYTEA PRIMARY KEY,
                origin_chain BIGINT NOT NULL,
                target_chain BIGINT NOT NULL,
                dependency_id BYTEA,
                swap_group_id BYTEA,
                state VARCHAR(20) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS contract_events (
                id BIGSERIAL PRIMARY KEY,
                chain_id BIGINT NOT NULL,
                block_number BIGINT NOT NULL,
                tx_hash VARCHAR(66) NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                event_data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE INDEX IF NOT EXISTS idx_events_chain_block
            ON contract_events (chain_id, block_number)
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS tx_submissions (
                id BIGSERIAL PRIMARY KEY,
                tx_id BYTEA NOT NULL,
                chain_id BIGINT NOT NULL,
                ethereum_tx_hash VARCHAR(66) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                confirmed_at TIMESTAMPTZ
            )
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE INDEX IF NOT EXISTS idx_submissions_tx_id
            ON tx_submissions (tx_id)
            "#,
        )
        .execute(&self.pool)
        .await?;

        info!("Database migrations complete");
        Ok(())
    }

    /// Health check
    pub async fn health_check(&self) -> RelayerResult<()> {
        sqlx::query("SELECT 1")
            .execute(&self.pool)
            .await
            .map_err(|e| RelayerError::Database(e))?;
        Ok(())
    }

    /// Get block checkpoint for a chain
    pub async fn get_checkpoint(&self, chain_id: u64) -> RelayerResult<u64> {
        let row = sqlx::query(
            "SELECT block_number FROM chain_checkpoints WHERE chain_id = $1",
        )
        .bind(chain_id as i64)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.map(|r| r.get::<i64, _>("block_number") as u64).unwrap_or(0))
    }

    /// Save block checkpoint for a chain
    pub async fn save_checkpoint(&self, chain_id: u64, block_number: u64) -> RelayerResult<()> {
        sqlx::query(
            r#"
            INSERT INTO chain_checkpoints (chain_id, block_number, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (chain_id)
            DO UPDATE SET block_number = $2, updated_at = NOW()
            "#,
        )
        .bind(chain_id as i64)
        .bind(block_number as i64)
        .execute(&self.pool)
        .await?;

        debug!("Saved checkpoint for chain {}: block {}", chain_id, block_number);
        Ok(())
    }

    /// Store a contract event
    pub async fn store_event(&self, event: &ContractEvent) -> RelayerResult<()> {
        let event_data = serde_json::to_value(event)
            .map_err(|e| RelayerError::Internal(e.to_string()))?;

        let (chain_id, block_number, tx_hash) = match event {
            ContractEvent::TransactionBuffered {
                chain_id,
                block_number,
                tx_hash,
                ..
            } => (*chain_id, *block_number, format!("{:?}", tx_hash)),
            ContractEvent::TransactionReady {
                chain_id,
                block_number,
                tx_hash,
                ..
            } => (*chain_id, *block_number, format!("{:?}", tx_hash)),
            _ => {
                // Extract common fields
                let chain_id = event.chain_id();
                (chain_id, 0, String::new())
            }
        };

        sqlx::query(
            r#"
            INSERT INTO contract_events (chain_id, block_number, tx_hash, event_type, event_data)
            VALUES ($1, $2, $3, $4, $5)
            "#,
        )
        .bind(chain_id as i64)
        .bind(block_number as i64)
        .bind(&tx_hash)
        .bind(event.name())
        .bind(event_data)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Store a pending transaction
    pub async fn store_pending_transaction(&self, tx: &PendingTransaction) -> RelayerResult<()> {
        let state_str = match tx.state {
            crate::coordination::dependency::TransactionState::Buffered => "buffered",
            crate::coordination::dependency::TransactionState::DependencyPending => "dependency_pending",
            crate::coordination::dependency::TransactionState::Ready => "ready",
            crate::coordination::dependency::TransactionState::Submitted => "submitted",
            crate::coordination::dependency::TransactionState::Finalized => "finalized",
            crate::coordination::dependency::TransactionState::Failed => "failed",
            crate::coordination::dependency::TransactionState::Expired => "expired",
        };

        sqlx::query(
            r#"
            INSERT INTO pending_transactions
                (tx_id, origin_chain, target_chain, dependency_id, swap_group_id, state)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (tx_id)
            DO UPDATE SET state = $6, updated_at = NOW()
            "#,
        )
        .bind(&tx.tx_id[..])
        .bind(tx.origin_chain as i64)
        .bind(tx.target_chain as i64)
        .bind(tx.dependency_id.map(|d| d.to_vec()))
        .bind(tx.swap_group_id.map(|g| g.to_vec()))
        .bind(state_str)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Get pending transactions
    pub async fn get_pending_transactions(&self) -> RelayerResult<Vec<PendingTransaction>> {
        let rows = sqlx::query(
            r#"
            SELECT tx_id, origin_chain, target_chain, dependency_id, swap_group_id, state,
                   EXTRACT(EPOCH FROM created_at)::BIGINT as created_at
            FROM pending_transactions
            WHERE state NOT IN ('finalized', 'failed', 'expired')
            "#,
        )
        .fetch_all(&self.pool)
        .await?;

        let transactions = rows
            .into_iter()
            .map(|row| {
                let tx_id_bytes: Vec<u8> = row.get("tx_id");
                let mut tx_id = [0u8; 32];
                tx_id.copy_from_slice(&tx_id_bytes[..32]);

                let dependency_id: Option<Vec<u8>> = row.get("dependency_id");
                let dependency_id = dependency_id.map(|d| {
                    let mut arr = [0u8; 32];
                    arr.copy_from_slice(&d[..32]);
                    arr
                });

                let swap_group_id: Option<Vec<u8>> = row.get("swap_group_id");
                let swap_group_id = swap_group_id.map(|g| {
                    let mut arr = [0u8; 32];
                    arr.copy_from_slice(&g[..32]);
                    arr
                });

                let state_str: String = row.get("state");
                let state = match state_str.as_str() {
                    "buffered" => crate::coordination::dependency::TransactionState::Buffered,
                    "dependency_pending" => {
                        crate::coordination::dependency::TransactionState::DependencyPending
                    }
                    "ready" => crate::coordination::dependency::TransactionState::Ready,
                    "submitted" => crate::coordination::dependency::TransactionState::Submitted,
                    _ => crate::coordination::dependency::TransactionState::Buffered,
                };

                PendingTransaction {
                    tx_id,
                    origin_chain: row.get::<i64, _>("origin_chain") as u64,
                    target_chain: row.get::<i64, _>("target_chain") as u64,
                    dependency_id,
                    swap_group_id,
                    state,
                    created_at: row.get::<i64, _>("created_at") as u64,
                }
            })
            .collect();

        Ok(transactions)
    }

    /// Record a transaction submission
    pub async fn record_submission(
        &self,
        tx_id: &[u8; 32],
        chain_id: u64,
        ethereum_tx_hash: &str,
    ) -> RelayerResult<()> {
        sqlx::query(
            r#"
            INSERT INTO tx_submissions (tx_id, chain_id, ethereum_tx_hash, status)
            VALUES ($1, $2, $3, 'pending')
            "#,
        )
        .bind(&tx_id[..])
        .bind(chain_id as i64)
        .bind(ethereum_tx_hash)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Update submission status
    pub async fn update_submission_status(
        &self,
        ethereum_tx_hash: &str,
        status: &str,
    ) -> RelayerResult<()> {
        let confirmed_at = if status == "confirmed" {
            Some(Utc::now())
        } else {
            None
        };

        sqlx::query(
            r#"
            UPDATE tx_submissions
            SET status = $1, confirmed_at = $2
            WHERE ethereum_tx_hash = $3
            "#,
        )
        .bind(status)
        .bind(confirmed_at)
        .bind(ethereum_tx_hash)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Get transaction statistics
    pub async fn get_stats(&self) -> RelayerResult<TransactionStats> {
        let row = sqlx::query(
            r#"
            SELECT
                COUNT(*) FILTER (WHERE state = 'buffered') as buffered,
                COUNT(*) FILTER (WHERE state = 'ready') as ready,
                COUNT(*) FILTER (WHERE state = 'submitted') as submitted,
                COUNT(*) FILTER (WHERE state = 'finalized') as finalized,
                COUNT(*) FILTER (WHERE state = 'failed') as failed
            FROM pending_transactions
            "#,
        )
        .fetch_one(&self.pool)
        .await?;

        Ok(TransactionStats {
            buffered: row.get::<i64, _>("buffered") as u64,
            ready: row.get::<i64, _>("ready") as u64,
            submitted: row.get::<i64, _>("submitted") as u64,
            finalized: row.get::<i64, _>("finalized") as u64,
            failed: row.get::<i64, _>("failed") as u64,
        })
    }
}

/// Transaction statistics
#[derive(Debug, Clone)]
pub struct TransactionStats {
    pub buffered: u64,
    pub ready: u64,
    pub submitted: u64,
    pub finalized: u64,
    pub failed: u64,
}
