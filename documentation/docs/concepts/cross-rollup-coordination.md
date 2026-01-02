# Cross-Rollup Coordination

How Tesseract coordinates transaction execution across multiple rollups.

---

## Multi-Chain Architecture

Tesseract is designed for deployment across multiple Layer 2 rollups:

```mermaid
graph TB
    subgraph Ethereum
        E[Tesseract Coordinator]
    end

    subgraph Polygon
        P[Tesseract Coordinator]
    end

    subgraph Arbitrum
        A[Tesseract Coordinator]
    end

    subgraph Optimism
        O[Tesseract Coordinator]
    end

    E <-->|Coordinate| P
    E <-->|Coordinate| A
    E <-->|Coordinate| O
    P <-->|Coordinate| A
    P <-->|Coordinate| O
    A <-->|Coordinate| O
```

---

## Supported Networks

| Network | Mainnet | Testnet |
|---------|---------|---------|
| Ethereum | Mainnet | Sepolia |
| Polygon | Mainnet | Mumbai |
| Arbitrum | One | Goerli |
| Optimism | Mainnet | Goerli |

---

## Coordination Patterns

### 1. Point-to-Point Transfer

Simple transfer between two rollups:

```mermaid
sequenceDiagram
    participant Ethereum
    participant Polygon

    Note over Ethereum: User initiates
    Ethereum->>Ethereum: Buffer transaction
    Ethereum->>Ethereum: Resolve dependency
    Ethereum->>Polygon: Execute on target
    Polygon->>Ethereum: Confirm execution
    Ethereum->>Ethereum: Mark executed
```

**Example:**

```python
# Transfer from Ethereum to Polygon
tx_id = generate_tx_id()

# Buffer on Ethereum
eth_contract.functions.buffer_transaction(
    tx_id,
    eth_contract.address,      # Origin: Ethereum
    polygon_contract.address,  # Target: Polygon
    payload,
    b'\x00' * 32,             # No dependency
    execution_time
).transact({'from': operator})
```

### 2. Multi-Hop Coordination

Transaction spanning multiple rollups in sequence:

```mermaid
sequenceDiagram
    participant Ethereum
    participant Arbitrum
    participant Polygon

    Note over Ethereum: Step 1
    Ethereum->>Ethereum: Buffer TX-A
    Ethereum->>Ethereum: Resolve TX-A

    Note over Arbitrum: Step 2
    Arbitrum->>Arbitrum: Buffer TX-B (depends on TX-A)
    Ethereum->>Arbitrum: Confirm TX-A ready
    Arbitrum->>Arbitrum: Resolve TX-B

    Note over Polygon: Step 3
    Polygon->>Polygon: Buffer TX-C (depends on TX-B)
    Arbitrum->>Polygon: Confirm TX-B ready
    Polygon->>Polygon: Resolve TX-C
```

### 3. Parallel Execution

Multiple independent transactions across rollups:

```mermaid
graph LR
    subgraph Origin
        A[Buffer All]
    end

    subgraph Parallel
        B[Execute on Polygon]
        C[Execute on Arbitrum]
        D[Execute on Optimism]
    end

    A --> B
    A --> C
    A --> D
```

---

## Dependency Graphs

### Linear Dependencies

```python
# Transaction chain: A -> B -> C
transactions = [
    {"id": b'\x01' * 32, "dependency": b'\x00' * 32},  # A: no dependency
    {"id": b'\x02' * 32, "dependency": b'\x01' * 32},  # B: depends on A
    {"id": b'\x03' * 32, "dependency": b'\x02' * 32},  # C: depends on B
]

# Buffer all
for tx in transactions:
    contract.functions.buffer_transaction(
        tx["id"], origin, target, payload, tx["dependency"], timestamp
    ).transact({'from': operator})

# Resolve in order
for tx in transactions:
    contract.functions.resolve_dependency(tx["id"]).transact({'from': operator})
```

### DAG Dependencies

```mermaid
graph TD
    A[Transaction A] --> C[Transaction C]
    B[Transaction B] --> C
    C --> D[Transaction D]
```

!!! note "Current Limitation"
    The current implementation supports single dependencies. DAG support with multiple dependencies is planned for future releases.

---

## Cross-Chain State Synchronization

### Event-Based Synchronization

Monitor events on origin chain to trigger actions on target:

```python
def sync_cross_chain(origin_contract, target_contract):
    """Synchronize state between chains."""

    # Watch for ready transactions on origin
    event_filter = origin_contract.events.TransactionReady.createFilter(
        fromBlock='latest'
    )

    while True:
        for event in event_filter.get_new_entries():
            tx_id = event.args.tx_id

            # Get transaction details
            details = origin_contract.functions.get_transaction_details(tx_id).call()
            origin, target, dep, timestamp, state = details

            # If this targets our chain, execute
            if target == target_contract.address:
                execute_on_target(target_contract, tx_id, details)

        time.sleep(2)
```

### Merkle Proof Verification

For trustless cross-chain verification (future feature):

```python
# Verify transaction inclusion on origin chain
def verify_cross_chain(origin_proof, target_contract):
    # Verify Merkle proof
    is_valid = verify_merkle_proof(
        origin_proof.root,
        origin_proof.leaf,
        origin_proof.path
    )

    if is_valid:
        # Safe to execute on target
        target_contract.functions.mark_executed(tx_id).transact()
```

---

## Timing Coordination

### Coordination Window

All transactions must be resolved within the coordination window:

```python
# Default: 30 seconds
# Configurable: 5-300 seconds

# Set custom window (owner only)
contract.functions.set_coordination_window(60).transact({'from': owner})
```

### Cross-Chain Timing

Account for block time differences:

| Network | Block Time | Finality |
|---------|------------|----------|
| Ethereum | ~12s | ~15 min |
| Polygon | ~2s | ~5 min |
| Arbitrum | ~0.25s | ~15 min |
| Optimism | ~2s | ~15 min |

**Best Practice:** Set execution timestamps with sufficient buffer:

```python
# Allow for worst-case cross-chain latency
buffer_time = 300  # 5 minutes
execution_time = int(time.time()) + buffer_time
```

---

## Operator Network

### Distributed Operators

Deploy operators across regions for reliability:

```mermaid
graph TB
    subgraph US-East
        OP1[Operator 1]
    end

    subgraph EU-West
        OP2[Operator 2]
    end

    subgraph Asia
        OP3[Operator 3]
    end

    OP1 --> C[Tesseract Contracts]
    OP2 --> C
    OP3 --> C
```

### Operator Responsibilities

| Task | Frequency | Priority |
|------|-----------|----------|
| Monitor events | Continuous | High |
| Resolve dependencies | On-demand | High |
| Mark executions | On-demand | Medium |
| Health checks | Every minute | Medium |

---

## Error Recovery

### Failed Resolution

```python
def handle_failed_resolution(contract, tx_id):
    """Handle failed dependency resolution."""

    # Check failure reason
    logs = contract.events.TransactionFailed.getLogs(
        argument_filters={'tx_id': tx_id}
    )

    for log in logs:
        reason = log.args.reason

        if "expired" in reason:
            # Transaction missed its window
            # User needs to create new transaction
            notify_user_expired(tx_id)

        elif "dependency" in reason:
            # Dependency not satisfied
            # Check and resolve dependency first
            dep_id = get_dependency(tx_id)
            contract.functions.resolve_dependency(dep_id).transact()
```

### Circuit Breaker

Emergency pause for critical issues:

```python
# Owner can pause operations
contract.functions.pause().transact({'from': owner})

# Resume when safe
contract.functions.unpause().transact({'from': owner})
```

---

## Performance Considerations

### Gas Costs by Network

| Network | Buffer Gas | Resolve Gas |
|---------|------------|-------------|
| Ethereum | ~80,000 | ~40,000 |
| Polygon | ~80,000 | ~40,000 |
| Arbitrum | ~80,000 | ~40,000 |
| Optimism | ~80,000 | ~40,000 |

### Throughput

- **Target**: 1000+ transactions per coordination window
- **Bottleneck**: Block space on individual rollups
- **Optimization**: Batch processing in application layer

---

## Next Steps

- [Security Model](security-model.md) - Security architecture
- [Deployment Guide](../guides/deployment.md) - Multi-chain deployment
- [Monitoring](../guides/monitoring.md) - Cross-chain monitoring
