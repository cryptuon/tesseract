# Tesseract Relayer

High-performance Rust relayer for cross-chain coordination of atomic swaps.

## Features

- **Multi-Chain Monitoring**: WebSocket primary with HTTP fallback
- **Finality Tracking**: Chain-specific confirmation requirements
- **Transaction Management**: Nonce handling, retry logic, stuck TX recovery
- **State Persistence**: PostgreSQL for crash recovery
- **Metrics Export**: Prometheus metrics on port 9090

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Tesseract Relayer                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Chain     │    │   Chain     │    │   Chain     │      │
│  │  Listener   │    │  Listener   │    │  Listener   │      │
│  │ (Ethereum)  │    │ (Polygon)   │    │ (Arbitrum)  │      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│                 ┌──────────▼──────────┐                     │
│                 │   Coordination      │                     │
│                 │      Engine         │                     │
│                 └──────────┬──────────┘                     │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐              │
│         │                  │                  │              │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐      │
│  │     TX      │    │    State    │    │   Metrics   │      │
│  │   Sender    │    │   Manager   │    │  (Prom)     │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Rust 1.75+
- PostgreSQL 14+
- RPC endpoints for target chains

### Build

```bash
cd relayer
cargo build --release
```

### Configure

Create `config/production.toml`:

```toml
[database]
url = "postgres://user:pass@localhost/tesseract"

[chains.ethereum]
chain_id = 1
rpc_urls = ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"]
ws_url = "wss://eth.llamarpc.com"
contract_address = "0x..."
coordinator_address = "0x..."
confirmation_blocks = 32

[chains.polygon]
chain_id = 137
rpc_urls = ["https://polygon.llamarpc.com"]
ws_url = "wss://polygon.llamarpc.com"
contract_address = "0x..."
coordinator_address = "0x..."
confirmation_blocks = 128

[chains.arbitrum]
chain_id = 42161
rpc_urls = ["https://arb1.arbitrum.io/rpc"]
contract_address = "0x..."
coordinator_address = "0x..."
confirmation_blocks = 0  # Instant finality

[relayer]
max_retries = 3
retry_delay_ms = 1000
health_check_interval_secs = 30
```

### Run

```bash
# Set environment variables
export RELAYER_PRIVATE_KEY="0x..."
export DATABASE_URL="postgres://..."

# Run relayer
cargo run --release

# Or with logging
RUST_LOG=info,tesseract_relayer=debug cargo run --release
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `RELAYER_PRIVATE_KEY` | Hex-encoded private key | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `TESSERACT_CONFIG` | Path to config file | No (default: `config/default.toml`) |
| `RUST_LOG` | Logging level | No |

### Chain Configuration

Each chain requires:

| Field | Description |
|-------|-------------|
| `chain_id` | Network chain ID |
| `rpc_urls` | List of RPC endpoints (failover order) |
| `ws_url` | WebSocket URL for event streaming |
| `contract_address` | TesseractBuffer contract address |
| `coordinator_address` | AtomicSwapCoordinator address |
| `confirmation_blocks` | Blocks to wait for finality |
| `max_gas_price_gwei` | Maximum gas price cap |

## Components

### Chain Listener (`src/chain/listener.rs`)

Monitors chains for events:
- `TransactionBuffered`: New transaction buffered
- `TransactionReady`: Transaction ready for execution
- `TransactionResolved`: Dependency resolved
- `SwapOrderCreated`: New swap order

Uses WebSocket for real-time events with HTTP polling fallback.

### Chain Provider (`src/chain/provider.rs`)

Multi-RPC management with automatic failover:
- Round-robin provider selection
- Automatic failover on errors
- Health check integration
- EIP-1559 gas estimation

### Coordination Engine (`src/coordination/engine.rs`)

Cross-chain coordination logic:
- Monitors origin chains for `TransactionReady` events
- Tracks dependency graph across chains
- Submits `resolve_dependency` on target chains
- Handles swap group atomicity

### Transaction Sender (`src/tx/sender.rs`)

Transaction submission with reliability:
- EIP-1559 gas estimation
- Nonce management with gap handling
- Retry with exponential backoff
- Stuck transaction speed-up

### State Manager (`src/state/manager.rs`)

PostgreSQL state persistence:
- Transaction tracking across restarts
- Nonce persistence
- Submission history

## Database Schema

```sql
CREATE TABLE cross_rollup_transactions (
    tx_id BYTEA PRIMARY KEY,
    origin_chain_id BIGINT NOT NULL,
    target_chain_id BIGINT NOT NULL,
    state VARCHAR(20) NOT NULL,
    dependency_tx_id BYTEA,
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pending_submissions (
    id BIGSERIAL PRIMARY KEY,
    tx_id BYTEA NOT NULL,
    chain_id BIGINT NOT NULL,
    nonce BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    ethereum_tx_hash VARCHAR(66),
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE relayer_nonces (
    chain_id BIGINT PRIMARY KEY,
    current_nonce BIGINT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Run migrations:
```bash
cd relayer
sqlx migrate run
```

## Metrics

Prometheus metrics exposed on `:9090/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `tesseract_chain_connected` | Gauge | Chain connection status (0/1) |
| `tesseract_events_received_total` | Counter | Events by type and chain |
| `tesseract_transactions_submitted_total` | Counter | Submissions by result |
| `tesseract_transaction_latency_seconds` | Histogram | End-to-end latency |
| `tesseract_wallet_balance_eth` | Gauge | Wallet balance per chain |
| `tesseract_block_sync_lag` | Gauge | Blocks behind head |

## Monitoring

### Prometheus

```yaml
scrape_configs:
  - job_name: 'tesseract-relayer'
    static_configs:
      - targets: ['relayer:9090']
```

### Grafana

Import dashboard from `monitoring/grafana/provisioning/dashboards/tesseract-overview.json`

### Alerts

See `monitoring/alerting_rules.yml` for critical alerts:
- Chain disconnected
- Low wallet balance
- High failure rate
- Block sync lag

## Development

### Run Tests

```bash
cargo test
```

### Check Compilation

```bash
cargo check
cargo clippy
```

### Format Code

```bash
cargo fmt
```

## Deployment

### Docker

```dockerfile
FROM rust:1.75 AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/tesseract-relayer /usr/local/bin/
CMD ["tesseract-relayer"]
```

### AWS ECS

See `infrastructure/terraform/` for ECS Fargate deployment with:
- Auto-scaling (2-10 instances)
- ALB health checks
- CloudWatch logging
- Secrets Manager integration

## Troubleshooting

### Connection Issues

```bash
# Check RPC connectivity
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  YOUR_RPC_URL
```

### Nonce Issues

```bash
# Reset nonce in database
psql $DATABASE_URL -c "DELETE FROM relayer_nonces WHERE chain_id = 1;"
```

### Stuck Transactions

The relayer automatically detects and speeds up stuck transactions by:
1. Monitoring pending transactions
2. Resubmitting with 25% higher gas after timeout
3. Tracking replacement transactions

## License

MIT License - see [LICENSE](../LICENSE)
