# Events

Guide to monitoring and handling Tesseract events.

---

## Overview

Tesseract emits events at key points in the transaction lifecycle:

| Event | When Emitted |
|-------|--------------|
| `TransactionBuffered` | New transaction stored |
| `TransactionReady` | Dependencies resolved successfully |
| `TransactionFailed` | Resolution failed |

---

## Event Definitions

### TransactionBuffered

```vyper
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    timestamp: uint256
```

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| `tx_id` | `bytes32` | Yes | Transaction identifier |
| `origin_rollup` | `address` | Yes | Source rollup |
| `target_rollup` | `address` | Yes | Destination rollup |
| `timestamp` | `uint256` | No | Execution timestamp |

### TransactionReady

```vyper
event TransactionReady:
    tx_id: indexed(bytes32)
```

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| `tx_id` | `bytes32` | Yes | Transaction identifier |

### TransactionFailed

```vyper
event TransactionFailed:
    tx_id: indexed(bytes32)
    reason: String[100]
```

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| `tx_id` | `bytes32` | Yes | Transaction identifier |
| `reason` | `String[100]` | No | Failure reason |

---

## Monitoring Events

### Python - Polling

```python
from web3 import Web3
import time

def poll_events(contract, from_block='latest'):
    """Poll for new events."""

    # Create filters
    buffered = contract.events.TransactionBuffered.createFilter(
        fromBlock=from_block
    )
    ready = contract.events.TransactionReady.createFilter(
        fromBlock=from_block
    )
    failed = contract.events.TransactionFailed.createFilter(
        fromBlock=from_block
    )

    while True:
        # Process buffered events
        for event in buffered.get_new_entries():
            handle_buffered(event)

        # Process ready events
        for event in ready.get_new_entries():
            handle_ready(event)

        # Process failed events
        for event in failed.get_new_entries():
            handle_failed(event)

        time.sleep(2)


def handle_buffered(event):
    print(f"New transaction buffered:")
    print(f"  ID: {event.args.tx_id.hex()}")
    print(f"  Origin: {event.args.origin_rollup}")
    print(f"  Target: {event.args.target_rollup}")
    print(f"  Timestamp: {event.args.timestamp}")


def handle_ready(event):
    print(f"Transaction ready: {event.args.tx_id.hex()}")


def handle_failed(event):
    print(f"Transaction failed: {event.args.tx_id.hex()}")
    print(f"  Reason: {event.args.reason}")
```

### Python - WebSocket

```python
import asyncio
from web3 import AsyncWeb3
from web3.providers import WebsocketProvider

async def stream_events(contract):
    """Stream events via WebSocket."""

    async for event in contract.events.TransactionBuffered.subscribe():
        print(f"Buffered: {event.args.tx_id.hex()}")

    async for event in contract.events.TransactionReady.subscribe():
        print(f"Ready: {event.args.tx_id.hex()}")
```

### JavaScript

```javascript
// Real-time event listening
contract.on('TransactionBuffered', (txId, origin, target, timestamp, event) => {
    console.log('New transaction:', {
        txId: txId,
        origin: origin,
        target: target,
        timestamp: timestamp.toString(),
        block: event.blockNumber
    });
});

contract.on('TransactionReady', (txId, event) => {
    console.log('Transaction ready:', txId);
});

contract.on('TransactionFailed', (txId, reason, event) => {
    console.log('Transaction failed:', txId, reason);
});
```

---

## Filtering Events

### By Transaction ID

```python
# Filter for specific transaction
tx_id = b'\x01' * 32

filter = contract.events.TransactionBuffered.createFilter(
    fromBlock=0,
    argument_filters={'tx_id': tx_id}
)

events = filter.get_all_entries()
```

### By Rollup Address

```python
# Filter by origin rollup
origin_filter = contract.events.TransactionBuffered.createFilter(
    fromBlock=0,
    argument_filters={'origin_rollup': '0x1111...'}
)

# Filter by target rollup
target_filter = contract.events.TransactionBuffered.createFilter(
    fromBlock=0,
    argument_filters={'target_rollup': '0x2222...'}
)
```

### By Block Range

```python
# Get events from block range
filter = contract.events.TransactionBuffered.createFilter(
    fromBlock=1000000,
    toBlock=1001000
)

events = filter.get_all_entries()
print(f"Found {len(events)} events")
```

---

## Historical Events

### Get All Past Events

```python
def get_all_transactions(contract):
    """Retrieve all buffered transactions."""

    # Get all buffered events
    events = contract.events.TransactionBuffered.getLogs(fromBlock=0)

    transactions = []
    for event in events:
        transactions.append({
            'tx_id': event.args.tx_id.hex(),
            'origin': event.args.origin_rollup,
            'target': event.args.target_rollup,
            'timestamp': event.args.timestamp,
            'block': event.blockNumber
        })

    return transactions
```

### Build Transaction History

```python
def build_transaction_history(contract, tx_id):
    """Build complete history for a transaction."""

    history = []

    # Check buffered
    buffered = contract.events.TransactionBuffered.getLogs(
        fromBlock=0,
        argument_filters={'tx_id': tx_id}
    )
    if buffered:
        history.append({
            'event': 'BUFFERED',
            'block': buffered[0].blockNumber,
            'data': dict(buffered[0].args)
        })

    # Check ready
    ready = contract.events.TransactionReady.getLogs(
        fromBlock=0,
        argument_filters={'tx_id': tx_id}
    )
    if ready:
        history.append({
            'event': 'READY',
            'block': ready[0].blockNumber
        })

    # Check failed
    failed = contract.events.TransactionFailed.getLogs(
        fromBlock=0,
        argument_filters={'tx_id': tx_id}
    )
    if failed:
        history.append({
            'event': 'FAILED',
            'block': failed[0].blockNumber,
            'reason': failed[0].args.reason
        })

    return sorted(history, key=lambda x: x['block'])
```

---

## Event-Driven Architecture

### Observer Pattern

```python
class TransactionObserver:
    """Observer for transaction events."""

    def __init__(self, contract):
        self.contract = contract
        self.handlers = {
            'buffered': [],
            'ready': [],
            'failed': []
        }

    def on_buffered(self, handler):
        self.handlers['buffered'].append(handler)
        return self

    def on_ready(self, handler):
        self.handlers['ready'].append(handler)
        return self

    def on_failed(self, handler):
        self.handlers['failed'].append(handler)
        return self

    def start(self):
        """Start observing events."""
        buffered = self.contract.events.TransactionBuffered.createFilter(
            fromBlock='latest'
        )
        ready = self.contract.events.TransactionReady.createFilter(
            fromBlock='latest'
        )
        failed = self.contract.events.TransactionFailed.createFilter(
            fromBlock='latest'
        )

        while True:
            for event in buffered.get_new_entries():
                for handler in self.handlers['buffered']:
                    handler(event)

            for event in ready.get_new_entries():
                for handler in self.handlers['ready']:
                    handler(event)

            for event in failed.get_new_entries():
                for handler in self.handlers['failed']:
                    handler(event)

            time.sleep(2)


# Usage
observer = TransactionObserver(contract)

observer.on_buffered(lambda e: print(f"Buffered: {e.args.tx_id.hex()}"))
observer.on_ready(lambda e: print(f"Ready: {e.args.tx_id.hex()}"))
observer.on_failed(lambda e: print(f"Failed: {e.args.tx_id.hex()}"))

observer.start()
```

### Webhook Integration

```python
import requests

def send_webhook(url, event_type, data):
    """Send event to webhook endpoint."""
    payload = {
        'event_type': event_type,
        'data': data,
        'timestamp': int(time.time())
    }
    response = requests.post(url, json=payload)
    return response.status_code == 200


def monitor_with_webhooks(contract, webhook_url):
    """Monitor events and send to webhook."""

    observer = TransactionObserver(contract)

    observer.on_buffered(lambda e: send_webhook(
        webhook_url,
        'transaction.buffered',
        {
            'tx_id': e.args.tx_id.hex(),
            'origin': e.args.origin_rollup,
            'target': e.args.target_rollup
        }
    ))

    observer.on_ready(lambda e: send_webhook(
        webhook_url,
        'transaction.ready',
        {'tx_id': e.args.tx_id.hex()}
    ))

    observer.on_failed(lambda e: send_webhook(
        webhook_url,
        'transaction.failed',
        {
            'tx_id': e.args.tx_id.hex(),
            'reason': e.args.reason
        }
    ))

    observer.start()
```

---

## Metrics and Monitoring

### Event Metrics

```python
from collections import defaultdict
import time

class EventMetrics:
    """Collect metrics from events."""

    def __init__(self):
        self.counts = defaultdict(int)
        self.last_events = defaultdict(list)

    def record_buffered(self, event):
        self.counts['buffered'] += 1
        self.last_events['buffered'].append({
            'tx_id': event.args.tx_id.hex(),
            'time': time.time()
        })

    def record_ready(self, event):
        self.counts['ready'] += 1

    def record_failed(self, event):
        self.counts['failed'] += 1
        self.last_events['failed'].append({
            'tx_id': event.args.tx_id.hex(),
            'reason': event.args.reason,
            'time': time.time()
        })

    def get_stats(self):
        return {
            'total_buffered': self.counts['buffered'],
            'total_ready': self.counts['ready'],
            'total_failed': self.counts['failed'],
            'success_rate': self.counts['ready'] / max(1, self.counts['buffered']),
            'recent_failures': self.last_events['failed'][-10:]
        }
```

---

## Best Practices

1. **Use indexed fields for filtering** - Reduces query time
2. **Handle reorgs** - Events can be reverted in chain reorganizations
3. **Batch historical queries** - Paginate large event ranges
4. **Implement retry logic** - Network issues can cause missed events
5. **Store processed events** - Track which events have been handled

---

## Next Steps

- [Contract API](contract-api.md) - Full API reference
- [Monitoring Guide](../guides/monitoring.md) - Production monitoring
- [Examples](../examples/basic-usage.md) - Working examples
