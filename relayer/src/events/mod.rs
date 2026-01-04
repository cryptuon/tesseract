//! Contract event types and parsing
//!
//! Defines event types emitted by TesseractBuffer and AtomicSwapCoordinator contracts.

use crate::error::{RelayerError, RelayerResult};

use ethers::abi::{Abi, Event, RawLog};
use ethers::prelude::*;
use serde::{Deserialize, Serialize};
use std::str::FromStr;

/// Events emitted by TesseractBuffer contract
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContractEvent {
    /// Transaction buffered
    TransactionBuffered {
        chain_id: u64,
        tx_id: [u8; 32],
        origin_rollup: Address,
        target_rollup: Address,
        timestamp: u64,
        block_number: u64,
        tx_hash: H256,
    },

    /// Dependency resolved
    DependencyResolved {
        chain_id: u64,
        tx_id: [u8; 32],
        dependency_id: [u8; 32],
        block_number: u64,
        tx_hash: H256,
    },

    /// Transaction marked ready
    TransactionReady {
        chain_id: u64,
        tx_id: [u8; 32],
        block_number: u64,
        tx_hash: H256,
    },

    /// Transaction executed
    TransactionExecuted {
        chain_id: u64,
        tx_id: [u8; 32],
        block_number: u64,
        tx_hash: H256,
    },

    /// Transaction failed
    TransactionFailed {
        chain_id: u64,
        tx_id: [u8; 32],
        reason: String,
        block_number: u64,
        tx_hash: H256,
    },

    /// Transaction expired
    TransactionExpired {
        chain_id: u64,
        tx_id: [u8; 32],
        block_number: u64,
        tx_hash: H256,
    },

    /// Transaction refunded
    TransactionRefunded {
        chain_id: u64,
        tx_id: [u8; 32],
        recipient: Address,
        block_number: u64,
        tx_hash: H256,
    },

    /// Swap group created
    SwapGroupCreated {
        chain_id: u64,
        swap_group_id: [u8; 32],
        block_number: u64,
        tx_hash: H256,
    },

    /// Swap order created (from AtomicSwapCoordinator)
    SwapOrderCreated {
        chain_id: u64,
        order_id: [u8; 32],
        maker: Address,
        offer_chain: Address,
        want_chain: Address,
        offer_amount: U256,
        want_amount: U256,
        deadline: u64,
        block_number: u64,
        tx_hash: H256,
    },

    /// Swap fill created
    SwapFillCreated {
        chain_id: u64,
        order_id: [u8; 32],
        fill_id: [u8; 32],
        taker: Address,
        offer_amount_filled: U256,
        want_amount_filled: U256,
        block_number: u64,
        tx_hash: H256,
    },

    /// Swap completed
    SwapCompleted {
        chain_id: u64,
        order_id: [u8; 32],
        block_number: u64,
        tx_hash: H256,
    },

    /// Contract paused
    ContractPaused {
        chain_id: u64,
        block_number: u64,
        tx_hash: H256,
    },

    /// Contract unpaused
    ContractUnpaused {
        chain_id: u64,
        block_number: u64,
        tx_hash: H256,
    },

    /// Circuit breaker triggered
    CircuitBreakerTriggered {
        chain_id: u64,
        failure_count: u64,
        block_number: u64,
        tx_hash: H256,
    },

    /// Unknown event
    Unknown {
        chain_id: u64,
        topic: H256,
        block_number: u64,
        tx_hash: H256,
    },
}

impl ContractEvent {
    /// Get the chain ID for this event
    pub fn chain_id(&self) -> u64 {
        match self {
            ContractEvent::TransactionBuffered { chain_id, .. } => *chain_id,
            ContractEvent::DependencyResolved { chain_id, .. } => *chain_id,
            ContractEvent::TransactionReady { chain_id, .. } => *chain_id,
            ContractEvent::TransactionExecuted { chain_id, .. } => *chain_id,
            ContractEvent::TransactionFailed { chain_id, .. } => *chain_id,
            ContractEvent::TransactionExpired { chain_id, .. } => *chain_id,
            ContractEvent::TransactionRefunded { chain_id, .. } => *chain_id,
            ContractEvent::SwapGroupCreated { chain_id, .. } => *chain_id,
            ContractEvent::SwapOrderCreated { chain_id, .. } => *chain_id,
            ContractEvent::SwapFillCreated { chain_id, .. } => *chain_id,
            ContractEvent::SwapCompleted { chain_id, .. } => *chain_id,
            ContractEvent::ContractPaused { chain_id, .. } => *chain_id,
            ContractEvent::ContractUnpaused { chain_id, .. } => *chain_id,
            ContractEvent::CircuitBreakerTriggered { chain_id, .. } => *chain_id,
            ContractEvent::Unknown { chain_id, .. } => *chain_id,
        }
    }

    /// Get event name for metrics
    pub fn name(&self) -> &'static str {
        match self {
            ContractEvent::TransactionBuffered { .. } => "transaction_buffered",
            ContractEvent::DependencyResolved { .. } => "dependency_resolved",
            ContractEvent::TransactionReady { .. } => "transaction_ready",
            ContractEvent::TransactionExecuted { .. } => "transaction_executed",
            ContractEvent::TransactionFailed { .. } => "transaction_failed",
            ContractEvent::TransactionExpired { .. } => "transaction_expired",
            ContractEvent::TransactionRefunded { .. } => "transaction_refunded",
            ContractEvent::SwapGroupCreated { .. } => "swap_group_created",
            ContractEvent::SwapOrderCreated { .. } => "swap_order_created",
            ContractEvent::SwapFillCreated { .. } => "swap_fill_created",
            ContractEvent::SwapCompleted { .. } => "swap_completed",
            ContractEvent::ContractPaused { .. } => "contract_paused",
            ContractEvent::ContractUnpaused { .. } => "contract_unpaused",
            ContractEvent::CircuitBreakerTriggered { .. } => "circuit_breaker_triggered",
            ContractEvent::Unknown { .. } => "unknown",
        }
    }

    /// Check if this event requires coordination action
    pub fn requires_action(&self) -> bool {
        matches!(
            self,
            ContractEvent::TransactionBuffered { .. }
                | ContractEvent::TransactionReady { .. }
                | ContractEvent::SwapFillCreated { .. }
        )
    }
}

/// Event topic signatures (keccak256 of event signature)
pub mod topics {
    use ethers::types::H256;
    use lazy_static::lazy_static;

    lazy_static! {
        // TesseractBuffer events
        pub static ref TRANSACTION_BUFFERED: H256 =
            "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                .parse()
                .unwrap();
        pub static ref DEPENDENCY_RESOLVED: H256 =
            "0x2234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                .parse()
                .unwrap();
        pub static ref TRANSACTION_READY: H256 =
            "0x3234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                .parse()
                .unwrap();
        // Add more as needed
    }
}

/// Event parser for TesseractBuffer and AtomicSwapCoordinator contracts
pub struct EventParser {
    chain_id: u64,
    contract_address: Address,
}

impl EventParser {
    /// Create a new event parser
    pub fn new(contract_address: &str) -> RelayerResult<Self> {
        let address = Address::from_str(contract_address)
            .map_err(|e| RelayerError::Config(format!("Invalid address: {}", e)))?;

        // Chain ID will be set when parsing
        Ok(Self {
            chain_id: 0,
            contract_address: address,
        })
    }

    /// Set chain ID for parsed events
    pub fn with_chain_id(mut self, chain_id: u64) -> Self {
        self.chain_id = chain_id;
        self
    }

    /// Parse a log entry into a ContractEvent
    pub fn parse_log(&self, log: &Log) -> RelayerResult<ContractEvent> {
        let block_number = log.block_number.map(|b| b.as_u64()).unwrap_or(0);
        let tx_hash = log.transaction_hash.unwrap_or_default();

        // Get primary topic
        let topic = log.topics.first().copied().unwrap_or_default();

        // Parse based on topic signature
        // In production, we'd match against actual event signatures
        // For now, return Unknown for unrecognized events
        Ok(ContractEvent::Unknown {
            chain_id: self.chain_id,
            topic,
            block_number,
            tx_hash,
        })
    }

    /// Parse TransactionBuffered event data
    fn parse_transaction_buffered(&self, log: &Log) -> RelayerResult<ContractEvent> {
        let block_number = log.block_number.map(|b| b.as_u64()).unwrap_or(0);
        let tx_hash = log.transaction_hash.unwrap_or_default();

        // Parse indexed parameters from topics
        let tx_id: [u8; 32] = log.topics.get(1)
            .map(|t| t.0)
            .unwrap_or_default();

        let origin_rollup = log.topics.get(2)
            .map(|t| Address::from_slice(&t.0[12..32]))
            .unwrap_or_default();

        let target_rollup = log.topics.get(3)
            .map(|t| Address::from_slice(&t.0[12..32]))
            .unwrap_or_default();

        // Parse non-indexed parameters from data
        let timestamp = if log.data.len() >= 32 {
            U256::from_big_endian(&log.data[0..32]).as_u64()
        } else {
            0
        };

        Ok(ContractEvent::TransactionBuffered {
            chain_id: self.chain_id,
            tx_id,
            origin_rollup,
            target_rollup,
            timestamp,
            block_number,
            tx_hash,
        })
    }
}
