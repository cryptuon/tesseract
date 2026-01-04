//! State management with PostgreSQL persistence
//!
//! Handles:
//! - Transaction state persistence
//! - Block checkpoints for restart recovery
//! - Event storage
//! - Submission tracking

mod manager;

pub use manager::StateManager;
