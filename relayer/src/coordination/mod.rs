//! Coordination engine for cross-chain transaction orchestration
//!
//! The coordination engine:
//! 1. Monitors events from all connected chains
//! 2. Tracks transaction dependencies across chains
//! 3. Submits resolve_dependency calls on target chains
//! 4. Manages swap group atomicity

pub mod dependency;
pub mod engine;

pub use dependency::{DependencyGraph, PendingTransaction, TransactionState};
pub use engine::CoordinationEngine;
