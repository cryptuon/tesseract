# Basic Usage Examples

Working examples for common Tesseract operations.

---

## Setup

All examples assume this setup:

```python
from web3 import Web3
import json
import time
import os

# Connect to network
w3 = Web3(Web3.HTTPProvider(os.environ['RPC_URL']))

# Load contract
with open('artifacts/TesseractSimple.json', 'r') as f:
    contract_data = json.load(f)

contract = w3.eth.contract(
    address=os.environ['CONTRACT_ADDRESS'],
    abi=contract_data['abi']
)

# Operator account
operator = w3.eth.account.from_key(os.environ['OPERATOR_KEY'])
```

---

## Buffer a Transaction

```python
def buffer_transaction():
    """Buffer a simple cross-rollup transaction."""

    # Generate unique transaction ID
    tx_id = os.urandom(32)

    # Define rollups
    origin = "0x1111111111111111111111111111111111111111"
    target = "0x2222222222222222222222222222222222222222"

    # Payload data
    payload = b"Hello, cross-chain!"

    # Execute 60 seconds from now
    timestamp = int(time.time()) + 60

    # Build transaction
    tx = contract.functions.buffer_transaction(
        tx_id,
        origin,
        target,
        payload,
        b'\x00' * 32,  # No dependency
        timestamp
    ).build_transaction({
        'from': operator.address,
        'nonce': w3.eth.get_transaction_count(operator.address),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price
    })

    # Sign and send
    signed = w3.eth.account.sign_transaction(tx, operator.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

    # Wait for confirmation
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"Transaction buffered!")
    print(f"  TX ID: {tx_id.hex()}")
    print(f"  TX Hash: {receipt.transactionHash.hex()}")
    print(f"  Gas Used: {receipt.gasUsed}")

    return tx_id


# Run
tx_id = buffer_transaction()
```

---

## Check Transaction State

```python
def check_transaction(tx_id: bytes):
    """Check the state of a transaction."""

    # Get state
    state = contract.functions.get_transaction_state(tx_id).call()
    state_names = ['EMPTY', 'BUFFERED', 'READY', 'EXECUTED']

    print(f"Transaction: {tx_id.hex()[:16]}...")
    print(f"State: {state_names[state]}")

    if state == 0:
        return

    # Get details
    details = contract.functions.get_transaction_details(tx_id).call()
    origin, target, dependency, timestamp, _ = details

    print(f"Origin: {origin}")
    print(f"Target: {target}")
    print(f"Timestamp: {timestamp}")

    # Check if ready
    is_ready = contract.functions.is_transaction_ready(tx_id).call()
    print(f"Ready: {is_ready}")


# Run
check_transaction(tx_id)
```

---

## Resolve Dependencies

```python
def resolve_and_execute(tx_id: bytes):
    """Resolve dependencies and mark executed."""

    # Check current state
    state = contract.functions.get_transaction_state(tx_id).call()
    if state != 1:  # Not BUFFERED
        print(f"Cannot resolve: state is {state}")
        return

    # Get timestamp
    details = contract.functions.get_transaction_details(tx_id).call()
    timestamp = details[3]

    # Wait for timestamp
    wait_time = timestamp - int(time.time())
    if wait_time > 0:
        print(f"Waiting {wait_time}s for timestamp...")
        time.sleep(wait_time + 1)

    # Resolve
    print("Resolving dependencies...")
    tx = contract.functions.resolve_dependency(tx_id).build_transaction({
        'from': operator.address,
        'nonce': w3.eth.get_transaction_count(operator.address),
        'gas': 100000,
        'gasPrice': w3.eth.gas_price
    })

    signed = w3.eth.account.sign_transaction(tx, operator.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)

    # Check if ready
    is_ready = contract.functions.is_transaction_ready(tx_id).call()
    print(f"Ready: {is_ready}")

    if not is_ready:
        print("Transaction not ready, check events for failure reason")
        return

    # Mark executed
    print("Marking as executed...")
    tx = contract.functions.mark_executed(tx_id).build_transaction({
        'from': operator.address,
        'nonce': w3.eth.get_transaction_count(operator.address),
        'gas': 50000,
        'gasPrice': w3.eth.gas_price
    })

    signed = w3.eth.account.sign_transaction(tx, operator.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)

    print("Transaction executed!")


# Run
resolve_and_execute(tx_id)
```

---

## Complete Workflow

```python
def full_workflow():
    """Complete transaction lifecycle example."""

    print("=== Tesseract Full Workflow ===\n")

    # 1. Buffer
    print("Step 1: Buffer transaction")
    tx_id = os.urandom(32)

    contract.functions.buffer_transaction(
        tx_id,
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        b"Full workflow test",
        b'\x00' * 32,
        int(time.time()) + 10  # 10 seconds
    ).transact({'from': operator.address})

    state = contract.functions.get_transaction_state(tx_id).call()
    print(f"  State: BUFFERED ({state})")

    # 2. Wait
    print("\nStep 2: Wait for timestamp")
    time.sleep(12)
    print("  Done")

    # 3. Resolve
    print("\nStep 3: Resolve dependencies")
    contract.functions.resolve_dependency(tx_id).transact({'from': operator.address})

    state = contract.functions.get_transaction_state(tx_id).call()
    print(f"  State: READY ({state})")

    # 4. Execute
    print("\nStep 4: Mark executed")
    contract.functions.mark_executed(tx_id).transact({'from': operator.address})

    state = contract.functions.get_transaction_state(tx_id).call()
    print(f"  State: EXECUTED ({state})")

    print("\n=== Workflow Complete ===")
    print(f"Transaction ID: {tx_id.hex()}")


# Run
full_workflow()
```

---

## Monitor Events

```python
def monitor_events(duration: int = 60):
    """Monitor events for a period of time."""

    print(f"Monitoring events for {duration} seconds...\n")

    # Create filters
    buffered_filter = contract.events.TransactionBuffered.createFilter(
        fromBlock='latest'
    )
    ready_filter = contract.events.TransactionReady.createFilter(
        fromBlock='latest'
    )
    failed_filter = contract.events.TransactionFailed.createFilter(
        fromBlock='latest'
    )

    start = time.time()
    while time.time() - start < duration:
        # Check buffered
        for event in buffered_filter.get_new_entries():
            print(f"[BUFFERED] {event.args.tx_id.hex()[:16]}...")
            print(f"  Origin: {event.args.origin_rollup}")
            print(f"  Target: {event.args.target_rollup}")

        # Check ready
        for event in ready_filter.get_new_entries():
            print(f"[READY] {event.args.tx_id.hex()[:16]}...")

        # Check failed
        for event in failed_filter.get_new_entries():
            print(f"[FAILED] {event.args.tx_id.hex()[:16]}...")
            print(f"  Reason: {event.args.reason}")

        time.sleep(2)

    print("Monitoring complete.")


# Run
monitor_events(60)
```

---

## Batch Operations

```python
def batch_buffer(count: int = 5):
    """Buffer multiple transactions."""

    tx_ids = []

    print(f"Buffering {count} transactions...\n")

    for i in range(count):
        tx_id = os.urandom(32)

        contract.functions.buffer_transaction(
            tx_id,
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            f"Batch transaction {i}".encode(),
            b'\x00' * 32,
            int(time.time()) + 30
        ).transact({'from': operator.address})

        tx_ids.append(tx_id)
        print(f"  {i+1}. {tx_id.hex()[:16]}...")

    print(f"\nBuffered {len(tx_ids)} transactions")
    return tx_ids


def batch_resolve(tx_ids: list):
    """Resolve multiple transactions."""

    print(f"\nResolving {len(tx_ids)} transactions...")

    # Wait for timestamps
    time.sleep(32)

    for tx_id in tx_ids:
        try:
            contract.functions.resolve_dependency(tx_id).transact({
                'from': operator.address
            })
            print(f"  Resolved: {tx_id.hex()[:16]}...")
        except Exception as e:
            print(f"  Failed: {tx_id.hex()[:16]}... - {e}")


# Run
tx_ids = batch_buffer(5)
batch_resolve(tx_ids)
```

---

## Error Handling

```python
from web3.exceptions import ContractLogicError

def safe_buffer(origin: str, target: str, payload: bytes):
    """Buffer with comprehensive error handling."""

    tx_id = os.urandom(32)

    try:
        tx = contract.functions.buffer_transaction(
            tx_id, origin, target, payload,
            b'\x00' * 32, int(time.time()) + 60
        ).build_transaction({
            'from': operator.address,
            'nonce': w3.eth.get_transaction_count(operator.address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        signed = w3.eth.account.sign_transaction(tx, operator.key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"Success: {tx_id.hex()[:16]}...")
            return tx_id
        else:
            print("Transaction failed (reverted)")
            return None

    except ContractLogicError as e:
        error_msg = str(e)
        if "Not authorized" in error_msg:
            print("Error: Not an authorized operator")
        elif "Transaction already exists" in error_msg:
            print("Error: Duplicate transaction ID")
        elif "Timestamp cannot be in the past" in error_msg:
            print("Error: Invalid timestamp")
        else:
            print(f"Contract error: {error_msg}")
        return None

    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


# Run
result = safe_buffer(
    "0x1111111111111111111111111111111111111111",
    "0x2222222222222222222222222222222222222222",
    b"Test payload"
)
```

---

## Next Steps

- [Dependency Chains](dependency-chains.md) - Create linked transactions
- [Cross-Chain DeFi](cross-chain-defi.md) - DeFi examples
- [API Reference](../api/contract-api.md) - Full API docs
