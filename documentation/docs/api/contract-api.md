# Smart Contract API

Complete reference for the TesseractSimple.vy smart contract.

---

## Contract Overview

| Property | Value |
|----------|-------|
| **Contract** | TesseractSimple.vy |
| **Language** | Vyper 0.3.10 |
| **Size** | 7,276 bytes compiled |
| **Functions** | 18 total |

---

## Data Structures

### State Enum

```vyper
enum State:
    EMPTY     # 0: Transaction doesn't exist
    BUFFERED  # 1: Transaction stored
    READY     # 2: Ready for execution
    EXECUTED  # 3: Successfully executed
```

### Transaction Struct

```vyper
struct Transaction:
    origin_rollup: address      # Source rollup address
    target_rollup: address      # Destination rollup address
    payload: Bytes[512]         # Transaction data (max 512 bytes)
    dependency_tx_id: bytes32   # Required dependency transaction
    timestamp: uint256          # Execution timestamp
    state: State                # Current transaction state
```

---

## Core Functions

### buffer_transaction

Buffer a new cross-rollup transaction.

```vyper
@external
def buffer_transaction(
    tx_id: bytes32,
    origin_rollup: address,
    target_rollup: address,
    payload: Bytes[512],
    dependency_tx_id: bytes32,
    timestamp: uint256
)
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tx_id` | `bytes32` | Unique transaction identifier |
| `origin_rollup` | `address` | Origin rollup address |
| `target_rollup` | `address` | Target rollup address |
| `payload` | `Bytes[512]` | Transaction data (max 512 bytes) |
| `dependency_tx_id` | `bytes32` | Dependency ID (empty if none) |
| `timestamp` | `uint256` | Execution timestamp |

**Access:** Authorized operators only

**Gas:** ~80,000

**Events:** `TransactionBuffered`

**Reverts:**

- `"Not authorized"` - Caller is not an operator
- `"Invalid transaction ID"` - tx_id is empty
- `"Invalid origin rollup"` - origin_rollup is zero address
- `"Invalid target rollup"` - target_rollup is zero address
- `"Origin and target must be different"` - Same address
- `"Timestamp cannot be in the past"` - timestamp < block.timestamp
- `"Transaction already exists"` - tx_id already used

**Example:**

=== "Python"
    ```python
    tx_id = b'\x01' * 32
    tx = contract.functions.buffer_transaction(
        tx_id,
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        b"payload data",
        b'\x00' * 32,  # No dependency
        int(time.time()) + 300
    ).transact({'from': operator})
    ```

=== "JavaScript"
    ```javascript
    const txId = '0x' + '01'.repeat(32);
    const tx = await contract.buffer_transaction(
        txId,
        '0x1111111111111111111111111111111111111111',
        '0x2222222222222222222222222222222222222222',
        ethers.utils.toUtf8Bytes('payload data'),
        '0x' + '00'.repeat(32),
        Math.floor(Date.now() / 1000) + 300
    );
    ```

---

### resolve_dependency

Check and resolve transaction dependencies.

```vyper
@external
def resolve_dependency(tx_id: bytes32)
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tx_id` | `bytes32` | Transaction to resolve |

**Access:** Authorized operators only

**Gas:** ~40,000

**Events:** `TransactionReady` or `TransactionFailed`

**Logic:**

1. Verify transaction is in BUFFERED state
2. Check if current time >= transaction timestamp
3. Check if current time <= timestamp + coordination_window
4. Verify dependency is READY or EXECUTED (if any)
5. Update state to READY if all conditions met

**Reverts:**

- `"Not authorized"` - Caller is not an operator
- `"Transaction not in buffered state"` - Wrong state

**Example:**

```python
# Resolve after timestamp passes
contract.functions.resolve_dependency(tx_id).transact({'from': operator})

# Check result
state = contract.functions.get_transaction_state(tx_id).call()
```

---

### mark_executed

Mark a transaction as executed.

```vyper
@external
def mark_executed(tx_id: bytes32)
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tx_id` | `bytes32` | Transaction identifier |

**Access:** Authorized operators only

**Gas:** ~25,000

**Requirements:**

- Transaction must be in READY state
- Caller must be authorized operator

**Reverts:**

- `"Not authorized"` - Caller is not an operator
- `"Transaction not ready"` - Not in READY state

**Example:**

```python
# Mark as executed after execution on target chain
contract.functions.mark_executed(tx_id).transact({'from': operator})
```

---

## View Functions

### get_transaction_state

Get current transaction state.

```vyper
@view
@external
def get_transaction_state(tx_id: bytes32) -> State
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tx_id` | `bytes32` | Transaction identifier |

**Returns:** `State` enum value (0-3)

**Example:**

```python
state = contract.functions.get_transaction_state(tx_id).call()
# 0 = EMPTY, 1 = BUFFERED, 2 = READY, 3 = EXECUTED
```

---

### is_transaction_ready

Check if transaction is ready for execution.

```vyper
@view
@external
def is_transaction_ready(tx_id: bytes32) -> bool
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tx_id` | `bytes32` | Transaction identifier |

**Returns:** `bool` - True if state is READY and timestamp has passed

**Example:**

```python
is_ready = contract.functions.is_transaction_ready(tx_id).call()
if is_ready:
    # Safe to execute
    pass
```

---

### get_transaction_details

Get complete transaction details.

```vyper
@view
@external
def get_transaction_details(tx_id: bytes32) -> (address, address, bytes32, uint256, State)
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `tx_id` | `bytes32` | Transaction identifier |

**Returns:** Tuple containing:

| Index | Type | Description |
|-------|------|-------------|
| 0 | `address` | origin_rollup |
| 1 | `address` | target_rollup |
| 2 | `bytes32` | dependency_tx_id |
| 3 | `uint256` | timestamp |
| 4 | `State` | state |

**Example:**

```python
details = contract.functions.get_transaction_details(tx_id).call()
origin, target, dependency, timestamp, state = details
```

---

## Administrative Functions

### add_operator

Add an authorized operator.

```vyper
@external
def add_operator(operator: address)
```

**Access:** Owner only

**Gas:** ~25,000

**Reverts:**

- `"Only owner can add operators"`
- `"Invalid operator address"` - Zero address

---

### remove_operator

Remove operator authorization.

```vyper
@external
def remove_operator(operator: address)
```

**Access:** Owner only

**Gas:** ~25,000

**Reverts:**

- `"Only owner can remove operators"`

---

### set_coordination_window

Configure coordination timing.

```vyper
@external
def set_coordination_window(window: uint256)
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `window` | `uint256` | Window duration in seconds (5-300) |

**Access:** Owner only

**Gas:** ~25,000

**Reverts:**

- `"Only owner can set window"`
- `"Window must be between 5 and 300 seconds"`

---

## Public Storage Variables

### owner

```vyper
owner: public(address)
```

Returns the contract owner address.

### authorized_operators

```vyper
authorized_operators: public(HashMap[address, bool])
```

Check if an address is an authorized operator.

```python
is_operator = contract.functions.authorized_operators(address).call()
```

### transactions

```vyper
transactions: public(HashMap[bytes32, Transaction])
```

Get transaction by ID.

### transaction_count

```vyper
transaction_count: public(uint256)
```

Total number of transactions buffered.

### coordination_window

```vyper
coordination_window: public(uint256)
```

Current coordination window in seconds (default: 30).

---

## Events

### TransactionBuffered

Emitted when a new transaction is buffered.

```vyper
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    timestamp: uint256
```

### TransactionReady

Emitted when dependencies are resolved.

```vyper
event TransactionReady:
    tx_id: indexed(bytes32)
```

### TransactionFailed

Emitted when resolution fails.

```vyper
event TransactionFailed:
    tx_id: indexed(bytes32)
    reason: String[100]
```

---

## Error Messages

| Message | Function | Cause |
|---------|----------|-------|
| `"Not authorized"` | buffer, resolve, execute | Caller not operator |
| `"Only owner can add operators"` | add_operator | Non-owner caller |
| `"Only owner can remove operators"` | remove_operator | Non-owner caller |
| `"Only owner can set window"` | set_coordination_window | Non-owner caller |
| `"Invalid transaction ID"` | buffer_transaction | Empty tx_id |
| `"Invalid origin rollup"` | buffer_transaction | Zero address |
| `"Invalid target rollup"` | buffer_transaction | Zero address |
| `"Origin and target must be different"` | buffer_transaction | Same addresses |
| `"Timestamp cannot be in the past"` | buffer_transaction | Past timestamp |
| `"Transaction already exists"` | buffer_transaction | Duplicate tx_id |
| `"Transaction not in buffered state"` | resolve_dependency | Wrong state |
| `"Transaction not ready"` | mark_executed | Not READY state |
| `"Window must be between 5 and 300 seconds"` | set_coordination_window | Out of range |

---

## Gas Costs

| Operation | Gas Usage |
|-----------|-----------|
| `buffer_transaction` | ~80,000 |
| `resolve_dependency` | ~40,000 |
| `mark_executed` | ~25,000 |
| `add_operator` | ~25,000 |
| `remove_operator` | ~25,000 |
| `set_coordination_window` | ~25,000 |
| View functions | ~3,000-5,000 |

---

## Next Steps

- [Python SDK](python-sdk.md) - High-level Python interface
- [Events](events.md) - Event monitoring guide
- [Examples](../examples/basic-usage.md) - Working examples
