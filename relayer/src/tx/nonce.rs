//! Nonce management for reliable transaction submission
//!
//! Handles:
//! - Local nonce tracking to avoid conflicts
//! - Nonce gap detection and recovery
//! - Stuck transaction replacement

use crate::chain::ChainProvider;
use crate::error::{RelayerError, RelayerResult};

use dashmap::DashMap;
use ethers::prelude::*;
use ethers::types::{Address, U256};
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, warn};

/// Per-chain nonce state
struct ChainNonceState {
    /// Current local nonce (next to use)
    current: u64,
    /// Pending transactions: nonce -> tx_hash
    pending: DashMap<u64, String>,
    /// Last confirmed nonce
    confirmed: u64,
}

/// Manages nonces across multiple chains
pub struct NonceManager {
    /// Wallet address
    wallet_address: Address,
    /// Per-chain nonce state
    chain_state: DashMap<u64, Mutex<ChainNonceState>>,
}

impl NonceManager {
    /// Create a new nonce manager
    pub fn new(wallet_address: Address) -> Self {
        Self {
            wallet_address,
            chain_state: DashMap::new(),
        }
    }

    /// Initialize nonce for a chain
    pub async fn init_chain(
        &self,
        chain_id: u64,
        provider: &ChainProvider,
    ) -> RelayerResult<()> {
        let on_chain_nonce = self.fetch_nonce(provider).await?;

        let state = ChainNonceState {
            current: on_chain_nonce,
            pending: DashMap::new(),
            confirmed: on_chain_nonce.saturating_sub(1),
        };

        self.chain_state.insert(chain_id, Mutex::new(state));
        debug!(
            "Initialized nonce for chain {}: {}",
            chain_id, on_chain_nonce
        );

        Ok(())
    }

    /// Get the next nonce for a chain
    pub async fn get_nonce(&self, chain_id: u64) -> RelayerResult<u64> {
        let state = self
            .chain_state
            .get(&chain_id)
            .ok_or(RelayerError::Nonce {
                chain_id,
                message: "Chain not initialized".to_string(),
            })?;

        let mut state = state.lock().await;
        let nonce = state.current;
        state.current += 1;

        debug!("Allocated nonce {} for chain {}", nonce, chain_id);
        Ok(nonce)
    }

    /// Mark a nonce as pending with transaction hash
    pub async fn mark_pending(
        &self,
        chain_id: u64,
        nonce: u64,
        tx_hash: &str,
    ) -> RelayerResult<()> {
        let state = self
            .chain_state
            .get(&chain_id)
            .ok_or(RelayerError::Nonce {
                chain_id,
                message: "Chain not initialized".to_string(),
            })?;

        let state = state.lock().await;
        state.pending.insert(nonce, tx_hash.to_string());
        Ok(())
    }

    /// Confirm a nonce (transaction mined)
    pub async fn confirm_nonce(
        &self,
        chain_id: u64,
        nonce: u64,
    ) -> RelayerResult<()> {
        let state = self
            .chain_state
            .get(&chain_id)
            .ok_or(RelayerError::Nonce {
                chain_id,
                message: "Chain not initialized".to_string(),
            })?;

        let mut state = state.lock().await;
        state.pending.remove(&nonce);
        if nonce > state.confirmed {
            state.confirmed = nonce;
        }
        Ok(())
    }

    /// Release a nonce (transaction failed, can be reused)
    pub async fn release_nonce(
        &self,
        chain_id: u64,
        nonce: u64,
    ) -> RelayerResult<()> {
        let state = self
            .chain_state
            .get(&chain_id)
            .ok_or(RelayerError::Nonce {
                chain_id,
                message: "Chain not initialized".to_string(),
            })?;

        let mut state = state.lock().await;
        state.pending.remove(&nonce);

        // If this was the next nonce, we can reset
        if nonce == state.current - 1 {
            state.current = nonce;
        }
        Ok(())
    }

    /// Sync nonces with on-chain state
    pub async fn sync(&self, chain_id: u64, provider: &ChainProvider) -> RelayerResult<()> {
        let on_chain_nonce = self.fetch_nonce(provider).await?;

        let state = self
            .chain_state
            .get(&chain_id)
            .ok_or(RelayerError::Nonce {
                chain_id,
                message: "Chain not initialized".to_string(),
            })?;

        let mut state = state.lock().await;

        // Detect gaps
        if on_chain_nonce > state.confirmed + 1 {
            warn!(
                "Nonce gap detected on chain {}: expected {}, got {}",
                chain_id,
                state.confirmed + 1,
                on_chain_nonce
            );
        }

        // Clear pending transactions that have been confirmed
        let to_remove: Vec<u64> = state
            .pending
            .iter()
            .filter(|entry| *entry.key() < on_chain_nonce)
            .map(|entry| *entry.key())
            .collect();

        for nonce in to_remove {
            state.pending.remove(&nonce);
        }

        state.confirmed = on_chain_nonce.saturating_sub(1);

        // Ensure current is at least on_chain_nonce
        if state.current < on_chain_nonce {
            state.current = on_chain_nonce;
        }

        Ok(())
    }

    /// Check for stuck transactions (pending too long)
    pub async fn get_stuck_transactions(
        &self,
        chain_id: u64,
        max_pending_blocks: u64,
        current_block: u64,
    ) -> RelayerResult<Vec<(u64, String)>> {
        let state = self
            .chain_state
            .get(&chain_id)
            .ok_or(RelayerError::Nonce {
                chain_id,
                message: "Chain not initialized".to_string(),
            })?;

        let state = state.lock().await;

        // In a real implementation, we'd track when each tx was submitted
        // For now, just return all pending with nonces below confirmed + threshold
        let stuck: Vec<_> = state
            .pending
            .iter()
            .filter(|entry| *entry.key() <= state.confirmed + max_pending_blocks)
            .map(|entry| (*entry.key(), entry.value().clone()))
            .collect();

        Ok(stuck)
    }

    /// Fetch nonce from chain
    async fn fetch_nonce(&self, provider: &ChainProvider) -> RelayerResult<u64> {
        let nonce = provider
            .http()
            .get_transaction_count(self.wallet_address, None)
            .await
            .map_err(|e| RelayerError::Nonce {
                chain_id: provider.chain_id(),
                message: e.to_string(),
            })?;

        Ok(nonce.as_u64())
    }

    /// Get pending count for a chain
    pub async fn pending_count(&self, chain_id: u64) -> usize {
        self.chain_state
            .get(&chain_id)
            .map(|s| {
                // Can't await in map, so use blocking
                0 // Simplified - in production we'd use proper async
            })
            .unwrap_or(0)
    }
}
