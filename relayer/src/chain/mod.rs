//! Chain module - handles multi-chain connections and event listening
//!
//! This module provides:
//! - Multi-RPC provider management with automatic failover
//! - WebSocket event streaming with HTTP fallback
//! - Chain-specific finality tracking
//! - Automatic reconnection and health monitoring

pub mod finality;
pub mod listener;
pub mod provider;

pub use finality::FinalityTracker;
pub use listener::ChainListener;
pub use provider::{ChainProvider, GasPrice};

use crate::config::{ChainConfig, Settings};
use crate::error::{RelayerError, RelayerResult};
use crate::events::ContractEvent;
use crate::state::StateManager;

use dashmap::DashMap;
use std::sync::Arc;
use tokio::sync::{broadcast, mpsc, RwLock};
use tracing::{debug, error, info, warn};

/// Manages connections to all configured chains
pub struct ChainManager {
    /// Chain providers indexed by chain ID
    providers: DashMap<u64, Arc<ChainProvider>>,
    /// Chain listeners indexed by chain ID
    listeners: DashMap<u64, Arc<ChainListener>>,
    /// Finality trackers indexed by chain ID
    finality_trackers: DashMap<u64, Arc<FinalityTracker>>,
    /// Event broadcast channel
    event_tx: broadcast::Sender<ContractEvent>,
    /// State manager for persistence
    state_manager: Arc<StateManager>,
    /// Shutdown signal
    shutdown: Arc<RwLock<bool>>,
}

impl ChainManager {
    /// Create a new chain manager with all configured chains
    pub async fn new(settings: &Settings, state_manager: Arc<StateManager>) -> RelayerResult<Self> {
        let (event_tx, _) = broadcast::channel(10000);
        let providers = DashMap::new();
        let listeners = DashMap::new();
        let finality_trackers = DashMap::new();

        // Initialize providers for all enabled chains
        for (name, chain_config) in settings.enabled_chains() {
            if chain_config.contract_address.is_empty() {
                warn!("Skipping chain {} - no contract address configured", name);
                continue;
            }

            info!(
                "Initializing chain {} (ID: {})",
                chain_config.name, chain_config.chain_id
            );

            // Create provider
            let provider = ChainProvider::new(chain_config.clone()).await?;
            let provider = Arc::new(provider);
            providers.insert(chain_config.chain_id, provider.clone());

            // Create finality tracker
            let finality = FinalityTracker::new(
                chain_config.chain_id,
                chain_config.confirmation_blocks,
                provider.clone(),
            );
            finality_trackers.insert(chain_config.chain_id, Arc::new(finality));

            // Create listener
            let listener = ChainListener::new(
                chain_config.clone(),
                provider.clone(),
                event_tx.clone(),
                state_manager.clone(),
            )
            .await?;
            listeners.insert(chain_config.chain_id, Arc::new(listener));

            info!("Chain {} initialized successfully", chain_config.name);
        }

        Ok(Self {
            providers,
            listeners,
            finality_trackers,
            event_tx,
            state_manager,
            shutdown: Arc::new(RwLock::new(false)),
        })
    }

    /// Start all chain listeners
    pub async fn start_listeners(&self) -> RelayerResult<()> {
        let mut handles = Vec::new();

        for entry in self.listeners.iter() {
            let listener = entry.value().clone();
            let shutdown = self.shutdown.clone();

            let handle = tokio::spawn(async move {
                loop {
                    if *shutdown.read().await {
                        break;
                    }

                    if let Err(e) = listener.listen().await {
                        error!("Listener error for chain {}: {}", listener.chain_id(), e);
                        // Reconnect after delay
                        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                    }
                }
            });

            handles.push(handle);
        }

        // Wait for all listeners
        futures::future::join_all(handles).await;
        Ok(())
    }

    /// Subscribe to contract events from all chains
    pub fn subscribe_events(&self) -> broadcast::Receiver<ContractEvent> {
        self.event_tx.subscribe()
    }

    /// Get provider for a specific chain
    pub fn get_provider(&self, chain_id: u64) -> RelayerResult<Arc<ChainProvider>> {
        self.providers
            .get(&chain_id)
            .map(|p| p.clone())
            .ok_or(RelayerError::ChainNotFound { chain_id })
    }

    /// Get finality tracker for a specific chain
    pub fn get_finality_tracker(&self, chain_id: u64) -> RelayerResult<Arc<FinalityTracker>> {
        self.finality_trackers
            .get(&chain_id)
            .map(|f| f.clone())
            .ok_or(RelayerError::ChainNotFound { chain_id })
    }

    /// Health check for all chains
    pub async fn health_check(&self) -> Vec<(u64, bool)> {
        let mut results = Vec::new();

        for entry in self.providers.iter() {
            let chain_id = *entry.key();
            let provider = entry.value();
            let healthy = provider.health_check().await;
            results.push((chain_id, healthy));

            crate::metrics::record_chain_health(chain_id, healthy);
        }

        results
    }

    /// Get all connected chain IDs
    pub fn connected_chains(&self) -> Vec<u64> {
        self.providers.iter().map(|e| *e.key()).collect()
    }

    /// Stop all chain listeners
    pub async fn stop(&self) {
        *self.shutdown.write().await = true;
        info!("Chain manager stopped");
    }
}
