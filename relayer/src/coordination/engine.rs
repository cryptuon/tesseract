//! Main coordination engine for cross-chain transaction orchestration

use super::dependency::{DependencyGraph, PendingTransaction, TransactionState};
use crate::chain::ChainManager;
use crate::config::RelayerConfig;
use crate::error::{RelayerError, RelayerResult};
use crate::events::ContractEvent;
use crate::state::StateManager;
use crate::tx::TransactionSender;

use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{interval, Duration};
use tracing::{debug, error, info, warn};

/// Cross-chain coordination engine
pub struct CoordinationEngine {
    /// Chain manager for multi-chain access
    chain_manager: Arc<ChainManager>,
    /// State manager for persistence
    state_manager: Arc<StateManager>,
    /// Dependency graph
    dependency_graph: Arc<DependencyGraph>,
    /// Transaction sender
    tx_sender: Arc<TransactionSender>,
    /// Configuration
    config: RelayerConfig,
    /// Shutdown flag
    shutdown: Arc<RwLock<bool>>,
}

impl CoordinationEngine {
    /// Create a new coordination engine
    pub async fn new(
        chain_manager: Arc<ChainManager>,
        state_manager: Arc<StateManager>,
        config: RelayerConfig,
    ) -> RelayerResult<Self> {
        let dependency_graph = Arc::new(DependencyGraph::new());
        let tx_sender = Arc::new(TransactionSender::new(
            chain_manager.clone(),
            state_manager.clone(),
            config.clone(),
        ).await?);

        // Load pending transactions from database
        let pending = state_manager.get_pending_transactions().await?;
        for tx in pending {
            dependency_graph.add_transaction(tx).await;
        }

        Ok(Self {
            chain_manager,
            state_manager,
            dependency_graph,
            tx_sender,
            config,
            shutdown: Arc::new(RwLock::new(false)),
        })
    }

    /// Main coordination loop
    pub async fn run(&self) -> RelayerResult<()> {
        // Subscribe to events from all chains
        let mut event_rx = self.chain_manager.subscribe_events();

        // Processing interval
        let mut process_interval = interval(Duration::from_millis(self.config.poll_interval_ms));

        // Cleanup interval
        let mut cleanup_interval = interval(Duration::from_secs(300)); // 5 minutes

        info!("Coordination engine started");

        loop {
            if *self.shutdown.read().await {
                break;
            }

            tokio::select! {
                // Process incoming events
                Ok(event) = event_rx.recv() => {
                    if let Err(e) = self.handle_event(event).await {
                        error!("Error handling event: {}", e);
                    }
                }

                // Periodic processing of pending transactions
                _ = process_interval.tick() => {
                    if let Err(e) = self.process_pending().await {
                        error!("Error processing pending transactions: {}", e);
                    }
                }

                // Periodic cleanup
                _ = cleanup_interval.tick() => {
                    self.cleanup().await;
                }
            }
        }

        info!("Coordination engine stopped");
        Ok(())
    }

    /// Handle an incoming contract event
    async fn handle_event(&self, event: ContractEvent) -> RelayerResult<()> {
        debug!("Handling event: {:?}", event.name());

        match event {
            ContractEvent::TransactionBuffered {
                chain_id,
                tx_id,
                origin_rollup,
                target_rollup,
                timestamp,
                ..
            } => {
                self.handle_transaction_buffered(
                    chain_id,
                    tx_id,
                    origin_rollup,
                    target_rollup,
                    timestamp,
                )
                .await?;
            }

            ContractEvent::TransactionReady { chain_id, tx_id, .. } => {
                self.handle_transaction_ready(chain_id, tx_id).await?;
            }

            ContractEvent::DependencyResolved {
                chain_id,
                tx_id,
                dependency_id,
                ..
            } => {
                self.handle_dependency_resolved(chain_id, tx_id, dependency_id).await?;
            }

            ContractEvent::TransactionExecuted { tx_id, .. } => {
                self.dependency_graph.mark_finalized(&tx_id).await;
                info!("Transaction {:?} executed successfully", hex::encode(tx_id));
            }

            ContractEvent::TransactionFailed { tx_id, reason, .. } => {
                self.dependency_graph.mark_failed(&tx_id).await;
                warn!("Transaction {:?} failed: {}", hex::encode(tx_id), reason);
            }

            ContractEvent::SwapFillCreated {
                chain_id,
                order_id,
                fill_id,
                ..
            } => {
                self.handle_swap_fill(chain_id, order_id, fill_id).await?;
            }

            ContractEvent::ContractPaused { chain_id, .. } => {
                warn!("Contract paused on chain {}", chain_id);
                crate::metrics::record_contract_paused(chain_id);
            }

            ContractEvent::CircuitBreakerTriggered {
                chain_id,
                failure_count,
                ..
            } => {
                error!(
                    "Circuit breaker triggered on chain {} after {} failures",
                    chain_id, failure_count
                );
                crate::metrics::record_circuit_breaker(chain_id);
            }

            _ => {
                // Other events logged but not actioned
                debug!("Unhandled event type: {}", event.name());
            }
        }

        Ok(())
    }

    /// Handle new buffered transaction
    async fn handle_transaction_buffered(
        &self,
        origin_chain: u64,
        tx_id: [u8; 32],
        origin_rollup: ethers::types::Address,
        target_rollup: ethers::types::Address,
        timestamp: u64,
    ) -> RelayerResult<()> {
        info!(
            "New transaction buffered: {} on chain {}",
            hex::encode(tx_id),
            origin_chain
        );

        // Determine target chain from rollup address
        // In production, we'd have a mapping of rollup addresses to chain IDs
        let target_chain = self.resolve_target_chain(&target_rollup)?;

        let pending_tx = PendingTransaction {
            tx_id,
            origin_chain,
            target_chain,
            dependency_id: None, // Will be set when we query the contract
            swap_group_id: None,
            state: TransactionState::Buffered,
            created_at: timestamp,
        };

        self.dependency_graph.add_transaction(pending_tx.clone()).await;
        self.state_manager.store_pending_transaction(&pending_tx).await?;

        crate::metrics::record_transaction_buffered(origin_chain);
        Ok(())
    }

    /// Handle transaction marked ready
    async fn handle_transaction_ready(
        &self,
        chain_id: u64,
        tx_id: [u8; 32],
    ) -> RelayerResult<()> {
        info!(
            "Transaction ready: {} on chain {}",
            hex::encode(tx_id),
            chain_id
        );

        self.dependency_graph.mark_ready(&tx_id).await;
        Ok(())
    }

    /// Handle dependency resolution
    async fn handle_dependency_resolved(
        &self,
        _chain_id: u64,
        tx_id: [u8; 32],
        dependency_id: [u8; 32],
    ) -> RelayerResult<()> {
        info!(
            "Dependency resolved: {} -> {}",
            hex::encode(dependency_id),
            hex::encode(tx_id)
        );

        // The dependent transaction can now proceed
        self.dependency_graph.mark_ready(&tx_id).await;
        Ok(())
    }

    /// Handle swap fill - coordinate the cross-chain legs
    async fn handle_swap_fill(
        &self,
        chain_id: u64,
        order_id: [u8; 32],
        fill_id: [u8; 32],
    ) -> RelayerResult<()> {
        info!(
            "Swap fill created: order {} fill {} on chain {}",
            hex::encode(order_id),
            hex::encode(fill_id),
            chain_id
        );

        // In a full implementation, we would:
        // 1. Look up the swap order details
        // 2. Create corresponding transactions on target chains
        // 3. Coordinate atomic execution

        crate::metrics::record_swap_fill(chain_id);
        Ok(())
    }

    /// Process pending transactions
    async fn process_pending(&self) -> RelayerResult<()> {
        // Get all ready transactions
        for chain_id in self.chain_manager.connected_chains() {
            let ready_txs = self.dependency_graph.get_ready_for_chain(chain_id).await;

            for tx in ready_txs {
                // Check if transaction is part of a swap group
                if let Some(group_id) = tx.swap_group_id {
                    // Wait for all swap group members to be ready
                    if !self.dependency_graph.is_swap_group_ready(&group_id).await {
                        continue;
                    }
                }

                // Submit the transaction
                match self.tx_sender.submit_resolve(&tx).await {
                    Ok(tx_hash) => {
                        self.dependency_graph.mark_submitted(&tx.tx_id).await;
                        info!(
                            "Submitted resolve for {} on chain {}: {:?}",
                            hex::encode(tx.tx_id),
                            chain_id,
                            tx_hash
                        );
                    }
                    Err(e) => {
                        if e.is_retryable() {
                            warn!("Retryable error submitting tx: {}", e);
                        } else {
                            error!("Failed to submit tx: {}", e);
                            self.dependency_graph.mark_failed(&tx.tx_id).await;
                        }
                    }
                }
            }
        }

        Ok(())
    }

    /// Resolve target chain from rollup address
    fn resolve_target_chain(&self, _rollup: &ethers::types::Address) -> RelayerResult<u64> {
        // In production, maintain a mapping of rollup addresses to chain IDs
        // For now, return a default
        Ok(1) // Ethereum mainnet
    }

    /// Cleanup old data
    async fn cleanup(&self) {
        // Clean up old transactions (24 hours)
        self.dependency_graph.cleanup(86400).await;

        // Clean up finality tracker caches
        for chain_id in self.chain_manager.connected_chains() {
            if let Ok(tracker) = self.chain_manager.get_finality_tracker(chain_id) {
                tracker.cleanup_cache(10000).await;
            }
        }
    }

    /// Stop the coordination engine
    pub async fn stop(&self) {
        *self.shutdown.write().await = true;
        info!("Coordination engine shutdown initiated");
    }
}
