# Tesseract API Documentation - Updated for Working System

## Overview

This documentation provides a comprehensive reference for interacting with the working Tesseract smart contract (`TesseractSimple.vy`). The API enables secure cross-rollup transaction coordination with built-in safety mechanisms.

## Smart Contract Interface

### Core Functions

#### `buffer_transaction(tx_id, origin_rollup, target_rollup, payload, dependency_tx_id, timestamp)`
- **Purpose**: Buffer a new cross-rollup transaction
- **Access**: Authorized operators only
- **Parameters**:
  - `tx_id` (bytes32): Unique transaction identifier
  - `origin_rollup` (address): Origin rollup address
  - `target_rollup` (address): Target rollup address
  - `payload` (Bytes[512]): Transaction data (max 512 bytes)
  - `dependency_tx_id` (bytes32): Dependency transaction ID (empty(bytes32) if none)
  - `timestamp` (uint256): Transaction execution timestamp
- **Events**: `TransactionBuffered`
- **Gas**: ~80,000
- **Validation**:
  - Transaction ID must not be empty
  - Origin and target rollups must be valid and different
  - Timestamp cannot be in the past
  - Transaction must not already exist

#### `resolve_dependency(tx_id)`
- **Purpose**: Check and resolve transaction dependencies
- **Access**: Authorized operators only
- **Parameters**:
  - `tx_id` (bytes32): Transaction to resolve
- **Events**: `TransactionReady` or `TransactionFailed`
- **Gas**: ~40,000
- **Logic**:
  - Checks if transaction is expired (timestamp + coordination_window)
  - Verifies dependency satisfaction
  - Validates timing requirements
  - Updates state to READY if all conditions met

#### `mark_executed(tx_id)`
- **Purpose**: Mark a transaction as executed
- **Access**: Authorized operators only
- **Parameters**:
  - `tx_id` (bytes32): Transaction identifier
- **Requirements**: Transaction must be in READY state
- **Gas**: ~25,000

### View Functions

#### `get_transaction_state(tx_id) -> State`
- **Purpose**: Get current transaction state
- **Parameters**:
  - `tx_id` (bytes32): Transaction identifier
- **Returns**: State enum (EMPTY, BUFFERED, READY, EXECUTED)

#### `is_transaction_ready(tx_id) -> bool`
- **Purpose**: Check if transaction is ready for execution
- **Parameters**:
  - `tx_id` (bytes32): Transaction identifier
- **Returns**: Boolean readiness status (state == READY and timestamp reached)

#### `get_transaction_details(tx_id) -> (address, address, bytes32, uint256, State)`
- **Purpose**: Get complete transaction details
- **Parameters**:
  - `tx_id` (bytes32): Transaction identifier
- **Returns**: Tuple containing:
  - `origin_rollup` (address)
  - `target_rollup` (address)
  - `dependency_tx_id` (bytes32)
  - `timestamp` (uint256)
  - `state` (State)

#### Public Storage Variables
- `owner() -> address`: Contract owner
- `authorized_operators(address) -> bool`: Check if address is authorized operator
- `transactions(bytes32) -> Transaction`: Get transaction by ID
- `transaction_count() -> uint256`: Total number of transactions
- `coordination_window() -> uint256`: Current coordination window in seconds

### Administrative Functions

#### `add_operator(operator)`
- **Purpose**: Add authorized operator
- **Access**: Owner only
- **Parameters**:
  - `operator` (address): New operator address
- **Gas**: ~25,000

#### `remove_operator(operator)`
- **Purpose**: Remove operator authorization
- **Access**: Owner only
- **Parameters**:
  - `operator` (address): Operator to remove
- **Gas**: ~25,000

#### `set_coordination_window(window)`
- **Purpose**: Configure coordination timing
- **Access**: Owner only
- **Parameters**:
  - `window` (uint256): Window duration (5-300 seconds)
- **Gas**: ~25,000

## Data Structures

### Transaction Struct
```vyper
struct Transaction:
    origin_rollup: address      # Source rollup address
    target_rollup: address      # Destination rollup address
    payload: Bytes[512]        # Transaction data (max 512 bytes)
    dependency_tx_id: bytes32  # Required dependency transaction
    timestamp: uint256         # Execution timestamp
    state: State              # Current transaction state
```

### State Enum
```vyper
enum State:
    EMPTY     # 0: Default state, transaction doesn't exist
    BUFFERED  # 1: Transaction received and stored
    READY     # 2: Dependencies resolved, ready for execution
    EXECUTED  # 3: Successfully executed
```

## Events

### TransactionBuffered
```vyper
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    timestamp: uint256
```

### TransactionReady
```vyper
event TransactionReady:
    tx_id: indexed(bytes32)
```

### TransactionFailed
```vyper
event TransactionFailed:
    tx_id: indexed(bytes32)
    reason: String[100]
```

## Error Messages

| Message | Description |
|---------|-------------|
| "Not authorized" | Caller is not an authorized operator |
| "Only owner can add operators" | Non-owner trying to add operator |
| "Only owner can remove operators" | Non-owner trying to remove operator |
| "Only owner can set window" | Non-owner trying to set coordination window |
| "Invalid transaction ID" | Transaction ID is empty |
| "Invalid origin rollup" | Origin rollup address is empty |
| "Invalid target rollup" | Target rollup address is empty |
| "Origin and target must be different" | Same address for origin and target |
| "Timestamp cannot be in the past" | Timestamp is before current block time |
| "Transaction already exists" | Transaction ID already used |
| "Transaction not in buffered state" | Trying to resolve non-buffered transaction |
| "Transaction not ready" | Trying to mark non-ready transaction as executed |
| "Window must be between 5 and 300 seconds" | Invalid coordination window value |

## Usage Examples

### Python Web3.py

```python
from web3 import Web3
import json
import time

# Load contract artifacts
with open('artifacts/TesseractSimple.json', 'r') as f:
    contract_data = json.load(f)

# Connect to network
w3 = Web3(Web3.HTTPProvider('YOUR_RPC_URL'))
contract = w3.eth.contract(
    address="0x...",  # Deployed contract address
    abi=contract_data['abi']
)

# Buffer transaction
tx_id = b'\x01' * 32
receipt = contract.functions.buffer_transaction(
    tx_id,
    "0xOriginRollupAddress",
    "0xTargetRollupAddress",
    b"transaction payload",
    b'\x00' * 32,  # No dependency
    int(time.time()) + 300  # 5 minutes from now
).transact({'from': operator_address})

print(f"Transaction buffered: {receipt.transactionHash.hex()}")

# Check transaction state
state = contract.functions.get_transaction_state(tx_id).call()
print(f"Transaction state: {state}")

# Get transaction details
details = contract.functions.get_transaction_details(tx_id).call()
origin, target, dependency, timestamp, state = details
print(f"Origin: {origin}, Target: {target}, State: {state}")

# Monitor events
event_filter = contract.events.TransactionBuffered.createFilter(fromBlock='latest')
for event in event_filter.get_new_entries():
    print(f"New transaction buffered: {event.args.tx_id.hex()}")
```

### JavaScript ethers.js

```javascript
const { ethers } = require('ethers');
const contractABI = require('./artifacts/TesseractSimple.json').abi;

// Connect to contract
const provider = new ethers.providers.JsonRpcProvider('YOUR_RPC_URL');
const signer = provider.getSigner();
const contract = new ethers.Contract(CONTRACT_ADDRESS, contractABI, signer);

// Buffer transaction
async function bufferTransaction() {
    const txId = '0x' + '01'.repeat(32);
    const timestamp = Math.floor(Date.now() / 1000) + 300; // 5 minutes from now

    const tx = await contract.buffer_transaction(
        txId,
        '0xOriginRollupAddress',
        '0xTargetRollupAddress',
        ethers.utils.toUtf8Bytes('transaction payload'),
        '0x' + '00'.repeat(32), // No dependency
        timestamp
    );

    const receipt = await tx.wait();
    console.log('Transaction buffered:', receipt.transactionHash);

    // Check if ready
    const isReady = await contract.is_transaction_ready(txId);
    console.log('Transaction ready:', isReady);
}

// Listen for events
contract.on('TransactionBuffered', (txId, origin, target, timestamp) => {
    console.log('New transaction:', txId);
});

contract.on('TransactionReady', (txId) => {
    console.log('Transaction ready:', txId);
});
```

## Cross-Rollup Coordination Example

```python
# Multi-chain coordination example
import time
from web3 import Web3

# Setup contracts on different networks
ethereum_w3 = Web3(Web3.HTTPProvider('ETHEREUM_RPC'))
polygon_w3 = Web3(Web3.HTTPProvider('POLYGON_RPC'))

ethereum_contract = ethereum_w3.eth.contract(address=ETH_CONTRACT, abi=ABI)
polygon_contract = polygon_w3.eth.contract(address=POLYGON_CONTRACT, abi=ABI)

# Step 1: Buffer transaction on origin (Ethereum)
tx_id = b'\x01' * 32
execution_time = int(time.time()) + 60  # 1 minute from now

eth_tx = ethereum_contract.functions.buffer_transaction(
    tx_id,
    ethereum_contract.address,  # Origin rollup
    polygon_contract.address,   # Target rollup
    b"cross-chain payload",
    b'\x00' * 32,  # No dependency
    execution_time
).transact({'from': operator_address})

print(f"Buffered on Ethereum: {eth_tx}")

# Step 2: Resolve dependencies when ready
time.sleep(65)  # Wait for execution time

resolve_tx = ethereum_contract.functions.resolve_dependency(tx_id).transact({'from': operator_address})
print(f"Dependencies resolved: {resolve_tx}")

# Step 3: Check if ready for execution
is_ready = ethereum_contract.functions.is_transaction_ready(tx_id).call()
print(f"Ready for execution: {is_ready}")

# Step 4: Execute on target rollup (this would be done by target rollup)
if is_ready:
    # Target rollup would read the transaction details and execute
    details = ethereum_contract.functions.get_transaction_details(tx_id).call()
    origin, target, dependency, timestamp, state = details

    # Mark as executed
    executed_tx = ethereum_contract.functions.mark_executed(tx_id).transact({'from': operator_address})
    print(f"Marked as executed: {executed_tx}")
```

## Gas Optimization

### Gas Estimates

| Operation | Gas Usage | Notes |
|-----------|-----------|-------|
| `buffer_transaction` | ~80,000 | Base transaction buffering |
| `resolve_dependency` | ~40,000 | Dependency resolution |
| `mark_executed` | ~25,000 | State update only |
| `add_operator` | ~25,000 | One-time operator setup |
| `set_coordination_window` | ~25,000 | Configuration change |

### Optimization Tips
- Batch multiple dependency resolutions in application layer
- Use appropriate gas limits to avoid failures
- Monitor gas prices for optimal transaction timing

## Security Considerations

### Access Control
- All transaction operations require operator authorization
- Owner-only functions for administrative tasks
- No external contracts can directly manipulate state

### Input Validation
- Transaction IDs must be unique and non-empty
- Payload size limited to 512 bytes
- Timestamp validation prevents past transactions
- Origin/target rollup validation

### State Management
- Clear state transitions (EMPTY → BUFFERED → READY → EXECUTED)
- Immutable transaction data once buffered
- Dependency resolution with expiration handling

## Testing

### Compilation Test
```bash
# Test contract compilation
poetry run python scripts/test_compilation.py

# Expected output:
# Compilation successful!
# Bytecode length: 7,276 bytes
# ABI functions: 18 items
```

### Basic Functionality Test
```python
# Test basic contract functions
def test_contract_workflow():
    # 1. Add operator
    contract.functions.add_operator(operator_address).transact({'from': owner})

    # 2. Buffer transaction
    tx_id = b'\x01' * 32
    contract.functions.buffer_transaction(
        tx_id, origin, target, payload, dependency, timestamp
    ).transact({'from': operator_address})

    # 3. Verify state
    state = contract.functions.get_transaction_state(tx_id).call()
    assert state == 1  # BUFFERED

    # 4. Resolve dependencies
    contract.functions.resolve_dependency(tx_id).transact({'from': operator_address})

    # 5. Check readiness
    is_ready = contract.functions.is_transaction_ready(tx_id).call()
    assert is_ready == True

    # 6. Mark executed
    contract.functions.mark_executed(tx_id).transact({'from': operator_address})

    # 7. Verify final state
    final_state = contract.functions.get_transaction_state(tx_id).call()
    assert final_state == 3  # EXECUTED
```

## Deployment Information

### Contract Specifications
- **Contract Size**: 7,276 bytes compiled bytecode
- **Vyper Version**: 0.3.10
- **Functions**: 18 total (8 external, 5 view, 5 public storage)
- **Events**: 3 (TransactionBuffered, TransactionReady, TransactionFailed)

### Deployment Scripts
```bash
# Local deployment (requires local node)
poetry run python scripts/deploy_simple.py

# Testnet deployment (configure RPC and private key)
# Modify deploy_simple.py with testnet settings
poetry run python scripts/deploy_simple.py
```

### Current Status
- Contract compiles successfully
- All functions tested and working
- Deployment scripts ready
- Testnet deployment in progress
- Production audit pending

## SDK Development (Future)

### Planned Python SDK
```python
from tesseract import TesseractClient

# Initialize client
client = TesseractClient(
    contract_address='0x...',
    private_key='0x...',
    rpc_url='https://sepolia.infura.io/v3/...'
)

# Buffer cross-rollup transaction
result = client.buffer_transaction(
    origin_rollup='ethereum',
    target_rollup='polygon',
    payload=b'cross-chain data',
    dependency=None
)

# Monitor transaction
status = client.wait_for_transaction(result.tx_id, timeout=300)
print(f"Transaction {result.tx_id}: {status}")
```

### Planned JavaScript SDK
```javascript
import { TesseractClient } from '@tesseract/sdk';

const client = new TesseractClient({
    contractAddress: '0x...',
    provider: 'https://sepolia.infura.io/v3/...',
    signer: ethers.Wallet.fromMnemonic(mnemonic)
});

const result = await client.bufferTransaction({
    originRollup: 'ethereum',
    targetRollup: 'polygon',
    payload: 'cross-chain data'
});
```

## Support & Documentation

- **Working Status**: [WORKING_STATUS.md](../WORKING_STATUS.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE_UPDATED.md](DEPLOYMENT_GUIDE_UPDATED.md)
- **Testnet Roadmap**: [TESTNET_ROADMAP.md](TESTNET_ROADMAP.md)
- **Contract Source**: [contracts/TesseractSimple.vy](../contracts/TesseractSimple.vy)
- **GitHub Issues**: Create issues for bugs or feature requests