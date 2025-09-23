# Tesseract API Documentation

## Overview

This document provides comprehensive API documentation for the Tesseract cross-rollup atomic transaction execution system. The API consists of smart contract functions, events, and a Python SDK for easy integration.

## Smart Contract API

### Contract Address

| Network | Contract Address |
|---------|-----------------|
| Ethereum Sepolia | `0x...` |
| Polygon Mumbai | `0x...` |
| Arbitrum Goerli | `0x...` |
| Optimism Goerli | `0x...` |

### Core Functions

#### buffer_transaction

Buffers a new cross-rollup transaction with its dependencies.

```vyper
@external
def buffer_transaction(
    tx_id: bytes32,
    origin_rollup: address,
    target_rollup: address,
    payload: Bytes[2048],
    dependency_tx_id: bytes32,
    timestamp: uint256
):
```

**Parameters:**
- `tx_id`: Unique identifier for the transaction (must be non-zero)
- `origin_rollup`: Address of the originating rollup
- `target_rollup`: Address of the target rollup
- `payload`: Transaction payload data (max 2048 bytes)
- `dependency_tx_id`: ID of the transaction this depends on (zero for no dependency)
- `timestamp`: Execution timestamp (must be in the future)

**Requirements:**
- Caller must have `BUFFER_ROLE`
- Transaction ID must be unique
- Origin and target rollups must be different
- Timestamp must be in the future but not too far (max 24 hours)

**Events Emitted:**
- `TransactionBuffered(tx_id, origin_rollup, target_rollup, dependency_tx_id, timestamp)`

**Example Usage:**
```python
from web3 import Web3
from hexbytes import HexBytes

# Buffer a transaction
tx_id = HexBytes("0x" + "1" * 64)
receipt = contract.functions.buffer_transaction(
    tx_id,
    "0xOriginRollupAddress",
    "0xTargetRollupAddress",
    b"transaction payload",
    HexBytes("0x" + "0" * 64),  # No dependency
    int(time.time()) + 300  # 5 minutes from now
).transact({'from': operator_address})
```

#### resolve_dependency

Resolves dependencies for a buffered transaction, making it ready for execution.

```vyper
@external
def resolve_dependency(tx_id: bytes32):
```

**Parameters:**
- `tx_id`: ID of the transaction to resolve

**Requirements:**
- Caller must have `RESOLVE_ROLE`
- Transaction must exist and be in BUFFERED state
- Dependencies must be satisfied
- Must be within the coordination time window

**Events Emitted:**
- `TransactionReady(tx_id)` on successful resolution
- `TransactionFailed(tx_id, reason)` on failure

**Example Usage:**
```python
# Resolve transaction dependency
receipt = contract.functions.resolve_dependency(tx_id).transact({
    'from': resolver_address
})

# Check if transaction is now ready
is_ready = contract.functions.is_transaction_ready(tx_id).call()
```

#### is_transaction_ready

Checks if a buffered transaction is ready for execution.

```vyper
@view
@external
def is_transaction_ready(tx_id: bytes32) -> bool:
```

**Parameters:**
- `tx_id`: ID of the transaction to check

**Returns:**
- `bool`: True if transaction is ready for execution

**Example Usage:**
```python
# Check if transaction is ready
ready = contract.functions.is_transaction_ready(tx_id).call()
if ready:
    print("Transaction is ready for execution")
```

### Access Control Functions

#### grant_role

Grants a role to an account.

```vyper
@external
def grant_role(role: bytes32, account: address):
```

**Parameters:**
- `role`: Role identifier (e.g., `BUFFER_ROLE`, `RESOLVE_ROLE`)
- `account`: Address to grant the role to

**Requirements:**
- Caller must be the contract owner

**Example Usage:**
```python
# Grant buffer role to an operator
buffer_role = contract.functions.BUFFER_ROLE().call()
receipt = contract.functions.grant_role(
    buffer_role,
    operator_address
).transact({'from': owner_address})
```

#### revoke_role

Revokes a role from an account.

```vyper
@external
def revoke_role(role: bytes32, account: address):
```

**Parameters:**
- `role`: Role identifier to revoke
- `account`: Address to revoke the role from

**Requirements:**
- Caller must be the contract owner

#### has_role

Checks if an account has a specific role.

```vyper
@view
@external
def has_role(role: bytes32, account: address) -> bool:
```

**Parameters:**
- `role`: Role identifier to check
- `account`: Address to check

**Returns:**
- `bool`: True if account has the role

### Emergency Functions

#### pause

Pauses all contract operations.

```vyper
@external
def pause():
```

**Requirements:**
- Caller must be owner or emergency admin

**Events Emitted:**
- `EmergencyPause(caller, timestamp)`

#### unpause

Unpauses contract operations.

```vyper
@external
def unpause():
```

**Requirements:**
- Caller must be the contract owner

**Events Emitted:**
- `EmergencyUnpause(caller, timestamp)`

### View Functions

#### get_transaction

Returns full transaction details.

```vyper
@view
@external
def get_transaction(tx_id: bytes32) -> BufferedTransaction:
```

**Returns:**
```vyper
struct BufferedTransaction:
    origin_rollup: address
    target_rollup: address
    payload: Bytes[2048]
    dependency_tx_id: bytes32
    timestamp: uint256
    state: TransactionState
    expiry: uint256
    confirmations: uint256
```

#### get_transaction_count

Returns the total number of transactions buffered.

```vyper
@view
@external
def get_transaction_count() -> uint256:
```

## Events

### TransactionBuffered

Emitted when a new transaction is buffered.

```vyper
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    dependency_tx_id: bytes32
    timestamp: uint256
```

### TransactionReady

Emitted when a transaction becomes ready for execution.

```vyper
event TransactionReady:
    tx_id: indexed(bytes32)
    resolved_at: uint256
```

### TransactionFailed

Emitted when transaction resolution fails.

```vyper
event TransactionFailed:
    tx_id: indexed(bytes32)
    reason: String[256]
    failed_at: uint256
```

### EmergencyPause / EmergencyUnpause

Emitted on emergency pause/unpause operations.

```vyper
event EmergencyPause:
    caller: indexed(address)
    paused_at: uint256

event EmergencyUnpause:
    caller: indexed(address)
    unpaused_at: uint256
```

## Python SDK

### Installation

```bash
pip install tesseract-sdk
```

### Basic Usage

```python
from tesseract import TesseractClient
from web3 import Web3

# Initialize client
web3 = Web3(Web3.HTTPProvider("https://sepolia.infura.io/v3/YOUR_KEY"))
client = TesseractClient(
    web3=web3,
    contract_address="0x...",
    private_key="0x..."  # Use environment variables in production
)
```

### TesseractClient Class

#### Constructor

```python
class TesseractClient:
    def __init__(
        self,
        web3: Web3,
        contract_address: str,
        private_key: str = None,
        account_address: str = None
    ):
```

**Parameters:**
- `web3`: Web3 instance connected to the desired network
- `contract_address`: Tesseract contract address
- `private_key`: Private key for transaction signing (optional)
- `account_address`: Account address to use (required if no private_key)

#### Methods

##### buffer_transaction

```python
def buffer_transaction(
    self,
    tx_id: bytes,
    origin_rollup: str,
    target_rollup: str,
    payload: bytes,
    dependency_tx_id: bytes = None,
    timestamp: int = None,
    **kwargs
) -> dict:
```

**Example:**
```python
import time
from hexbytes import HexBytes

receipt = client.buffer_transaction(
    tx_id=HexBytes("0x" + "1" * 64),
    origin_rollup="0xOriginAddress",
    target_rollup="0xTargetAddress",
    payload=b"transaction data",
    timestamp=int(time.time()) + 300
)
print(f"Transaction hash: {receipt['transactionHash'].hex()}")
```

##### resolve_dependency

```python
def resolve_dependency(self, tx_id: bytes, **kwargs) -> dict:
```

**Example:**
```python
receipt = client.resolve_dependency(
    tx_id=HexBytes("0x" + "1" * 64)
)
```

##### is_transaction_ready

```python
def is_transaction_ready(self, tx_id: bytes) -> bool:
```

**Example:**
```python
ready = client.is_transaction_ready(HexBytes("0x" + "1" * 64))
if ready:
    print("Transaction ready for execution")
```

##### get_transaction

```python
def get_transaction(self, tx_id: bytes) -> dict:
```

**Example:**
```python
tx_data = client.get_transaction(HexBytes("0x" + "1" * 64))
print(f"Transaction state: {tx_data['state']}")
```

### Event Monitoring

```python
class EventMonitor:
    def __init__(self, client: TesseractClient):
        self.client = client

    def monitor_buffered_transactions(self, callback=None):
        """Monitor TransactionBuffered events."""
        event_filter = self.client.contract.events.TransactionBuffered.createFilter(
            fromBlock='latest'
        )

        while True:
            for event in event_filter.get_new_entries():
                if callback:
                    callback(event)
                else:
                    print(f"New transaction buffered: {event['args']['tx_id'].hex()}")
            time.sleep(2)

# Usage
monitor = EventMonitor(client)
monitor.monitor_buffered_transactions()
```

### Batch Operations

```python
class BatchOperations:
    def __init__(self, client: TesseractClient):
        self.client = client

    def batch_buffer_transactions(self, transactions: list) -> list:
        """Buffer multiple transactions in batch."""
        receipts = []
        for tx in transactions:
            receipt = self.client.buffer_transaction(**tx)
            receipts.append(receipt)
        return receipts

    def wait_for_transactions_ready(self, tx_ids: list, timeout: int = 300) -> dict:
        """Wait for multiple transactions to become ready."""
        start_time = time.time()
        results = {}

        while time.time() - start_time < timeout:
            for tx_id in tx_ids:
                if tx_id not in results:
                    if self.client.is_transaction_ready(tx_id):
                        results[tx_id] = True

            if len(results) == len(tx_ids):
                break

            time.sleep(5)

        return results
```

## Multi-Chain Integration

### Cross-Chain Transaction Coordination

```python
from tesseract import MultiChainClient

# Initialize clients for multiple networks
clients = {
    'ethereum': TesseractClient(
        web3=Web3(Web3.HTTPProvider("https://sepolia.infura.io/v3/KEY")),
        contract_address="0x...",
        private_key="0x..."
    ),
    'polygon': TesseractClient(
        web3=Web3(Web3.HTTPProvider("https://polygon-mumbai.infura.io/v3/KEY")),
        contract_address="0x...",
        private_key="0x..."
    )
}

multi_client = MultiChainClient(clients)

# Execute cross-chain transaction
result = multi_client.execute_cross_chain_transaction(
    origin_chain='ethereum',
    target_chain='polygon',
    payload=b"cross-chain data"
)
```

### Cross-Chain State Verification

```python
def verify_cross_chain_state(origin_client, target_client, tx_id):
    """Verify transaction state across chains."""
    # Get transaction from origin chain
    origin_tx = origin_client.get_transaction(tx_id)

    # Verify corresponding state on target chain
    target_ready = target_client.is_transaction_ready(tx_id)

    return {
        'origin_state': origin_tx['state'],
        'target_ready': target_ready,
        'synchronized': origin_tx['state'] == 'READY' and target_ready
    }
```

## Error Handling

### Common Error Codes

| Error | Description | Solution |
|-------|-------------|----------|
| `AccessControl: account missing role` | Caller doesn't have required permission | Grant appropriate role to account |
| `Transaction already exists` | Duplicate transaction ID | Use unique transaction ID |
| `Invalid transaction ID` | Zero or invalid transaction ID | Provide valid non-zero ID |
| `Timestamp cannot be in the past` | Invalid timestamp | Use future timestamp |
| `Block transaction limit exceeded` | Too many transactions in block | Wait for next block |
| `Transaction being processed` | Concurrent processing attempt | Wait for current processing to complete |
| `Circuit breaker active` | System in emergency state | Wait for system recovery |

### Error Handling in SDK

```python
from tesseract.exceptions import (
    TesseractException,
    AccessControlError,
    ValidationError,
    RateLimitError
)

try:
    client.buffer_transaction(...)
except AccessControlError as e:
    print(f"Access denied: {e}")
    # Request role from administrator
except ValidationError as e:
    print(f"Invalid parameters: {e}")
    # Fix parameters and retry
except RateLimitError as e:
    print(f"Rate limited: {e}")
    # Wait and retry with exponential backoff
except TesseractException as e:
    print(f"System error: {e}")
    # Handle system-level errors
```

## Rate Limits

### Contract Rate Limits

- **Per Block**: 100 transactions maximum
- **Per User Per Block**: 10 transactions maximum
- **Payload Size**: 2048 bytes maximum
- **Coordination Window**: 30 seconds default

### API Rate Limits

- **Buffer Operations**: 10 TPS per account
- **Query Operations**: 100 TPS per account
- **Batch Operations**: 5 batches per minute

## Best Practices

### Transaction Management

1. **Unique IDs**: Always use cryptographically secure random transaction IDs
2. **Dependency Chains**: Keep dependency chains short (< 10 transactions)
3. **Timeouts**: Set reasonable execution timeouts (30-300 seconds)
4. **Error Handling**: Implement robust error handling and retry logic

### Security

1. **Key Management**: Never expose private keys in code
2. **Role Assignment**: Use principle of least privilege
3. **Input Validation**: Validate all inputs before submitting
4. **Monitoring**: Monitor for unusual transaction patterns

### Performance

1. **Batch Operations**: Use batch operations for multiple transactions
2. **Event Filtering**: Use indexed fields for efficient event filtering
3. **Caching**: Cache frequently accessed transaction states
4. **Connection Pooling**: Use connection pooling for high-throughput applications

## Support

- **Documentation**: [https://docs.tesseract.io](https://docs.tesseract.io)
- **Discord**: [https://discord.gg/tesseract](https://discord.gg/tesseract)
- **GitHub**: [https://github.com/tesseract-protocol/tesseract](https://github.com/tesseract-protocol/tesseract)
- **Email**: support@tesseract.io