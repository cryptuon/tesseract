# Dependency Chains

Examples of creating and managing transaction dependencies.

---

## Overview

Tesseract supports transaction dependencies where one transaction must complete before another can execute. This enables complex multi-step workflows.

---

## Simple Dependency

Two transactions where B depends on A:

```python
import os
import time

def simple_dependency():
    """Create two dependent transactions."""

    # Transaction A (no dependency)
    tx_a = os.urandom(32)

    contract.functions.buffer_transaction(
        tx_a,
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        b"Step A: Initialize",
        b'\x00' * 32,  # No dependency
        int(time.time()) + 30
    ).transact({'from': operator.address})

    print(f"Buffered A: {tx_a.hex()[:16]}...")

    # Transaction B (depends on A)
    tx_b = os.urandom(32)

    contract.functions.buffer_transaction(
        tx_b,
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        b"Step B: Execute",
        tx_a,  # Depends on A
        int(time.time()) + 30
    ).transact({'from': operator.address})

    print(f"Buffered B: {tx_b.hex()[:16]}... (depends on A)")

    # Wait for timestamps
    print("\nWaiting for timestamps...")
    time.sleep(32)

    # Resolve A first
    print("\nResolving A...")
    contract.functions.resolve_dependency(tx_a).transact({'from': operator.address})

    state_a = contract.functions.get_transaction_state(tx_a).call()
    print(f"  State A: {state_a} (2=READY)")

    # Now resolve B (dependency satisfied)
    print("\nResolving B...")
    contract.functions.resolve_dependency(tx_b).transact({'from': operator.address})

    state_b = contract.functions.get_transaction_state(tx_b).call()
    print(f"  State B: {state_b} (2=READY)")

    return tx_a, tx_b


# Run
simple_dependency()
```

---

## Linear Chain

Create a chain of N dependent transactions:

```python
def create_chain(length: int = 5):
    """Create a linear chain of dependent transactions."""

    print(f"Creating chain of {length} transactions...\n")

    transactions = []
    previous_id = b'\x00' * 32  # First has no dependency

    for i in range(length):
        tx_id = os.urandom(32)

        contract.functions.buffer_transaction(
            tx_id,
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            f"Chain step {i+1}".encode(),
            previous_id,
            int(time.time()) + 30
        ).transact({'from': operator.address})

        dep_info = f"(depends on {previous_id.hex()[:8]}...)" if i > 0 else "(root)"
        print(f"  {i+1}. {tx_id.hex()[:16]}... {dep_info}")

        transactions.append(tx_id)
        previous_id = tx_id

    return transactions


def resolve_chain(transactions: list):
    """Resolve chain in order."""

    print(f"\nResolving {len(transactions)} transactions in order...")

    # Wait for timestamps
    time.sleep(32)

    for i, tx_id in enumerate(transactions):
        try:
            contract.functions.resolve_dependency(tx_id).transact({
                'from': operator.address
            })
            state = contract.functions.get_transaction_state(tx_id).call()
            print(f"  {i+1}. {tx_id.hex()[:16]}... -> State: {state}")
        except Exception as e:
            print(f"  {i+1}. {tx_id.hex()[:16]}... -> FAILED: {e}")
            break


# Run
chain = create_chain(5)
resolve_chain(chain)
```

---

## Dependency Validation

Check if dependencies are satisfied before resolving:

```python
def check_dependency(tx_id: bytes) -> bool:
    """Check if transaction's dependency is satisfied."""

    # Get transaction details
    details = contract.functions.get_transaction_details(tx_id).call()
    dependency_id = details[2]

    # No dependency
    if dependency_id == b'\x00' * 32:
        print(f"  No dependency for {tx_id.hex()[:16]}...")
        return True

    # Check dependency state
    dep_state = contract.functions.get_transaction_state(dependency_id).call()
    state_names = ['EMPTY', 'BUFFERED', 'READY', 'EXECUTED']

    print(f"  Dependency {dependency_id.hex()[:16]}... is {state_names[dep_state]}")

    # Satisfied if READY or EXECUTED
    return dep_state >= 2


def smart_resolve(tx_id: bytes):
    """Resolve with dependency checking."""

    print(f"\nResolving {tx_id.hex()[:16]}...")

    # Check state
    state = contract.functions.get_transaction_state(tx_id).call()
    if state != 1:  # Not BUFFERED
        print(f"  Cannot resolve: state is {state}")
        return False

    # Check dependency
    if not check_dependency(tx_id):
        print("  Dependency not satisfied!")

        # Get and try to resolve dependency
        details = contract.functions.get_transaction_details(tx_id).call()
        dep_id = details[2]

        if dep_id != b'\x00' * 32:
            print(f"  Attempting to resolve dependency first...")
            success = smart_resolve(dep_id)
            if not success:
                return False

    # Now resolve this transaction
    try:
        contract.functions.resolve_dependency(tx_id).transact({
            'from': operator.address
        })
        print(f"  Resolved successfully!")
        return True
    except Exception as e:
        print(f"  Resolution failed: {e}")
        return False
```

---

## Parallel Branches

Create transactions that branch from a common root:

```python
def create_branches():
    """Create branching dependency structure.

    Structure:
        A (root)
       / \
      B   C
       \ /
        D
    """

    print("Creating branching structure...\n")

    # Root transaction A
    tx_a = os.urandom(32)
    contract.functions.buffer_transaction(
        tx_a, origin, target,
        b"Root A",
        b'\x00' * 32,
        int(time.time()) + 30
    ).transact({'from': operator.address})
    print(f"A (root): {tx_a.hex()[:16]}...")

    # Branch B (depends on A)
    tx_b = os.urandom(32)
    contract.functions.buffer_transaction(
        tx_b, origin, target,
        b"Branch B",
        tx_a,
        int(time.time()) + 30
    ).transact({'from': operator.address})
    print(f"B (-> A): {tx_b.hex()[:16]}...")

    # Branch C (depends on A)
    tx_c = os.urandom(32)
    contract.functions.buffer_transaction(
        tx_c, origin, target,
        b"Branch C",
        tx_a,
        int(time.time()) + 30
    ).transact({'from': operator.address})
    print(f"C (-> A): {tx_c.hex()[:16]}...")

    # Note: D would need multiple dependencies (not yet supported)
    # For now, D depends only on B
    tx_d = os.urandom(32)
    contract.functions.buffer_transaction(
        tx_d, origin, target,
        b"Merge D",
        tx_b,  # Only one dependency supported currently
        int(time.time()) + 30
    ).transact({'from': operator.address})
    print(f"D (-> B): {tx_d.hex()[:16]}...")

    return {'A': tx_a, 'B': tx_b, 'C': tx_c, 'D': tx_d}


def resolve_branches(txs: dict):
    """Resolve branching structure."""

    print("\nResolving branches...")
    time.sleep(32)

    # Resolve in correct order
    for name in ['A', 'B', 'C', 'D']:
        tx_id = txs[name]
        contract.functions.resolve_dependency(tx_id).transact({
            'from': operator.address
        })
        state = contract.functions.get_transaction_state(tx_id).call()
        print(f"  {name}: State = {state}")


# Run
origin = "0x1111111111111111111111111111111111111111"
target = "0x2222222222222222222222222222222222222222"

branches = create_branches()
resolve_branches(branches)
```

---

## Dependency Graph Visualization

```python
def visualize_dependencies(tx_ids: list):
    """Print dependency graph."""

    print("\nDependency Graph:")
    print("=" * 40)

    for tx_id in tx_ids:
        details = contract.functions.get_transaction_details(tx_id).call()
        dep_id = details[2]
        state = details[4]
        state_names = ['EMPTY', 'BUFFERED', 'READY', 'EXECUTED']

        tx_short = tx_id.hex()[:8]
        dep_short = dep_id.hex()[:8] if dep_id != b'\x00' * 32 else "none"

        print(f"  {tx_short} [{state_names[state]}] -> depends on: {dep_short}")

    print("=" * 40)


# Usage
chain = create_chain(3)
visualize_dependencies(chain)
```

---

## Auto-Resolver

Automatically resolve transactions as their dependencies become ready:

```python
import threading

class AutoResolver:
    """Automatically resolve transactions when ready."""

    def __init__(self, contract, operator):
        self.contract = contract
        self.operator = operator
        self.pending = []
        self.running = False

    def add(self, tx_id: bytes):
        """Add transaction to watch list."""
        self.pending.append(tx_id)

    def start(self):
        """Start auto-resolver in background."""
        self.running = True
        thread = threading.Thread(target=self._resolve_loop)
        thread.daemon = True
        thread.start()

    def stop(self):
        """Stop auto-resolver."""
        self.running = False

    def _can_resolve(self, tx_id: bytes) -> bool:
        """Check if transaction can be resolved."""
        state = self.contract.functions.get_transaction_state(tx_id).call()
        if state != 1:  # Not BUFFERED
            return False

        details = self.contract.functions.get_transaction_details(tx_id).call()
        dep_id = details[2]
        timestamp = details[3]

        # Check timestamp
        if int(time.time()) < timestamp:
            return False

        # Check dependency
        if dep_id != b'\x00' * 32:
            dep_state = self.contract.functions.get_transaction_state(dep_id).call()
            if dep_state < 2:  # Not READY or EXECUTED
                return False

        return True

    def _resolve_loop(self):
        """Main resolution loop."""
        while self.running:
            resolved = []

            for tx_id in self.pending:
                if self._can_resolve(tx_id):
                    try:
                        self.contract.functions.resolve_dependency(tx_id).transact({
                            'from': self.operator.address
                        })
                        print(f"[AutoResolver] Resolved: {tx_id.hex()[:16]}...")
                        resolved.append(tx_id)
                    except Exception as e:
                        print(f"[AutoResolver] Failed: {tx_id.hex()[:16]}... - {e}")

            # Remove resolved
            for tx_id in resolved:
                self.pending.remove(tx_id)

            time.sleep(2)


# Usage
resolver = AutoResolver(contract, operator)
resolver.start()

# Create transactions
chain = create_chain(3)
for tx_id in chain:
    resolver.add(tx_id)

# Wait for auto-resolution
time.sleep(60)
resolver.stop()
```

---

## Next Steps

- [Cross-Chain DeFi](cross-chain-defi.md) - DeFi use cases
- [Basic Usage](basic-usage.md) - Simple examples
- [API Reference](../api/contract-api.md) - Full API
