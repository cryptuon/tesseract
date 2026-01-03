# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tesseract is a cross-rollup atomic transaction execution system that enables coordinated transaction processing across multiple Layer 2 rollups. The system uses Vyper smart contracts for security and implements dependency resolution with time-bounded coordination windows.

### Core Architecture

The system follows a buffer-resolve-execute pattern:
1. **Transaction Buffering**: Cross-rollup transactions are buffered in the main contract with dependency information
2. **Dependency Resolution**: A separate resolution phase validates dependencies and timing constraints
3. **Atomic Execution**: Transactions are marked as ready for execution across multiple rollups

**Key Components:**
- `contracts/TesseractBuffer.vy`: Production contract with pause, circuit breaker, rate limiting
- `contracts/TesseractSimple.vy`: Simplified coordination contract
- Transaction states: EMPTY → BUFFERED → READY → EXECUTED (also FAILED, EXPIRED)
- Role-based access control (BUFFER_ROLE, RESOLVE_ROLE, ADMIN_ROLE)
- Time-bounded coordination windows (default 30 seconds)

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv
uv sync

# Install with dev dependencies
uv sync --all-extras
```

### Contract Development
```bash
# Run comprehensive test suite
uv run pytest tests/

# Run single test file
uv run pytest tests/test_compilation.py -v

# Run with coverage
uv run pytest --cov=tesseract tests/
```

### Deployment
```bash
# Validate environment before deployment
uv run python scripts/setup_environment.py local

# Deploy to local network (requires local blockchain node)
uv run python scripts/deploy_simple.py local

# Deploy to testnet
uv run python scripts/deploy_simple.py sepolia
```

### Operational Scripts
```bash
# Health check
uv run python scripts/health_check.py sepolia

# Monitor events
uv run python scripts/monitor_events.py sepolia --watch

# Manage operators
uv run python scripts/manage_operators.py sepolia add 0x...

# Emergency procedures
uv run python scripts/emergency.py sepolia status
```

### Code Quality
```bash
# Format Python code
uv run black .
```

## Contract Architecture

### State Management
The contract uses a simple state machine for transactions:
- Each transaction has a unique `bytes32` ID
- States progress: EMPTY → BUFFERED → READY → EXECUTED
- Dependencies are resolved by checking if dependency transactions are READY or EXECUTED

### Access Control Pattern
- `owner`: Can grant/revoke roles, configure settings, transfer ownership
- `BUFFER_ROLE`: Can buffer transactions
- `RESOLVE_ROLE`: Can resolve dependencies and mark transactions
- `ADMIN_ROLE`: Administrative functions
- `emergency_admin`: Can pause contract (but not unpause)

### Safety Mechanisms
- **Emergency Pause**: Stop all operations immediately
- **Circuit Breaker**: Auto-triggers after threshold failures (default 50)
- **Rate Limiting**: Per-block transaction limits

### Gas Optimization
- Transaction payload limited to 512 bytes for gas efficiency
- Minimal storage with efficient packing
- Events are indexed for efficient filtering

## Testing Strategy

### Test Suite (100 tests)
- `tests/test_compilation.py` - Contract compilation tests
- `tests/test_access_control.py` - Role-based access control
- `tests/test_transactions.py` - Transaction lifecycle
- `tests/test_validation.py` - Input validation
- `tests/test_safety.py` - Safety mechanisms
- `tests/test_integration.py` - End-to-end tests

### Known Issue: py-evm Compatibility
Some tests are marked `xfail` due to a py-evm 0.10.x bug with Vyper enum comparisons. These tests pass on real networks (testnets/mainnet).

## Key Files and Scripts

### Core Scripts
- `scripts/deploy_simple.py`: Multi-network deployment
- `scripts/setup_environment.py`: Environment validation
- `scripts/verify_deployment.py`: Post-deployment checks
- `scripts/health_check.py`: Health monitoring
- `scripts/monitor_events.py`: Event monitoring
- `scripts/manage_operators.py`: Operator management
- `scripts/emergency.py`: Emergency procedures

### Configuration
- `config/networks.json`: Network configurations (Sepolia, Mumbai, etc.)

### Documentation
- `docs/DEPLOYMENT_GUIDE_UPDATED.md`: Deployment instructions
- `docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md`: Production readiness checklist

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

The system is designed for deployment across:
- Ethereum (Mainnet/Sepolia)
- Polygon (Mainnet/Mumbai)
- Arbitrum (One/Goerli)
- Optimism (Mainnet/Goerli)

Each deployment uses identical contract code but separate operator configurations per network.

## Security Model

### Input Validation
- All transaction IDs must be non-empty `bytes32`
- Origin and target rollups must be different addresses
- Timestamps cannot be in the past
- Coordination window must be between 5-300 seconds

### State Protection
- Transaction data is immutable once buffered
- Only operators can modify transaction states
- Emergency controls available through owner/emergency_admin
- No external contract calls to prevent reentrancy

## Current Status

The system has a working TesseractBuffer.vy contract that:
- Compiles successfully with Vyper 0.3.10
- Has comprehensive test suite (100 tests)
- Includes emergency pause and circuit breaker
- Has role-based access control
- Ready for testnet deployment

Next steps: Configure testnet environment and deploy to Sepolia.
