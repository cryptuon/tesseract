//! Dependency graph for tracking cross-chain transaction dependencies

use std::collections::{HashMap, HashSet};
use tokio::sync::RwLock;

/// Transaction dependency tracking
#[derive(Debug, Clone)]
pub struct PendingTransaction {
    pub tx_id: [u8; 32],
    pub origin_chain: u64,
    pub target_chain: u64,
    pub dependency_id: Option<[u8; 32]>,
    pub swap_group_id: Option<[u8; 32]>,
    pub state: TransactionState,
    pub created_at: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum TransactionState {
    Buffered,
    DependencyPending,
    Ready,
    Submitted,
    Finalized,
    Failed,
    Expired,
}

/// Dependency graph for managing cross-chain transaction relationships
pub struct DependencyGraph {
    /// All tracked transactions
    transactions: RwLock<HashMap<[u8; 32], PendingTransaction>>,
    /// Dependencies: tx_id -> set of transactions waiting on it
    dependents: RwLock<HashMap<[u8; 32], HashSet<[u8; 32]>>>,
    /// Swap groups: group_id -> set of transaction IDs
    swap_groups: RwLock<HashMap<[u8; 32], HashSet<[u8; 32]>>>,
}

impl DependencyGraph {
    pub fn new() -> Self {
        Self {
            transactions: RwLock::new(HashMap::new()),
            dependents: RwLock::new(HashMap::new()),
            swap_groups: RwLock::new(HashMap::new()),
        }
    }

    /// Add a new transaction to track
    pub async fn add_transaction(&self, tx: PendingTransaction) {
        let tx_id = tx.tx_id;
        let dependency_id = tx.dependency_id;
        let swap_group_id = tx.swap_group_id;

        // Store transaction
        self.transactions.write().await.insert(tx_id, tx);

        // Track dependency relationship
        if let Some(dep_id) = dependency_id {
            self.dependents
                .write()
                .await
                .entry(dep_id)
                .or_insert_with(HashSet::new)
                .insert(tx_id);
        }

        // Track swap group membership
        if let Some(group_id) = swap_group_id {
            self.swap_groups
                .write()
                .await
                .entry(group_id)
                .or_insert_with(HashSet::new)
                .insert(tx_id);
        }
    }

    /// Mark a transaction as ready (dependency resolved)
    pub async fn mark_ready(&self, tx_id: &[u8; 32]) {
        if let Some(tx) = self.transactions.write().await.get_mut(tx_id) {
            tx.state = TransactionState::Ready;
        }
    }

    /// Mark a transaction as submitted
    pub async fn mark_submitted(&self, tx_id: &[u8; 32]) {
        if let Some(tx) = self.transactions.write().await.get_mut(tx_id) {
            tx.state = TransactionState::Submitted;
        }
    }

    /// Mark a transaction as finalized
    pub async fn mark_finalized(&self, tx_id: &[u8; 32]) {
        if let Some(tx) = self.transactions.write().await.get_mut(tx_id) {
            tx.state = TransactionState::Finalized;
        }

        // Notify dependents
        self.notify_dependents(tx_id).await;
    }

    /// Mark a transaction as failed
    pub async fn mark_failed(&self, tx_id: &[u8; 32]) {
        if let Some(tx) = self.transactions.write().await.get_mut(tx_id) {
            tx.state = TransactionState::Failed;
        }
    }

    /// Get transactions waiting on a dependency
    async fn notify_dependents(&self, resolved_tx_id: &[u8; 32]) {
        let dependents = self.dependents.read().await;
        if let Some(waiting) = dependents.get(resolved_tx_id) {
            let mut txs = self.transactions.write().await;
            for waiting_tx_id in waiting {
                if let Some(tx) = txs.get_mut(waiting_tx_id) {
                    if tx.state == TransactionState::DependencyPending {
                        tx.state = TransactionState::Ready;
                    }
                }
            }
        }
    }

    /// Get all transactions ready for submission on a specific chain
    pub async fn get_ready_for_chain(&self, target_chain: u64) -> Vec<PendingTransaction> {
        self.transactions
            .read()
            .await
            .values()
            .filter(|tx| {
                tx.target_chain == target_chain && tx.state == TransactionState::Ready
            })
            .cloned()
            .collect()
    }

    /// Get all transactions in a swap group
    pub async fn get_swap_group(&self, group_id: &[u8; 32]) -> Vec<PendingTransaction> {
        let group_txs = self.swap_groups.read().await;
        let txs = self.transactions.read().await;

        if let Some(tx_ids) = group_txs.get(group_id) {
            tx_ids
                .iter()
                .filter_map(|id| txs.get(id).cloned())
                .collect()
        } else {
            Vec::new()
        }
    }

    /// Check if all transactions in a swap group are ready
    pub async fn is_swap_group_ready(&self, group_id: &[u8; 32]) -> bool {
        let group_txs = self.get_swap_group(group_id).await;
        !group_txs.is_empty()
            && group_txs
                .iter()
                .all(|tx| tx.state == TransactionState::Ready)
    }

    /// Remove completed or expired transactions
    pub async fn cleanup(&self, max_age_secs: u64) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let mut txs = self.transactions.write().await;
        let to_remove: Vec<_> = txs
            .iter()
            .filter(|(_, tx)| {
                (tx.state == TransactionState::Finalized
                    || tx.state == TransactionState::Failed
                    || tx.state == TransactionState::Expired)
                    || (now - tx.created_at > max_age_secs)
            })
            .map(|(id, _)| *id)
            .collect();

        for id in to_remove {
            txs.remove(&id);
        }
    }

    /// Get transaction by ID
    pub async fn get_transaction(&self, tx_id: &[u8; 32]) -> Option<PendingTransaction> {
        self.transactions.read().await.get(tx_id).cloned()
    }

    /// Get all pending transactions
    pub async fn get_pending(&self) -> Vec<PendingTransaction> {
        self.transactions
            .read()
            .await
            .values()
            .filter(|tx| {
                matches!(
                    tx.state,
                    TransactionState::Buffered
                        | TransactionState::DependencyPending
                        | TransactionState::Ready
                        | TransactionState::Submitted
                )
            })
            .cloned()
            .collect()
    }
}

impl Default for DependencyGraph {
    fn default() -> Self {
        Self::new()
    }
}
