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
- `contracts/TesseractSimple.vy`: Main coordination contract (7,276 bytes compiled)
- Transaction states: EMPTY → BUFFERED → READY → EXECUTED
- Role-based access control with owner and authorized operators
- Time-bounded coordination windows (default 30 seconds)

## Development Commands

### Environment Setup
```bash
# Install dependencies
poetry install

# Activate Poetry shell
poetry shell
```

### Contract Development
```bash
# Test contract compilation (primary validation)
poetry run python scripts/test_compilation.py

# Run comprehensive test suite
poetry run pytest tests/

# Run single test file
poetry run pytest tests/test_compilation.py -v

# Test basic contract functionality
poetry run python scripts/test_basic.py
```

### Deployment
```bash
# Deploy to local network (requires local blockchain node)
poetry run python scripts/deploy_simple.py

# Deploy to multiple chains
poetry run python scripts/deploy_multichain.py
```

### Code Quality
```bash
# Format Python code
poetry run black .

# Run test coverage
poetry run pytest --cov=tesseract tests/
```

## Contract Architecture

### State Management
The contract uses a simple state machine for transactions:
- Each transaction has a unique `bytes32` ID
- States progress linearly: EMPTY → BUFFERED → READY → EXECUTED
- Dependencies are resolved by checking if dependency transactions are READY or EXECUTED

### Access Control Pattern
- `owner`: Can add/remove operators and configure coordination window
- `authorized_operators`: Can buffer, resolve, and mark transactions executed
- All state-changing functions use `assert` statements for access control

### Gas Optimization
- Transaction payload limited to 512 bytes for gas efficiency
- Minimal storage with efficient packing
- Events are indexed for efficient filtering

## Testing Strategy

### Compilation Tests (`tests/test_compilation.py`)
- Verifies contract compiles successfully with Vyper 0.3.10
- Validates ABI contains expected functions and events
- Should always pass before making changes

### Integration Testing Pattern
When adding new functionality:
1. Test contract compilation first
2. Test individual functions in isolation
3. Test complete transaction lifecycle (buffer → resolve → execute)
4. Test access control and error conditions

## Key Files and Scripts

### Core Scripts
- `scripts/test_compilation.py`: Primary validation script for contract compilation
- `scripts/deploy_simple.py`: Production-ready deployment script with gas estimation
- `scripts/test_basic.py`: Integration testing for contract functionality

### Documentation Structure
- `docs/API_DOCUMENTATION_UPDATED.md`: Current API reference for TesseractSimple.vy
- `docs/DEPLOYMENT_GUIDE_UPDATED.md`: Current deployment instructions
- `docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md`: Comprehensive production readiness checklist

## Vyper-Specific Considerations

### Language Constraints
- Use lowercase `bytes[n]` not `Bytes[n]` for byte arrays
- Avoid reserved keywords like `tx` (use `transaction` instead)
- All external functions require explicit access control assertions
- No inheritance or complex OOP patterns

### Common Patterns
```vyper
# Access control pattern
assert self.authorized_operators[msg.sender], "Not authorized"

# State validation pattern
assert transaction.state == State.BUFFERED, "Transaction not in buffered state"

# Time-based validation
assert block.timestamp >= transaction.timestamp, "Transaction not ready"
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
- Emergency controls available through owner functions
- No external contract calls to prevent reentrancy

## Current Status

The system has a working TesseractSimple.vy contract that:
- Compiles successfully (verified in CI)
- Implements core cross-rollup coordination logic
- Has basic access control and state management
- Ready for testnet deployment

Next development priorities are testnet deployment and comprehensive integration testing across multiple chains.