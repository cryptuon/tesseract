//! Error types for the Tesseract Relayer

use thiserror::Error;

/// Main error type for the relayer
#[derive(Error, Debug)]
pub enum RelayerError {
    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),

    #[error("Chain connection error for chain {chain_id}: {message}")]
    ChainConnection { chain_id: u64, message: String },

    #[error("Transaction error: {0}")]
    Transaction(String),

    #[error("Nonce error for chain {chain_id}: {message}")]
    Nonce { chain_id: u64, message: String },

    #[error("Gas estimation error: {0}")]
    GasEstimation(String),

    #[error("Event parsing error: {0}")]
    EventParsing(String),

    #[error("Coordination error: {0}")]
    Coordination(String),

    #[error("Wallet error: {0}")]
    Wallet(String),

    #[error("Contract error: {0}")]
    Contract(String),

    #[error("Timeout waiting for {operation}")]
    Timeout { operation: String },

    #[error("Chain {chain_id} not found")]
    ChainNotFound { chain_id: u64 },

    #[error("Transaction {tx_id} not found")]
    TransactionNotFound { tx_id: String },

    #[error("Invalid state transition from {from} to {to}")]
    InvalidStateTransition { from: String, to: String },

    #[error("Finality not reached for tx {tx_hash} on chain {chain_id}")]
    FinalityNotReached { chain_id: u64, tx_hash: String },

    #[error("Reorg detected on chain {chain_id} at block {block_number}")]
    ReorgDetected { chain_id: u64, block_number: u64 },

    #[error("Insufficient balance on chain {chain_id}: have {have}, need {need}")]
    InsufficientBalance {
        chain_id: u64,
        have: String,
        need: String,
    },

    #[error("Rate limited on chain {chain_id}")]
    RateLimited { chain_id: u64 },

    #[error("Internal error: {0}")]
    Internal(String),
}

impl RelayerError {
    /// Check if error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            RelayerError::ChainConnection { .. }
                | RelayerError::Timeout { .. }
                | RelayerError::RateLimited { .. }
                | RelayerError::FinalityNotReached { .. }
        )
    }

    /// Check if error should trigger an alert
    pub fn should_alert(&self) -> bool {
        matches!(
            self,
            RelayerError::InsufficientBalance { .. }
                | RelayerError::ReorgDetected { .. }
                | RelayerError::Wallet(_)
        )
    }
}

/// Result type for relayer operations
pub type RelayerResult<T> = Result<T, RelayerError>;
