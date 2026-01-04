//! Chain finality tracking for different L1/L2 networks
//!
//! Different chains have different finality models:
//! - Ethereum: Probabilistic (32 blocks for practical finality, ~6 min)
//! - Polygon: Probabilistic (128 blocks)
//! - Arbitrum: L1 finality (challenge period ~7 days for full, but we use soft finality)
//! - Optimism: L1 finality (same as Arbitrum)
//! - Avalanche: Instant finality (1 block)

use crate::chain::ChainProvider;
use crate::error::{RelayerError, RelayerResult};

use ethers::types::H256;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

/// Tracks finality for transactions on a specific chain
pub struct FinalityTracker {
    /// Chain ID
    chain_id: u64,
    /// Required confirmation blocks
    confirmation_blocks: u64,
    /// Chain provider
    provider: Arc<ChainProvider>,
    /// Pending transactions: tx_hash -> block_number
    pending: RwLock<HashMap<H256, u64>>,
    /// Finalized transactions (cached to avoid re-checking)
    finalized: RwLock<HashMap<H256, bool>>,
}

impl FinalityTracker {
    /// Create a new finality tracker
    pub fn new(
        chain_id: u64,
        confirmation_blocks: u64,
        provider: Arc<ChainProvider>,
    ) -> Self {
        Self {
            chain_id,
            confirmation_blocks,
            provider,
            pending: RwLock::new(HashMap::new()),
            finalized: RwLock::new(HashMap::new()),
        }
    }

    /// Track a new transaction for finality
    pub async fn track(&self, tx_hash: H256, block_number: u64) {
        self.pending.write().await.insert(tx_hash, block_number);
        debug!(
            "Tracking tx {} for finality on chain {} (block {})",
            tx_hash, self.chain_id, block_number
        );
    }

    /// Check if a transaction has reached finality
    pub async fn is_finalized(&self, tx_hash: H256) -> RelayerResult<bool> {
        // Check cache first
        if let Some(&finalized) = self.finalized.read().await.get(&tx_hash) {
            return Ok(finalized);
        }

        // Get current block
        let current_block = self.provider.get_block_number().await?;

        // Check if we're tracking this tx
        let pending = self.pending.read().await;
        if let Some(&tx_block) = pending.get(&tx_hash) {
            let confirmations = current_block.saturating_sub(tx_block);

            if confirmations >= self.confirmation_blocks {
                // Verify the transaction is still included (reorg protection)
                if self.verify_inclusion(tx_hash).await? {
                    // Cache the result
                    drop(pending);
                    self.finalized.write().await.insert(tx_hash, true);
                    self.pending.write().await.remove(&tx_hash);

                    info!(
                        "Transaction {} finalized on chain {} ({} confirmations)",
                        tx_hash, self.chain_id, confirmations
                    );
                    return Ok(true);
                } else {
                    // Reorg detected!
                    warn!(
                        "Reorg detected: tx {} no longer included on chain {}",
                        tx_hash, self.chain_id
                    );
                    return Err(RelayerError::ReorgDetected {
                        chain_id: self.chain_id,
                        block_number: tx_block,
                    });
                }
            }

            debug!(
                "Transaction {} has {} / {} confirmations on chain {}",
                tx_hash, confirmations, self.confirmation_blocks, self.chain_id
            );
            return Ok(false);
        }

        // Not tracked - try to get info from chain
        if let Some(receipt) = self.provider.get_transaction_receipt(tx_hash).await? {
            if let Some(block_num) = receipt.block_number {
                let confirmations = current_block.saturating_sub(block_num.as_u64());
                if confirmations >= self.confirmation_blocks {
                    self.finalized.write().await.insert(tx_hash, true);
                    return Ok(true);
                } else {
                    // Start tracking
                    self.pending
                        .write()
                        .await
                        .insert(tx_hash, block_num.as_u64());
                    return Ok(false);
                }
            }
        }

        // Transaction not found
        Err(RelayerError::TransactionNotFound {
            tx_id: format!("{:?}", tx_hash),
        })
    }

    /// Verify a transaction is still included in the chain
    async fn verify_inclusion(&self, tx_hash: H256) -> RelayerResult<bool> {
        match self.provider.get_transaction_receipt(tx_hash).await? {
            Some(receipt) => Ok(receipt.status == Some(1.into())),
            None => Ok(false),
        }
    }

    /// Get pending transaction count
    pub async fn pending_count(&self) -> usize {
        self.pending.read().await.len()
    }

    /// Check all pending transactions and return newly finalized ones
    pub async fn check_pending(&self) -> RelayerResult<Vec<H256>> {
        let current_block = self.provider.get_block_number().await?;
        let mut finalized = Vec::new();

        let pending = self.pending.read().await.clone();
        for (tx_hash, tx_block) in pending {
            let confirmations = current_block.saturating_sub(tx_block);
            if confirmations >= self.confirmation_blocks {
                if self.verify_inclusion(tx_hash).await? {
                    finalized.push(tx_hash);
                }
            }
        }

        // Update state
        for tx_hash in &finalized {
            self.pending.write().await.remove(tx_hash);
            self.finalized.write().await.insert(*tx_hash, true);
        }

        Ok(finalized)
    }

    /// Clear old finalized cache entries (call periodically)
    pub async fn cleanup_cache(&self, max_entries: usize) {
        let mut finalized = self.finalized.write().await;
        if finalized.len() > max_entries {
            // Simple FIFO-ish cleanup - just clear half
            let to_remove: Vec<_> = finalized
                .keys()
                .take(finalized.len() / 2)
                .cloned()
                .collect();
            for k in to_remove {
                finalized.remove(&k);
            }
        }
    }
}

/// Get recommended confirmation blocks for a chain
pub fn recommended_confirmations(chain_id: u64) -> u64 {
    match chain_id {
        // Ethereum mainnet
        1 => 32,
        // Ethereum testnets
        11155111 | 5 => 12,
        // Polygon mainnet
        137 => 128,
        // Polygon testnets
        80001 | 80002 => 32,
        // Arbitrum
        42161 | 421614 => 64,
        // Optimism
        10 | 11155420 => 64,
        // Base
        8453 | 84532 => 64,
        // Avalanche (instant finality)
        43114 | 43113 => 1,
        // Default conservative
        _ => 64,
    }
}
