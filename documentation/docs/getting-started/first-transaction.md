# Your First Transaction

Learn how to create and execute your first cross-rollup transaction with Tesseract.

---

## Overview

In this tutorial, you'll:

1. Deploy a Tesseract contract locally
2. Add an operator
3. Buffer a cross-rollup transaction
4. Resolve dependencies
5. Mark the transaction as executed

---

## Prerequisites

Ensure you've completed the [Quick Start](quick-start.md) guide.

---

## Step 1: Start a Local Blockchain

Start a local Ethereum node for testing:

=== "Anvil (Foundry)"
    ```bash
    anvil
    ```

=== "Ganache"
    ```bash
    ganache-cli
    ```

=== "Hardhat"
    ```bash
    npx hardhat node
    ```

---

## Step 2: Deploy the Contract

```python
from web3 import Web3
import vyper

# Connect to local node
w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

# Use first account as deployer
deployer = w3.eth.accounts[0]

# Compile contract
with open('contracts/TesseractSimple.vy', 'r') as f:
    source = f.read()

compiled = vyper.compile_code(source, output_formats=['abi', 'bytecode'])

# Deploy
Contract = w3.eth.contract(
    abi=compiled['abi'],
    bytecode=compiled['bytecode']
)

tx_hash = Contract.constructor().transact({'from': deployer})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

contract_address = receipt.contractAddress
print(f"Contract deployed at: {contract_address}")
```

---

## Step 3: Add an Operator

```python
# Load deployed contract
contract = w3.eth.contract(
    address=contract_address,
    abi=compiled['abi']
)

# Add operator (use second account)
operator = w3.eth.accounts[1]

tx = contract.functions.add_operator(operator).transact({'from': deployer})
w3.eth.wait_for_transaction_receipt(tx)

# Verify
is_operator = contract.functions.authorized_operators(operator).call()
print(f"Operator authorized: {is_operator}")
```

---

## Step 4: Buffer a Transaction

```python
import time

# Create transaction ID
tx_id = b'\x01' * 32  # 32-byte unique identifier

# Define rollups
origin_rollup = "0x1111111111111111111111111111111111111111"
target_rollup = "0x2222222222222222222222222222222222222222"

# Transaction payload
payload = b"Hello, cross-chain world!"

# No dependency for first transaction
dependency_id = b'\x00' * 32

# Execute 60 seconds from now
execution_time = int(time.time()) + 60

# Buffer the transaction
tx = contract.functions.buffer_transaction(
    tx_id,
    origin_rollup,
    target_rollup,
    payload,
    dependency_id,
    execution_time
).transact({'from': operator})

receipt = w3.eth.wait_for_transaction_receipt(tx)
print(f"Transaction buffered: {receipt.transactionHash.hex()}")

# Check state
state = contract.functions.get_transaction_state(tx_id).call()
print(f"Transaction state: {state}")  # Should be 1 (BUFFERED)
```

---

## Step 5: Resolve Dependencies

```python
# Wait for execution time
print("Waiting for execution time...")
time.sleep(65)

# Resolve dependencies
tx = contract.functions.resolve_dependency(tx_id).transact({'from': operator})
w3.eth.wait_for_transaction_receipt(tx)

# Check if ready
is_ready = contract.functions.is_transaction_ready(tx_id).call()
print(f"Transaction ready: {is_ready}")  # Should be True

# Check state
state = contract.functions.get_transaction_state(tx_id).call()
print(f"Transaction state: {state}")  # Should be 2 (READY)
```

---

## Step 6: Mark as Executed

```python
# Mark transaction as executed
tx = contract.functions.mark_executed(tx_id).transact({'from': operator})
w3.eth.wait_for_transaction_receipt(tx)

# Verify final state
state = contract.functions.get_transaction_state(tx_id).call()
print(f"Final state: {state}")  # Should be 3 (EXECUTED)

# Get full transaction details
details = contract.functions.get_transaction_details(tx_id).call()
print(f"Origin: {details[0]}")
print(f"Target: {details[1]}")
print(f"Dependency: {details[2].hex()}")
print(f"Timestamp: {details[3]}")
print(f"State: {details[4]}")
```

---

## Complete Script

Here's the complete script:

```python
#!/usr/bin/env python3
"""First Tesseract transaction example."""

from web3 import Web3
import vyper
import time

def main():
    # Connect
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
    deployer = w3.eth.accounts[0]
    operator = w3.eth.accounts[1]

    # Compile and deploy
    with open('contracts/TesseractSimple.vy', 'r') as f:
        source = f.read()

    compiled = vyper.compile_code(source, output_formats=['abi', 'bytecode'])

    Contract = w3.eth.contract(abi=compiled['abi'], bytecode=compiled['bytecode'])
    tx_hash = Contract.constructor().transact({'from': deployer})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    contract = w3.eth.contract(address=receipt.contractAddress, abi=compiled['abi'])
    print(f"Deployed at: {receipt.contractAddress}")

    # Add operator
    contract.functions.add_operator(operator).transact({'from': deployer})
    print("Operator added")

    # Buffer transaction
    tx_id = b'\x01' * 32
    contract.functions.buffer_transaction(
        tx_id,
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        b"Hello, cross-chain world!",
        b'\x00' * 32,
        int(time.time()) + 5  # 5 seconds for demo
    ).transact({'from': operator})
    print("Transaction buffered")

    # Wait and resolve
    time.sleep(6)
    contract.functions.resolve_dependency(tx_id).transact({'from': operator})
    print(f"Ready: {contract.functions.is_transaction_ready(tx_id).call()}")

    # Execute
    contract.functions.mark_executed(tx_id).transact({'from': operator})
    state = contract.functions.get_transaction_state(tx_id).call()
    print(f"Final state: {state} (EXECUTED)")

if __name__ == "__main__":
    main()
```

---

## Transaction States

| State | Value | Description |
|-------|-------|-------------|
| EMPTY | 0 | Transaction doesn't exist |
| BUFFERED | 1 | Transaction stored, awaiting resolution |
| READY | 2 | Dependencies resolved, ready for execution |
| EXECUTED | 3 | Successfully executed |

---

## Next Steps

- [Transaction Lifecycle](../concepts/transaction-lifecycle.md) - Deep dive into states
- [Dependency Chains](../examples/dependency-chains.md) - Create transaction dependencies
- [Deploy to Testnet](../guides/deployment.md) - Go live on Sepolia
