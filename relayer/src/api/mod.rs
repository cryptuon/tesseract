//! HTTP API for health checks, status, and monitoring

use crate::chain::ChainManager;
use crate::config::ApiConfig;
use crate::error::RelayerResult;
use crate::state::StateManager;

use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tracing::info;

/// Shared application state
#[derive(Clone)]
pub struct AppState {
    pub state_manager: Arc<StateManager>,
    pub chain_manager: Arc<ChainManager>,
}

/// Run the HTTP API server
pub async fn run_server(
    config: ApiConfig,
    state_manager: Arc<StateManager>,
    chain_manager: Arc<ChainManager>,
) -> RelayerResult<()> {
    let state = AppState {
        state_manager,
        chain_manager,
    };

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/ready", get(readiness_check))
        .route("/status", get(get_status))
        .route("/chains", get(get_chains))
        .route("/stats", get(get_stats))
        .with_state(state);

    let addr = format!("{}:{}", config.host, config.port);
    info!("Starting API server on {}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();

    Ok(())
}

/// Health check endpoint - basic liveness
async fn health_check() -> impl IntoResponse {
    Json(HealthResponse {
        status: "ok".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

/// Readiness check - verify all dependencies
async fn readiness_check(State(state): State<AppState>) -> impl IntoResponse {
    // Check database
    let db_ok = state.state_manager.health_check().await.is_ok();

    // Check chain connections
    let chain_health = state.chain_manager.health_check().await;
    let chains_ok = chain_health.iter().all(|(_, healthy)| *healthy);

    if db_ok && chains_ok {
        (
            StatusCode::OK,
            Json(ReadinessResponse {
                ready: true,
                database: db_ok,
                chains: chains_ok,
                details: chain_health
                    .into_iter()
                    .map(|(id, h)| ChainHealth {
                        chain_id: id,
                        healthy: h,
                    })
                    .collect(),
            }),
        )
    } else {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ReadinessResponse {
                ready: false,
                database: db_ok,
                chains: chains_ok,
                details: chain_health
                    .into_iter()
                    .map(|(id, h)| ChainHealth {
                        chain_id: id,
                        healthy: h,
                    })
                    .collect(),
            }),
        )
    }
}

/// Get relayer status
async fn get_status(State(state): State<AppState>) -> impl IntoResponse {
    let chain_health = state.chain_manager.health_check().await;

    Json(StatusResponse {
        version: env!("CARGO_PKG_VERSION").to_string(),
        uptime_seconds: 0, // Would track actual uptime
        connected_chains: state.chain_manager.connected_chains(),
        chain_status: chain_health
            .into_iter()
            .map(|(id, h)| ChainHealth {
                chain_id: id,
                healthy: h,
            })
            .collect(),
    })
}

/// Get connected chains
async fn get_chains(State(state): State<AppState>) -> impl IntoResponse {
    let chains = state.chain_manager.connected_chains();
    Json(ChainsResponse { chains })
}

/// Get transaction statistics
async fn get_stats(State(state): State<AppState>) -> impl IntoResponse {
    match state.state_manager.get_stats().await {
        Ok(stats) => (
            StatusCode::OK,
            Json(StatsResponse {
                buffered: stats.buffered,
                ready: stats.ready,
                submitted: stats.submitted,
                finalized: stats.finalized,
                failed: stats.failed,
            }),
        ),
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(StatsResponse {
                buffered: 0,
                ready: 0,
                submitted: 0,
                finalized: 0,
                failed: 0,
            }),
        ),
    }
}

// Response types

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    version: String,
}

#[derive(Serialize)]
struct ReadinessResponse {
    ready: bool,
    database: bool,
    chains: bool,
    details: Vec<ChainHealth>,
}

#[derive(Serialize)]
struct ChainHealth {
    chain_id: u64,
    healthy: bool,
}

#[derive(Serialize)]
struct StatusResponse {
    version: String,
    uptime_seconds: u64,
    connected_chains: Vec<u64>,
    chain_status: Vec<ChainHealth>,
}

#[derive(Serialize)]
struct ChainsResponse {
    chains: Vec<u64>,
}

#[derive(Serialize)]
struct StatsResponse {
    buffered: u64,
    ready: u64,
    submitted: u64,
    finalized: u64,
    failed: u64,
}
