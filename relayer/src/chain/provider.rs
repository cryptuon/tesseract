//! Chain provider with multi-RPC support and automatic failover

use crate::config::{ChainConfig, GasPriceStrategy};
use crate::error::{RelayerError, RelayerResult};

use ethers::prelude::*;
use ethers::providers::{Http, Provider, Ws};
use ethers::types::transaction::eip2718::TypedTransaction;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

/// Multi-provider wrapper with automatic failover
pub struct ChainProvider {
    /// Chain configuration
    config: ChainConfig,
    /// HTTP providers (multiple for failover)
    http_providers: Vec<Provider<Http>>,
    /// Current active provider index
    current_provider: AtomicUsize,
    /// WebSocket provider (optional, for event streaming)
    ws_provider: RwLock<Option<Provider<Ws>>>,
    /// Last known block number
    last_block: RwLock<u64>,
}

impl ChainProvider {
    /// Create a new chain provider
    pub async fn new(config: ChainConfig) -> RelayerResult<Self> {
        let mut http_providers = Vec::new();

        // Initialize HTTP providers
        for url in &config.rpc_urls {
            match Provider::<Http>::try_from(url.as_str()) {
                Ok(provider) => {
                    let provider = provider.interval(Duration::from_millis(100));
                    http_providers.push(provider);
                    debug!("Added HTTP provider for chain {}: {}", config.chain_id, url);
                }
                Err(e) => {
                    warn!(
                        "Failed to create provider for {}: {}",
                        url, e
                    );
                }
            }
        }

        if http_providers.is_empty() {
            return Err(RelayerError::ChainConnection {
                chain_id: config.chain_id,
                message: "No valid RPC providers".to_string(),
            });
        }

        // Try to initialize WebSocket provider
        let ws_provider = if let Some(ref ws_url) = config.ws_url {
            match Provider::<Ws>::connect(ws_url).await {
                Ok(provider) => {
                    info!("WebSocket connected for chain {}", config.chain_id);
                    Some(provider)
                }
                Err(e) => {
                    warn!(
                        "WebSocket connection failed for chain {}: {}",
                        config.chain_id, e
                    );
                    None
                }
            }
        } else {
            None
        };

        // Get initial block number
        let initial_block = http_providers[0]
            .get_block_number()
            .await
            .map(|b| b.as_u64())
            .unwrap_or(0);

        Ok(Self {
            config,
            http_providers,
            current_provider: AtomicUsize::new(0),
            ws_provider: RwLock::new(ws_provider),
            last_block: RwLock::new(initial_block),
        })
    }

    /// Get the active HTTP provider
    pub fn http(&self) -> &Provider<Http> {
        let idx = self.current_provider.load(Ordering::Relaxed);
        &self.http_providers[idx % self.http_providers.len()]
    }

    /// Get WebSocket provider if available
    pub async fn ws(&self) -> Option<Provider<Ws>> {
        self.ws_provider.read().await.clone()
    }

    /// Switch to next available provider
    pub fn failover(&self) {
        let current = self.current_provider.load(Ordering::Relaxed);
        let next = (current + 1) % self.http_providers.len();
        self.current_provider.store(next, Ordering::Relaxed);
        warn!(
            "Chain {} failover to provider {}",
            self.config.chain_id, next
        );
    }

    /// Get current block number with failover
    pub async fn get_block_number(&self) -> RelayerResult<u64> {
        for _ in 0..self.http_providers.len() {
            match self.http().get_block_number().await {
                Ok(block) => {
                    let block_num = block.as_u64();
                    *self.last_block.write().await = block_num;
                    return Ok(block_num);
                }
                Err(e) => {
                    warn!(
                        "Failed to get block number from chain {}: {}",
                        self.config.chain_id, e
                    );
                    self.failover();
                }
            }
        }

        Err(RelayerError::ChainConnection {
            chain_id: self.config.chain_id,
            message: "All providers failed".to_string(),
        })
    }

    /// Get block with transaction receipts
    pub async fn get_block(&self, block_number: u64) -> RelayerResult<Option<Block<H256>>> {
        self.http()
            .get_block(block_number)
            .await
            .map_err(|e| RelayerError::ChainConnection {
                chain_id: self.config.chain_id,
                message: e.to_string(),
            })
    }

    /// Get transaction receipt
    pub async fn get_transaction_receipt(
        &self,
        tx_hash: H256,
    ) -> RelayerResult<Option<TransactionReceipt>> {
        self.http()
            .get_transaction_receipt(tx_hash)
            .await
            .map_err(|e| RelayerError::ChainConnection {
                chain_id: self.config.chain_id,
                message: e.to_string(),
            })
    }

    /// Get logs for a filter
    pub async fn get_logs(&self, filter: &Filter) -> RelayerResult<Vec<Log>> {
        for _ in 0..self.http_providers.len() {
            match self.http().get_logs(filter).await {
                Ok(logs) => return Ok(logs),
                Err(e) => {
                    warn!(
                        "Failed to get logs from chain {}: {}",
                        self.config.chain_id, e
                    );
                    self.failover();
                }
            }
        }

        Err(RelayerError::ChainConnection {
            chain_id: self.config.chain_id,
            message: "All providers failed to get logs".to_string(),
        })
    }

    /// Estimate gas for a transaction
    pub async fn estimate_gas(&self, tx: &TypedTransaction) -> RelayerResult<U256> {
        self.http()
            .estimate_gas(tx, None)
            .await
            .map_err(|e| RelayerError::GasEstimation(e.to_string()))
    }

    /// Get current gas price based on chain strategy
    pub async fn get_gas_price(&self) -> RelayerResult<GasPrice> {
        match self.config.gas_price_strategy {
            GasPriceStrategy::Legacy => {
                let price = self.http().get_gas_price().await.map_err(|e| {
                    RelayerError::GasEstimation(e.to_string())
                })?;
                Ok(GasPrice::Legacy(price))
            }
            GasPriceStrategy::Eip1559 | GasPriceStrategy::Optimism => {
                let (max_fee, priority_fee) = self.estimate_eip1559_fees().await?;
                Ok(GasPrice::Eip1559 {
                    max_fee_per_gas: max_fee,
                    max_priority_fee_per_gas: priority_fee,
                })
            }
            GasPriceStrategy::Arbitrum => {
                // Arbitrum uses L1 + L2 gas model
                let price = self.http().get_gas_price().await.map_err(|e| {
                    RelayerError::GasEstimation(e.to_string())
                })?;
                Ok(GasPrice::Legacy(price))
            }
        }
    }

    /// Estimate EIP-1559 fees
    async fn estimate_eip1559_fees(&self) -> RelayerResult<(U256, U256)> {
        let block = self
            .http()
            .get_block(BlockNumber::Latest)
            .await
            .map_err(|e| RelayerError::GasEstimation(e.to_string()))?
            .ok_or_else(|| RelayerError::GasEstimation("No latest block".to_string()))?;

        let base_fee = block
            .base_fee_per_gas
            .ok_or_else(|| RelayerError::GasEstimation("No base fee in block".to_string()))?;

        // Priority fee estimation (can be improved with fee history)
        let priority_fee = U256::from(2_000_000_000u64); // 2 gwei default

        // Max fee = 2 * base_fee + priority_fee (buffer for block variability)
        let max_fee = base_fee * 2 + priority_fee;

        // Cap at configured max
        let max_gwei = U256::from(self.config.max_gas_price_gwei) * U256::from(1_000_000_000u64);
        let max_fee = std::cmp::min(max_fee, max_gwei);

        Ok((max_fee, priority_fee))
    }

    /// Health check
    pub async fn health_check(&self) -> bool {
        match self.get_block_number().await {
            Ok(_) => true,
            Err(e) => {
                error!("Health check failed for chain {}: {}", self.config.chain_id, e);
                false
            }
        }
    }

    /// Get chain ID
    pub fn chain_id(&self) -> u64 {
        self.config.chain_id
    }

    /// Get contract address
    pub fn contract_address(&self) -> &str {
        &self.config.contract_address
    }

    /// Get coordinator address
    pub fn coordinator_address(&self) -> &str {
        &self.config.coordinator_address
    }

    /// Get confirmation blocks
    pub fn confirmation_blocks(&self) -> u64 {
        self.config.confirmation_blocks
    }

    /// Reconnect WebSocket
    pub async fn reconnect_ws(&self) -> RelayerResult<()> {
        if let Some(ref ws_url) = self.config.ws_url {
            match Provider::<Ws>::connect(ws_url).await {
                Ok(provider) => {
                    *self.ws_provider.write().await = Some(provider);
                    info!("WebSocket reconnected for chain {}", self.config.chain_id);
                    Ok(())
                }
                Err(e) => Err(RelayerError::ChainConnection {
                    chain_id: self.config.chain_id,
                    message: format!("WebSocket reconnection failed: {}", e),
                }),
            }
        } else {
            Ok(())
        }
    }
}

/// Gas price types
#[derive(Debug, Clone)]
pub enum GasPrice {
    Legacy(U256),
    Eip1559 {
        max_fee_per_gas: U256,
        max_priority_fee_per_gas: U256,
    },
}
