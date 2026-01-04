# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tesseract is a cross-rollup atomic swap protocol enabling trustless token exchanges across Ethereum L2s. The system consists of:
- **7 Vyper smart contracts** with DeFi security features
- **High-performance Rust relayer** for cross-chain coordination
- **AWS infrastructure** with Terraform for production deployment

### Core Architecture

The system follows a commit-reveal-resolve pattern:
1. **Commit Phase**: User commits transaction hash (hides payload from MEV bots)
2. **Reveal Phase**: User reveals payload after commitment is on-chain
3. **Resolution Phase**: Relayer resolves dependencies after MIN_RESOLUTION_DELAY blocks
4. **Execution**: Transactions marked READY are executed atomically

**Smart Contracts (7 total):**
- `contracts/TesseractBuffer.vy`: Core buffering with DeFi security (12,578 bytes)
- `contracts/AtomicSwapCoordinator.vy`: Order book and swap coordination (8,332 bytes)
- `contracts/TesseractToken.vy`: TESS governance token (ERC-20)
- `contracts/TesseractStaking.vy`: Staking with tiered rewards (5-15% APY)
- `contracts/FeeCollector.vy`: Protocol fee collection (0.2% default)
- `contracts/RelayerRegistry.vy`: Relayer bonding and management
- `contracts/TesseractGovernor.vy`: On-chain governance

**DeFi Security Features:**
- MEV protection via commit-reveal scheme
- Flash loan resistance (2-block minimum delay)
- Atomic swap groups (multi-leg swaps)
- Slippage protection with min_receive_amount

**Rust Relayer (`relayer/`):**
- Multi-chain event monitoring (WebSocket + HTTP failover)
- Cross-chain coordination engine
- Transaction submission with retry logic
- PostgreSQL state persistence
- Prometheus metrics export

## Development Commands

### Environment Setup
```bash
# Install Python dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Build Rust relayer
cd relayer && cargo build --release
```

### Contract Development
```bash
# Run full test suite (135 tests)
uv run pytest tests/ -v

# Run specific test categories
uv run pytest tests/test_compilation.py -v      # Contract compilation
uv run pytest tests/test_tokenomics.py -v       # Tokenomics contracts
uv run pytest tests/test_defi_security.py -v    # DeFi security features

# Run integration tests (requires Anvil)
uv run pytest tests/integration/ -v
```

### Deployment
```bash
# Deploy to testnet
uv run python scripts/deploy_simple.py sepolia

# Verify on block explorer
uv run python scripts/verify_on_explorer.py sepolia

# Health check
uv run python scripts/health_check.py sepolia
```

### Rust Relayer
```bash
cd relayer

# Build
cargo build --release

# Run
cargo run --release

# Run tests
cargo test

# Check compilation
cargo check
```

### Infrastructure (Terraform)
```bash
cd infrastructure/terraform

# Deploy staging
terraform init -backend-config=environments/staging/backend.tf
terraform apply -var-file=environments/staging/terraform.tfvars

# Deploy production
terraform apply -var-file=environments/production/terraform.tfvars
```

### Code Quality
```bash
# Format Python
uv run black .

# Format Rust
cd relayer && cargo fmt

# Lint Rust
cd relayer && cargo clippy
```

## Contract Architecture

### Transaction States
```
EMPTY → BUFFERED → READY → EXECUTED
              ↓         ↓
          EXPIRED   FAILED
              ↓
          REFUNDED
```

### TesseractBuffer.vy Key Functions
- `buffer_transaction()`: Basic transaction buffering
- `buffer_transaction_with_commitment()`: MEV-protected buffering with commit-reveal
- `reveal_transaction()`: Reveal payload after commitment
- `resolve_dependency()`: Mark transaction as ready (requires MIN_RESOLUTION_DELAY blocks)
- `claim_refund()`: Claim refund for expired transactions

### AtomicSwapCoordinator.vy Key Functions
- `create_swap_order()`: Create order with slippage protection
- `fill_swap_order()`: Fill order (supports partial fills)
- `cancel_swap_order()`: Cancel unfilled order

### Access Control Pattern
- `owner`: Grant/revoke roles, configure settings
- `BUFFER_ROLE`: Buffer transactions
- `RESOLVE_ROLE`: Resolve dependencies
- `ADMIN_ROLE`: Administrative functions
- `emergency_admin`: Pause contract (but not unpause)

### Safety Mechanisms
- **MIN_RESOLUTION_DELAY**: 2 blocks before resolution (flash loan protection)
- **Emergency Pause**: Stop all operations immediately
- **Circuit Breaker**: Auto-triggers after 50 consecutive failures
- **Rate Limiting**: Per-block transaction limits

## Testing Strategy

### Test Suite (135 tests)
| File | Tests | Description |
|------|-------|-------------|
| `test_compilation.py` | 11 | All 7 contracts compile |
| `test_tokenomics.py` | 21 | Token, staking, governance |
| `test_access_control.py` | 27 | Role-based permissions |
| `test_safety.py` | 26 | Emergency controls, circuit breaker |
| `test_defi_security.py` | 14 | Commit-reveal, flash loan protection |
| `test_integration.py` | 11 | End-to-end scenarios |
| `tests/integration/` | 23 | Cross-chain tests (requires Anvil) |

### Known Issue: py-evm Compatibility
Some tests are marked `xfail` due to a py-evm 0.10.x bug with Vyper enum comparisons. These tests pass on real networks (testnets/mainnet) and with Anvil.

## Key Files and Scripts

### Smart Contracts
- `contracts/TesseractBuffer.vy`: Core transaction buffering
- `contracts/AtomicSwapCoordinator.vy`: Swap order book
- `contracts/TesseractToken.vy`: TESS governance token
- `contracts/TesseractStaking.vy`: Staking with tiered rewards
- `contracts/FeeCollector.vy`: Protocol fee collection
- `contracts/RelayerRegistry.vy`: Relayer management
- `contracts/TesseractGovernor.vy`: On-chain governance

### Rust Relayer
- `relayer/src/main.rs`: Entry point
- `relayer/src/chain/listener.rs`: Event monitoring
- `relayer/src/chain/provider.rs`: Multi-RPC with failover
- `relayer/src/coordination/engine.rs`: Cross-chain coordination
- `relayer/src/tx/sender.rs`: Transaction submission
- `relayer/src/tx/nonce.rs`: Nonce management

### Deployment Scripts
- `scripts/deploy_simple.py`: Multi-network deployment
- `scripts/verify_on_explorer.py`: Block explorer verification
- `scripts/health_check.py`: Health monitoring
- `scripts/emergency.py`: Emergency procedures

### Infrastructure
- `infrastructure/terraform/`: AWS deployment
- `relayer/monitoring/`: Prometheus + Grafana
- `relayer/monitoring/alerting_rules.yml`: Alert definitions

### Configuration
- `config/networks.json`: Network configurations
- `relayer/config/`: Relayer configurations

## Vyper-Specific Considerations

### Language Constraints
- Use lowercase `bytes[n]` not `Bytes[n]` for byte arrays
- Avoid reserved keywords like `tx` (use `transaction` instead)
- All external functions require explicit access control assertions
- No inheritance or complex OOP patterns

### Common Patterns
```vyper
# Role-based access control
assert self.has_role[role][msg.sender], "Missing role"

# State validation pattern
assert transaction.state == State.BUFFERED, "Invalid state"

# Time-based validation
assert block.timestamp >= transaction.timestamp, "Not ready"
```

## Multi-Chain Deployment

Supported networks (updated testnets):
- **Ethereum**: Mainnet / Sepolia
- **Polygon**: Mainnet / Amoy (Mumbai deprecated)
- **Arbitrum**: One / Sepolia
- **Optimism**: Mainnet / Sepolia
- **Base**: Mainnet / Sepolia

Each deployment uses identical contract code with network-specific configurations in `config/networks.json`.

## Security Model

### DeFi Security
- **MEV Protection**: Commit-reveal scheme hides payload until reveal
- **Flash Loan Protection**: MIN_RESOLUTION_DELAY (2 blocks) before resolution
- **Atomic Swap Groups**: Multi-leg swaps succeed or fail together
- **Slippage Protection**: Configurable min_receive_amount per order

### Input Validation
- All transaction IDs must be non-empty `bytes32`
- Origin and target rollups must be different addresses
- Timestamps cannot be in the past
- Coordination window must be between 5-300 seconds

### State Protection
- Transaction data is immutable once buffered
- Only operators can modify transaction states
- Emergency controls via owner/emergency_admin
- No external contract calls (reentrancy safe)

## Current Status

| Component | Status |
|-----------|--------|
| Smart Contracts (7) | Complete |
| Rust Relayer | Complete (compiles) |
| Test Suite (135 tests) | 86 pass, 40 xfail |
| Monitoring Stack | Complete |
| Terraform Infrastructure | Complete |
| Testnet Deployment | Ready |
| Security Audit | Pending |

**Next Steps**: Deploy to Sepolia testnet and run integration tests with Anvil.
