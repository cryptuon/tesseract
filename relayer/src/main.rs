//! Tesseract Relayer - Multi-chain cross-rollup atomic swap coordination
//!
//! This relayer monitors TesseractBuffer contracts across multiple chains and
//! coordinates atomic transaction execution for cross-chain swaps.

use anyhow::Result;
use std::sync::Arc;
use tokio::signal;
use tracing::{error, info, warn};

mod api;
mod chain;
mod config;
mod coordination;
mod error;
mod events;
mod metrics;
mod state;
mod tx;

use chain::ChainManager;
use config::Settings;
use coordination::CoordinationEngine;
use metrics::MetricsServer;
use state::StateManager;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    init_logging();

    info!("Starting Tesseract Relayer v{}", env!("CARGO_PKG_VERSION"));

    // Load configuration
    let settings = Settings::load()?;
    info!(
        "Loaded configuration for {} chains",
        settings.enabled_chains().len()
    );

    // Initialize database connection
    let state_manager = Arc::new(StateManager::new(&settings.database).await?);
    info!("Database connection established");

    // Run migrations
    state_manager.run_migrations().await?;
    info!("Database migrations complete");

    // Initialize metrics server
    let metrics_server = if settings.metrics.enabled {
        let server = MetricsServer::new(settings.metrics.port);
        Some(server)
    } else {
        None
    };

    // Initialize chain manager (handles all chain connections)
    let chain_manager = Arc::new(ChainManager::new(&settings, state_manager.clone()).await?);
    info!("Chain connections initialized");

    // Initialize coordination engine
    let coordination_engine = Arc::new(
        CoordinationEngine::new(
            chain_manager.clone(),
            state_manager.clone(),
            settings.relayer.clone(),
        )
        .await?,
    );
    info!("Coordination engine initialized");

    // Start API server
    let api_handle = tokio::spawn({
        let settings = settings.clone();
        let state_manager = state_manager.clone();
        let chain_manager = chain_manager.clone();
        async move {
            if let Err(e) = api::run_server(settings.api, state_manager, chain_manager).await {
                error!("API server error: {}", e);
            }
        }
    });

    // Start metrics server
    let metrics_handle = if let Some(server) = metrics_server {
        Some(tokio::spawn(async move {
            if let Err(e) = server.run().await {
                error!("Metrics server error: {}", e);
            }
        }))
    } else {
        None
    };

    // Start chain listeners
    let listener_handle = tokio::spawn({
        let chain_manager = chain_manager.clone();
        async move {
            if let Err(e) = chain_manager.start_listeners().await {
                error!("Chain listener error: {}", e);
            }
        }
    });

    // Start coordination engine
    let coordination_handle = tokio::spawn({
        let engine = coordination_engine.clone();
        async move {
            if let Err(e) = engine.run().await {
                error!("Coordination engine error: {}", e);
            }
        }
    });

    // Health check loop
    let health_handle = tokio::spawn({
        let chain_manager = chain_manager.clone();
        let state_manager = state_manager.clone();
        let interval = settings.relayer.health_check_interval_secs;
        async move {
            loop {
                tokio::time::sleep(tokio::time::Duration::from_secs(interval)).await;

                // Check chain connections
                let health = chain_manager.health_check().await;
                for (chain_id, healthy) in health {
                    if !healthy {
                        warn!("Chain {} health check failed", chain_id);
                    }
                }

                // Check database connection
                if let Err(e) = state_manager.health_check().await {
                    warn!("Database health check failed: {}", e);
                }

                metrics::record_health_check();
            }
        }
    });

    info!("Tesseract Relayer is running");
    info!("API server: http://{}:{}", settings.api.host, settings.api.port);
    if settings.metrics.enabled {
        info!("Metrics: http://0.0.0.0:{}/metrics", settings.metrics.port);
    }

    // Wait for shutdown signal
    shutdown_signal().await;

    info!("Shutdown signal received, stopping...");

    // Graceful shutdown
    coordination_engine.stop().await;
    chain_manager.stop().await;

    // Abort background tasks
    api_handle.abort();
    listener_handle.abort();
    coordination_handle.abort();
    health_handle.abort();
    if let Some(h) = metrics_handle {
        h.abort();
    }

    info!("Tesseract Relayer stopped");
    Ok(())
}

fn init_logging() {
    use tracing_subscriber::{fmt, prelude::*, EnvFilter};

    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| {
        EnvFilter::new("info,tesseract_relayer=debug,sqlx=warn,hyper=warn")
    });

    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer().with_target(true).with_thread_ids(true))
        .init();
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}
