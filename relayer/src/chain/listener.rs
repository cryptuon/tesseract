//! Chain event listener with WebSocket streaming and HTTP polling fallback

use crate::config::ChainConfig;
use crate::error::{RelayerError, RelayerResult};
use crate::events::{ContractEvent, EventParser};
use crate::state::StateManager;

use super::ChainProvider;

use ethers::prelude::*;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::broadcast;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

/// Listens for contract events on a specific chain
pub struct ChainListener {
    /// Chain configuration
    config: ChainConfig,
    /// Chain provider
    provider: Arc<ChainProvider>,
    /// Event broadcast channel
    event_tx: broadcast::Sender<ContractEvent>,
    /// State manager for checkpoint persistence
    state_manager: Arc<StateManager>,
    /// Last processed block
    last_processed_block: RwLock<u64>,
    /// Event parser
    event_parser: EventParser,
}

impl ChainListener {
    /// Create a new chain listener
    pub async fn new(
        config: ChainConfig,
        provider: Arc<ChainProvider>,
        event_tx: broadcast::Sender<ContractEvent>,
        state_manager: Arc<StateManager>,
    ) -> RelayerResult<Self> {
        // Load last checkpoint from database
        let last_block = state_manager
            .get_checkpoint(config.chain_id)
            .await
            .unwrap_or(0);

        let event_parser = EventParser::new(&config.contract_address)?;

        Ok(Self {
            config,
            provider,
            event_tx,
            state_manager,
            last_processed_block: RwLock::new(last_block),
            event_parser,
        })
    }

    /// Get chain ID
    pub fn chain_id(&self) -> u64 {
        self.config.chain_id
    }

    /// Main listening loop
    pub async fn listen(&self) -> RelayerResult<()> {
        // Try WebSocket first, fall back to polling
        if let Some(_ws) = self.provider.ws().await {
            info!("Using WebSocket for chain {}", self.config.chain_id);
            self.listen_ws().await
        } else {
            info!("Using HTTP polling for chain {}", self.config.chain_id);
            self.listen_polling().await
        }
    }

    /// WebSocket-based event listening
    async fn listen_ws(&self) -> RelayerResult<()> {
        let contract_address: Address = self
            .config
            .contract_address
            .parse()
            .map_err(|e| RelayerError::Config(format!("Invalid contract address: {}", e)))?;

        // Create event filter
        let filter = Filter::new()
            .address(contract_address)
            .from_block(BlockNumber::Latest);

        // Note: In production, we'd use the WS provider's subscribe_logs
        // For now, fall back to polling since ethers-rs WS can be tricky
        self.listen_polling().await
    }

    /// HTTP polling-based event listening
    async fn listen_polling(&self) -> RelayerResult<()> {
        let contract_address: Address = self
            .config
            .contract_address
            .parse()
            .map_err(|e| RelayerError::Config(format!("Invalid contract address: {}", e)))?;

        let poll_interval = Duration::from_secs(2);

        loop {
            // Get current block
            let current_block = match self.provider.get_block_number().await {
                Ok(b) => b,
                Err(e) => {
                    warn!("Failed to get block number: {}", e);
                    tokio::time::sleep(poll_interval).await;
                    continue;
                }
            };

            let last_block = *self.last_processed_block.read().await;

            // Only process if we have new blocks
            if current_block <= last_block {
                tokio::time::sleep(poll_interval).await;
                continue;
            }

            // Calculate block range (limit to prevent huge queries)
            let from_block = last_block + 1;
            let to_block = std::cmp::min(current_block, from_block + 1000);

            debug!(
                "Chain {}: Processing blocks {} to {}",
                self.config.chain_id, from_block, to_block
            );

            // Create filter for block range
            let filter = Filter::new()
                .address(contract_address)
                .from_block(from_block)
                .to_block(to_block);

            // Get logs
            match self.provider.get_logs(&filter).await {
                Ok(logs) => {
                    for log in logs {
                        if let Err(e) = self.process_log(log).await {
                            error!("Failed to process log: {}", e);
                        }
                    }

                    // Update checkpoint
                    *self.last_processed_block.write().await = to_block;
                    if let Err(e) = self
                        .state_manager
                        .save_checkpoint(self.config.chain_id, to_block)
                        .await
                    {
                        warn!("Failed to save checkpoint: {}", e);
                    }

                    crate::metrics::record_blocks_processed(self.config.chain_id, to_block);
                }
                Err(e) => {
                    warn!("Failed to get logs: {}", e);
                    // Don't update checkpoint, will retry
                }
            }

            tokio::time::sleep(poll_interval).await;
        }
    }

    /// Process a single log entry
    async fn process_log(&self, log: Log) -> RelayerResult<()> {
        let event = self.event_parser.parse_log(&log)?;

        debug!(
            "Chain {} event: {:?}",
            self.config.chain_id, event
        );

        // Record metric
        crate::metrics::record_event(self.config.chain_id, &event);

        // Broadcast event
        if self.event_tx.send(event.clone()).is_err() {
            // No receivers, that's okay
        }

        // Store event in database
        self.state_manager.store_event(&event).await?;

        Ok(())
    }
}
