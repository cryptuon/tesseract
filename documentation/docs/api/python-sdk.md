# Python SDK

Python interface for interacting with Tesseract contracts.

---

## Overview

The Python SDK provides a high-level interface for Tesseract operations using Web3.py.

!!! note "SDK Status"
    A dedicated SDK package is planned. Currently, use Web3.py directly with the patterns shown below.

---

## Setup

### Installation

```bash
poetry install
```

### Basic Connection

```python
from web3 import Web3
import json

# Connect to network
w3 = Web3(Web3.HTTPProvider('https://sepolia.infura.io/v3/YOUR_KEY'))

# Load contract ABI
with open('artifacts/TesseractSimple.json', 'r') as f:
    contract_data = json.load(f)

# Create contract instance
contract = w3.eth.contract(
    address='0xYourContractAddress',
    abi=contract_data['abi']
)
```

---

## Client Wrapper

A reusable client class:

```python
from web3 import Web3
from typing import Optional, Tuple
import json
import time

class TesseractClient:
    """High-level client for Tesseract operations."""

    # State enum values
    EMPTY = 0
    BUFFERED = 1
    READY = 2
    EXECUTED = 3

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        private_key: Optional[str] = None,
        abi_path: str = 'artifacts/TesseractSimple.json'
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        with open(abi_path, 'r') as f:
            contract_data = json.load(f)

        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=contract_data['abi']
        )

        if private_key:
            self.account = self.w3.eth.account.from_key(private_key)
        else:
            self.account = None

    def _send_tx(self, func):
        """Send a transaction."""
        if not self.account:
            raise ValueError("No private key configured")

        tx = func.build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price
        })

        signed = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

    # Core operations

    def buffer_transaction(
        self,
        tx_id: bytes,
        origin_rollup: str,
        target_rollup: str,
        payload: bytes,
        dependency_tx_id: bytes = b'\x00' * 32,
        execution_delay: int = 60
    ) -> dict:
        """Buffer a new cross-rollup transaction."""
        timestamp = int(time.time()) + execution_delay

        func = self.contract.functions.buffer_transaction(
            tx_id,
            origin_rollup,
            target_rollup,
            payload,
            dependency_tx_id,
            timestamp
        )

        return self._send_tx(func)

    def resolve_dependency(self, tx_id: bytes) -> dict:
        """Resolve transaction dependencies."""
        func = self.contract.functions.resolve_dependency(tx_id)
        return self._send_tx(func)

    def mark_executed(self, tx_id: bytes) -> dict:
        """Mark transaction as executed."""
        func = self.contract.functions.mark_executed(tx_id)
        return self._send_tx(func)

    # View functions

    def get_state(self, tx_id: bytes) -> int:
        """Get transaction state."""
        return self.contract.functions.get_transaction_state(tx_id).call()

    def is_ready(self, tx_id: bytes) -> bool:
        """Check if transaction is ready."""
        return self.contract.functions.is_transaction_ready(tx_id).call()

    def get_details(self, tx_id: bytes) -> Tuple:
        """Get transaction details."""
        return self.contract.functions.get_transaction_details(tx_id).call()

    # Admin functions

    def add_operator(self, operator: str) -> dict:
        """Add an operator (owner only)."""
        func = self.contract.functions.add_operator(operator)
        return self._send_tx(func)

    def remove_operator(self, operator: str) -> dict:
        """Remove an operator (owner only)."""
        func = self.contract.functions.remove_operator(operator)
        return self._send_tx(func)

    # Utility functions

    def wait_for_ready(
        self,
        tx_id: bytes,
        timeout: int = 120,
        poll_interval: int = 2
    ) -> bool:
        """Wait for transaction to become ready."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_ready(tx_id):
                return True
            time.sleep(poll_interval)
        return False

    def get_state_name(self, tx_id: bytes) -> str:
        """Get human-readable state name."""
        state = self.get_state(tx_id)
        return ['EMPTY', 'BUFFERED', 'READY', 'EXECUTED'][state]
```

---

## Usage Examples

### Basic Workflow

```python
from tesseract_client import TesseractClient
import os

# Initialize client
client = TesseractClient(
    rpc_url=os.environ['RPC_URL'],
    contract_address=os.environ['CONTRACT_ADDRESS'],
    private_key=os.environ['OPERATOR_KEY']
)

# Create transaction
tx_id = b'\x01' * 32
origin = "0x1111111111111111111111111111111111111111"
target = "0x2222222222222222222222222222222222222222"

# Buffer
receipt = client.buffer_transaction(
    tx_id=tx_id,
    origin_rollup=origin,
    target_rollup=target,
    payload=b"Hello, cross-chain!",
    execution_delay=30  # 30 seconds from now
)
print(f"Buffered: {receipt.transactionHash.hex()}")

# Wait and resolve
client.wait_for_ready(tx_id, timeout=60)
client.resolve_dependency(tx_id)

# Check state
print(f"State: {client.get_state_name(tx_id)}")

# Execute
if client.is_ready(tx_id):
    client.mark_executed(tx_id)
    print("Executed successfully!")
```

### Dependency Chain

```python
# Create dependent transactions
tx_a = b'\x01' * 32
tx_b = b'\x02' * 32
tx_c = b'\x03' * 32

# Buffer chain: A -> B -> C
client.buffer_transaction(tx_a, origin, target, b"Step A")
client.buffer_transaction(tx_b, origin, target, b"Step B", dependency_tx_id=tx_a)
client.buffer_transaction(tx_c, origin, target, b"Step C", dependency_tx_id=tx_b)

# Resolve in order
for tx_id in [tx_a, tx_b, tx_c]:
    client.wait_for_ready(tx_id)
    client.resolve_dependency(tx_id)
    print(f"Resolved: {tx_id.hex()[:8]}")
```

### Event Monitoring

```python
def monitor_events(client, from_block='latest'):
    """Monitor transaction events."""

    buffered_filter = client.contract.events.TransactionBuffered.createFilter(
        fromBlock=from_block
    )
    ready_filter = client.contract.events.TransactionReady.createFilter(
        fromBlock=from_block
    )
    failed_filter = client.contract.events.TransactionFailed.createFilter(
        fromBlock=from_block
    )

    while True:
        # Check buffered
        for event in buffered_filter.get_new_entries():
            print(f"Buffered: {event.args.tx_id.hex()}")
            print(f"  Origin: {event.args.origin_rollup}")
            print(f"  Target: {event.args.target_rollup}")

        # Check ready
        for event in ready_filter.get_new_entries():
            print(f"Ready: {event.args.tx_id.hex()}")

        # Check failed
        for event in failed_filter.get_new_entries():
            print(f"Failed: {event.args.tx_id.hex()}")
            print(f"  Reason: {event.args.reason}")

        time.sleep(2)
```

---

## Multi-Chain Client

```python
class MultiChainClient:
    """Client for multi-chain Tesseract operations."""

    def __init__(self, configs: dict):
        """
        configs = {
            'ethereum': {
                'rpc_url': '...',
                'contract_address': '...',
                'private_key': '...'
            },
            'polygon': {...},
            'arbitrum': {...}
        }
        """
        self.clients = {}
        for chain, config in configs.items():
            self.clients[chain] = TesseractClient(**config)

    def buffer_cross_chain(
        self,
        origin_chain: str,
        target_chain: str,
        tx_id: bytes,
        payload: bytes
    ):
        """Buffer a cross-chain transaction."""
        origin_client = self.clients[origin_chain]
        target_client = self.clients[target_chain]

        return origin_client.buffer_transaction(
            tx_id=tx_id,
            origin_rollup=origin_client.contract.address,
            target_rollup=target_client.contract.address,
            payload=payload
        )

    def sync_execution(self, origin_chain: str, tx_id: bytes):
        """Synchronize execution across chains."""
        origin_client = self.clients[origin_chain]

        # Wait for ready on origin
        origin_client.wait_for_ready(tx_id)
        origin_client.resolve_dependency(tx_id)

        # Get target from transaction
        details = origin_client.get_details(tx_id)
        target_address = details[1]

        # Find target chain
        for chain, client in self.clients.items():
            if client.contract.address.lower() == target_address.lower():
                # Execute on target
                client.mark_executed(tx_id)
                break
```

---

## Async Client

```python
import asyncio
from web3 import AsyncWeb3, AsyncHTTPProvider

class AsyncTesseractClient:
    """Async client for high-throughput operations."""

    def __init__(self, rpc_url: str, contract_address: str, abi: dict):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=abi
        )

    async def get_state(self, tx_id: bytes) -> int:
        return await self.contract.functions.get_transaction_state(tx_id).call()

    async def is_ready(self, tx_id: bytes) -> bool:
        return await self.contract.functions.is_transaction_ready(tx_id).call()

    async def monitor_many(self, tx_ids: list[bytes]) -> dict:
        """Check states of multiple transactions concurrently."""
        tasks = [self.get_state(tx_id) for tx_id in tx_ids]
        states = await asyncio.gather(*tasks)
        return dict(zip(tx_ids, states))

# Usage
async def main():
    client = AsyncTesseractClient(...)
    tx_ids = [b'\x01' * 32, b'\x02' * 32, b'\x03' * 32]
    states = await client.monitor_many(tx_ids)
    for tx_id, state in states.items():
        print(f"{tx_id.hex()[:8]}: {state}")

asyncio.run(main())
```

---

## Error Handling

```python
from web3.exceptions import ContractLogicError

def safe_buffer(client, tx_id, origin, target, payload):
    """Buffer with error handling."""
    try:
        return client.buffer_transaction(tx_id, origin, target, payload)
    except ContractLogicError as e:
        if "Not authorized" in str(e):
            print("Error: Not an authorized operator")
        elif "Transaction already exists" in str(e):
            print("Error: Transaction ID already used")
        elif "Timestamp cannot be in the past" in str(e):
            print("Error: Invalid timestamp")
        else:
            print(f"Contract error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

---

## Next Steps

- [Events](events.md) - Event monitoring details
- [Contract API](contract-api.md) - Low-level reference
- [Examples](../examples/basic-usage.md) - More examples
