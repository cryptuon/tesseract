//! Prometheus metrics for monitoring
//!
//! Exposes metrics for:
//! - Chain connection status
//! - Transaction processing
//! - Event counts
//! - Error rates

use crate::error::RelayerResult;
use crate::events::ContractEvent;

use axum::{routing::get, Router};
use lazy_static::lazy_static;
use prometheus::{
    register_counter_vec, register_gauge_vec, register_histogram_vec,
    CounterVec, Encoder, GaugeVec, HistogramVec, TextEncoder,
};
use std::net::SocketAddr;
use tracing::info;

lazy_static! {
    // Chain metrics
    pub static ref CHAIN_CONNECTED: GaugeVec = register_gauge_vec!(
        "tesseract_chain_connected",
        "Chain connection status (1=connected, 0=disconnected)",
        &["chain_id"]
    ).unwrap();

    pub static ref CHAIN_BLOCK_HEIGHT: GaugeVec = register_gauge_vec!(
        "tesseract_chain_block_height",
        "Current block height per chain",
        &["chain_id"]
    ).unwrap();

    // Event metrics
    pub static ref EVENTS_RECEIVED: CounterVec = register_counter_vec!(
        "tesseract_events_received_total",
        "Total events received by type",
        &["chain_id", "event_type"]
    ).unwrap();

    // Transaction metrics
    pub static ref TX_BUFFERED: CounterVec = register_counter_vec!(
        "tesseract_transactions_buffered_total",
        "Total transactions buffered",
        &["chain_id"]
    ).unwrap();

    pub static ref TX_SUBMITTED: CounterVec = register_counter_vec!(
        "tesseract_transactions_submitted_total",
        "Total transactions submitted",
        &["chain_id"]
    ).unwrap();

    pub static ref TX_FINALIZED: CounterVec = register_counter_vec!(
        "tesseract_transactions_finalized_total",
        "Total transactions finalized",
        &["chain_id"]
    ).unwrap();

    pub static ref TX_FAILED: CounterVec = register_counter_vec!(
        "tesseract_transactions_failed_total",
        "Total transactions failed",
        &["chain_id"]
    ).unwrap();

    pub static ref TX_LATENCY: HistogramVec = register_histogram_vec!(
        "tesseract_transaction_latency_seconds",
        "Transaction processing latency",
        &["chain_id"],
        vec![0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
    ).unwrap();

    // Swap metrics
    pub static ref SWAP_FILLS: CounterVec = register_counter_vec!(
        "tesseract_swap_fills_total",
        "Total swap fills processed",
        &["chain_id"]
    ).unwrap();

    // Contract state metrics
    pub static ref CONTRACT_PAUSED: GaugeVec = register_gauge_vec!(
        "tesseract_contract_paused",
        "Contract pause status (1=paused, 0=active)",
        &["chain_id"]
    ).unwrap();

    pub static ref CIRCUIT_BREAKER: CounterVec = register_counter_vec!(
        "tesseract_circuit_breaker_triggers_total",
        "Total circuit breaker triggers",
        &["chain_id"]
    ).unwrap();

    // Wallet metrics
    pub static ref WALLET_BALANCE: GaugeVec = register_gauge_vec!(
        "tesseract_wallet_balance_eth",
        "Wallet balance in ETH",
        &["chain_id"]
    ).unwrap();

    // Health metrics
    pub static ref HEALTH_CHECK_SUCCESS: CounterVec = register_counter_vec!(
        "tesseract_health_check_success_total",
        "Total successful health checks",
        &[]
    ).unwrap();

    pub static ref HEALTH_CHECK_FAILURE: CounterVec = register_counter_vec!(
        "tesseract_health_check_failure_total",
        "Total failed health checks",
        &[]
    ).unwrap();
}

/// Prometheus metrics server
pub struct MetricsServer {
    port: u16,
}

impl MetricsServer {
    pub fn new(port: u16) -> Self {
        Self { port }
    }

    pub async fn run(&self) -> RelayerResult<()> {
        let app = Router::new().route("/metrics", get(metrics_handler));

        let addr = SocketAddr::from(([0, 0, 0, 0], self.port));
        info!("Starting metrics server on {}", addr);

        let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
        axum::serve(listener, app).await.unwrap();

        Ok(())
    }
}

async fn metrics_handler() -> String {
    let encoder = TextEncoder::new();
    let metric_families = prometheus::gather();
    let mut buffer = Vec::new();
    encoder.encode(&metric_families, &mut buffer).unwrap();
    String::from_utf8(buffer).unwrap()
}

// Helper functions to record metrics

pub fn record_chain_health(chain_id: u64, healthy: bool) {
    CHAIN_CONNECTED
        .with_label_values(&[&chain_id.to_string()])
        .set(if healthy { 1.0 } else { 0.0 });
}

pub fn record_blocks_processed(chain_id: u64, block_number: u64) {
    CHAIN_BLOCK_HEIGHT
        .with_label_values(&[&chain_id.to_string()])
        .set(block_number as f64);
}

pub fn record_event(chain_id: u64, event: &ContractEvent) {
    EVENTS_RECEIVED
        .with_label_values(&[&chain_id.to_string(), event.name()])
        .inc();
}

pub fn record_transaction_buffered(chain_id: u64) {
    TX_BUFFERED
        .with_label_values(&[&chain_id.to_string()])
        .inc();
}

pub fn record_tx_submitted(chain_id: u64) {
    TX_SUBMITTED
        .with_label_values(&[&chain_id.to_string()])
        .inc();
}

pub fn record_tx_finalized(chain_id: u64) {
    TX_FINALIZED
        .with_label_values(&[&chain_id.to_string()])
        .inc();
}

pub fn record_tx_failed(chain_id: u64) {
    TX_FAILED
        .with_label_values(&[&chain_id.to_string()])
        .inc();
}

pub fn record_tx_latency(chain_id: u64, latency_secs: f64) {
    TX_LATENCY
        .with_label_values(&[&chain_id.to_string()])
        .observe(latency_secs);
}

pub fn record_swap_fill(chain_id: u64) {
    SWAP_FILLS
        .with_label_values(&[&chain_id.to_string()])
        .inc();
}

pub fn record_contract_paused(chain_id: u64) {
    CONTRACT_PAUSED
        .with_label_values(&[&chain_id.to_string()])
        .set(1.0);
}

pub fn record_contract_unpaused(chain_id: u64) {
    CONTRACT_PAUSED
        .with_label_values(&[&chain_id.to_string()])
        .set(0.0);
}

pub fn record_circuit_breaker(chain_id: u64) {
    CIRCUIT_BREAKER
        .with_label_values(&[&chain_id.to_string()])
        .inc();
}

pub fn record_wallet_balance(chain_id: u64, balance_eth: f64) {
    WALLET_BALANCE
        .with_label_values(&[&chain_id.to_string()])
        .set(balance_eth);
}

pub fn record_health_check() {
    HEALTH_CHECK_SUCCESS.with_label_values(&[]).inc();
}

pub fn record_health_check_failure() {
    HEALTH_CHECK_FAILURE.with_label_values(&[]).inc();
}
