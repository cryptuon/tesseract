# Cross-Chain DeFi Examples

Examples of using Tesseract for DeFi operations across rollups.

---

## Overview

Tesseract enables atomic operations across multiple rollups, perfect for DeFi applications like:

- Cross-chain swaps
- Arbitrage execution
- Liquidity rebalancing
- Cross-chain lending

---

## Cross-Chain Swap

Execute an atomic swap between two rollups:

```python
import os
import time
from dataclasses import dataclass

@dataclass
class SwapOrder:
    """Cross-chain swap order."""
    source_chain: str
    target_chain: str
    source_token: str
    target_token: str
    amount: int
    min_receive: int


def execute_cross_chain_swap(order: SwapOrder):
    """Execute atomic cross-chain swap using Tesseract."""

    print(f"Executing cross-chain swap:")
    print(f"  {order.source_chain} -> {order.target_chain}")
    print(f"  {order.amount} {order.source_token} -> {order.target_token}")

    # Generate swap transaction ID
    swap_id = os.urandom(32)

    # Encode swap payload
    payload = encode_swap_payload(order)

    # Step 1: Lock on source chain
    lock_tx_id = os.urandom(32)

    source_contract.functions.buffer_transaction(
        lock_tx_id,
        order.source_chain,
        order.target_chain,
        payload,
        b'\x00' * 32,  # No dependency
        int(time.time()) + 120  # 2 minute window
    ).transact({'from': operator.address})

    print(f"  Locked on source: {lock_tx_id.hex()[:16]}...")

    # Step 2: Release on target (depends on lock)
    release_tx_id = os.urandom(32)

    target_contract.functions.buffer_transaction(
        release_tx_id,
        order.target_chain,
        order.source_chain,
        payload,
        lock_tx_id,  # Depends on lock
        int(time.time()) + 120
    ).transact({'from': operator.address})

    print(f"  Release queued: {release_tx_id.hex()[:16]}...")

    # Step 3: Wait and resolve
    time.sleep(5)

    # Resolve lock first
    source_contract.functions.resolve_dependency(lock_tx_id).transact({
        'from': operator.address
    })

    # Then resolve release
    target_contract.functions.resolve_dependency(release_tx_id).transact({
        'from': operator.address
    })

    print(f"  Swap resolved!")

    return {
        'swap_id': swap_id.hex(),
        'lock_tx': lock_tx_id.hex(),
        'release_tx': release_tx_id.hex()
    }


def encode_swap_payload(order: SwapOrder) -> bytes:
    """Encode swap parameters into payload."""
    # Simple encoding for example
    return (
        f"{order.source_token}:{order.target_token}:"
        f"{order.amount}:{order.min_receive}"
    ).encode()


# Usage
order = SwapOrder(
    source_chain="0x1111111111111111111111111111111111111111",
    target_chain="0x2222222222222222222222222222222222222222",
    source_token="ETH",
    target_token="USDC",
    amount=1_000_000_000_000_000_000,  # 1 ETH in wei
    min_receive=3000_000_000  # 3000 USDC (6 decimals)
)

result = execute_cross_chain_swap(order)
```

---

## Arbitrage Execution

Execute atomic arbitrage across multiple DEXes:

```python
@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity details."""
    buy_chain: str
    sell_chain: str
    token: str
    buy_price: float
    sell_price: float
    amount: int
    expected_profit: float


def execute_arbitrage(opp: ArbitrageOpportunity):
    """Execute atomic arbitrage."""

    print(f"Executing arbitrage:")
    print(f"  Buy on {opp.buy_chain} at {opp.buy_price}")
    print(f"  Sell on {opp.sell_chain} at {opp.sell_price}")
    print(f"  Expected profit: {opp.expected_profit}")

    execution_time = int(time.time()) + 30

    # Step 1: Buy transaction
    buy_tx_id = os.urandom(32)
    buy_payload = encode_buy_order(opp)

    buy_contract.functions.buffer_transaction(
        buy_tx_id,
        opp.buy_chain,
        opp.sell_chain,
        buy_payload,
        b'\x00' * 32,
        execution_time
    ).transact({'from': operator.address})

    # Step 2: Sell transaction (depends on buy)
    sell_tx_id = os.urandom(32)
    sell_payload = encode_sell_order(opp)

    sell_contract.functions.buffer_transaction(
        sell_tx_id,
        opp.sell_chain,
        opp.buy_chain,
        sell_payload,
        buy_tx_id,  # Must buy before selling
        execution_time
    ).transact({'from': operator.address})

    print(f"  Buy TX: {buy_tx_id.hex()[:16]}...")
    print(f"  Sell TX: {sell_tx_id.hex()[:16]}...")

    # Wait for execution time
    time.sleep(32)

    # Execute atomically
    buy_contract.functions.resolve_dependency(buy_tx_id).transact({
        'from': operator.address
    })
    sell_contract.functions.resolve_dependency(sell_tx_id).transact({
        'from': operator.address
    })

    # Verify both ready
    buy_ready = buy_contract.functions.is_transaction_ready(buy_tx_id).call()
    sell_ready = sell_contract.functions.is_transaction_ready(sell_tx_id).call()

    if buy_ready and sell_ready:
        print("  Arbitrage executed successfully!")
        buy_contract.functions.mark_executed(buy_tx_id).transact({
            'from': operator.address
        })
        sell_contract.functions.mark_executed(sell_tx_id).transact({
            'from': operator.address
        })
        return True
    else:
        print("  Arbitrage failed - rolling back")
        return False


def encode_buy_order(opp: ArbitrageOpportunity) -> bytes:
    return f"BUY:{opp.token}:{opp.amount}:{opp.buy_price}".encode()


def encode_sell_order(opp: ArbitrageOpportunity) -> bytes:
    return f"SELL:{opp.token}:{opp.amount}:{opp.sell_price}".encode()
```

---

## Liquidity Rebalancing

Rebalance liquidity across multiple pools:

```python
@dataclass
class RebalanceConfig:
    """Liquidity rebalancing configuration."""
    pools: list  # List of pool addresses
    target_ratios: dict  # {pool: target_ratio}
    token: str
    total_liquidity: int


def rebalance_liquidity(config: RebalanceConfig):
    """Rebalance liquidity across pools atomically."""

    print(f"Rebalancing liquidity for {config.token}:")

    # Calculate required transfers
    transfers = calculate_transfers(config)

    if not transfers:
        print("  No rebalancing needed")
        return

    # Create dependent transactions for each transfer
    transactions = []
    previous_tx = b'\x00' * 32

    for i, transfer in enumerate(transfers):
        tx_id = os.urandom(32)

        payload = encode_transfer(transfer)

        contract.functions.buffer_transaction(
            tx_id,
            transfer['from_pool'],
            transfer['to_pool'],
            payload,
            previous_tx,  # Chain transfers
            int(time.time()) + 60
        ).transact({'from': operator.address})

        transactions.append({
            'tx_id': tx_id,
            'from': transfer['from_pool'],
            'to': transfer['to_pool'],
            'amount': transfer['amount']
        })

        print(f"  Transfer {i+1}: {transfer['amount']} from {transfer['from_pool'][:10]}...")

        previous_tx = tx_id

    # Resolve all transfers in order
    time.sleep(62)

    for tx in transactions:
        contract.functions.resolve_dependency(tx['tx_id']).transact({
            'from': operator.address
        })

    print(f"  Rebalancing complete!")
    return transactions


def calculate_transfers(config: RebalanceConfig) -> list:
    """Calculate required transfers for rebalancing."""
    # Simplified calculation
    transfers = []
    # ... calculation logic
    return transfers


def encode_transfer(transfer: dict) -> bytes:
    return f"TRANSFER:{transfer['amount']}".encode()
```

---

## Cross-Chain Lending

Coordinate a cross-chain lending position:

```python
@dataclass
class LendingPosition:
    """Cross-chain lending position."""
    collateral_chain: str
    borrow_chain: str
    collateral_token: str
    collateral_amount: int
    borrow_token: str
    borrow_amount: int


def open_cross_chain_position(position: LendingPosition):
    """Open atomic cross-chain lending position."""

    print(f"Opening cross-chain lending position:")
    print(f"  Collateral: {position.collateral_amount} {position.collateral_token}")
    print(f"  Borrow: {position.borrow_amount} {position.borrow_token}")

    execution_time = int(time.time()) + 60

    # Step 1: Deposit collateral
    deposit_tx_id = os.urandom(32)
    deposit_payload = encode_deposit(position)

    collateral_contract.functions.buffer_transaction(
        deposit_tx_id,
        position.collateral_chain,
        position.borrow_chain,
        deposit_payload,
        b'\x00' * 32,
        execution_time
    ).transact({'from': operator.address})

    print(f"  Deposit TX: {deposit_tx_id.hex()[:16]}...")

    # Step 2: Borrow (depends on collateral deposit)
    borrow_tx_id = os.urandom(32)
    borrow_payload = encode_borrow(position)

    borrow_contract.functions.buffer_transaction(
        borrow_tx_id,
        position.borrow_chain,
        position.collateral_chain,
        borrow_payload,
        deposit_tx_id,  # Must deposit collateral first
        execution_time
    ).transact({'from': operator.address})

    print(f"  Borrow TX: {borrow_tx_id.hex()[:16]}...")

    # Execute atomically
    time.sleep(62)

    collateral_contract.functions.resolve_dependency(deposit_tx_id).transact({
        'from': operator.address
    })
    borrow_contract.functions.resolve_dependency(borrow_tx_id).transact({
        'from': operator.address
    })

    # Verify
    deposit_ready = collateral_contract.functions.is_transaction_ready(
        deposit_tx_id
    ).call()
    borrow_ready = borrow_contract.functions.is_transaction_ready(
        borrow_tx_id
    ).call()

    if deposit_ready and borrow_ready:
        # Execute both
        collateral_contract.functions.mark_executed(deposit_tx_id).transact({
            'from': operator.address
        })
        borrow_contract.functions.mark_executed(borrow_tx_id).transact({
            'from': operator.address
        })
        print("  Position opened successfully!")
        return {
            'deposit_tx': deposit_tx_id.hex(),
            'borrow_tx': borrow_tx_id.hex()
        }
    else:
        print("  Failed to open position")
        return None


def encode_deposit(position: LendingPosition) -> bytes:
    return f"DEPOSIT:{position.collateral_token}:{position.collateral_amount}".encode()


def encode_borrow(position: LendingPosition) -> bytes:
    return f"BORROW:{position.borrow_token}:{position.borrow_amount}".encode()
```

---

## Multi-Chain Governance

Execute governance decisions across multiple chains:

```python
def execute_governance_proposal(proposal_id: str, target_chains: list):
    """Execute governance proposal across all target chains."""

    print(f"Executing proposal {proposal_id} across {len(target_chains)} chains")

    execution_time = int(time.time()) + 300  # 5 minute coordination window

    transactions = []
    previous_tx = b'\x00' * 32

    # Create chained execution across all chains
    for i, chain in enumerate(target_chains):
        tx_id = os.urandom(32)

        payload = encode_governance_action(proposal_id, chain)

        contracts[chain].functions.buffer_transaction(
            tx_id,
            chain,
            target_chains[(i + 1) % len(target_chains)],
            payload,
            previous_tx,
            execution_time
        ).transact({'from': operator.address})

        transactions.append({
            'chain': chain,
            'tx_id': tx_id
        })

        previous_tx = tx_id
        print(f"  {chain}: {tx_id.hex()[:16]}...")

    # Wait and resolve all
    time.sleep(302)

    for tx in transactions:
        contracts[tx['chain']].functions.resolve_dependency(
            tx['tx_id']
        ).transact({'from': operator.address})

    # Verify all ready
    all_ready = all(
        contracts[tx['chain']].functions.is_transaction_ready(tx['tx_id']).call()
        for tx in transactions
    )

    if all_ready:
        # Execute all
        for tx in transactions:
            contracts[tx['chain']].functions.mark_executed(
                tx['tx_id']
            ).transact({'from': operator.address})
        print("  Governance proposal executed on all chains!")
    else:
        print("  Proposal execution failed")


def encode_governance_action(proposal_id: str, chain: str) -> bytes:
    return f"GOVERNANCE:{proposal_id}:{chain}".encode()
```

---

## Best Practices for DeFi

1. **Set appropriate coordination windows** - Allow for network latency
2. **Validate prices before execution** - Check for slippage
3. **Implement circuit breakers** - Stop on unusual conditions
4. **Monitor gas prices** - Ensure profitability
5. **Handle partial failures** - Plan rollback strategies

---

## Next Steps

- [Dependency Chains](dependency-chains.md) - Complex dependencies
- [Basic Usage](basic-usage.md) - Simple examples
- [Security Model](../concepts/security-model.md) - Security considerations
