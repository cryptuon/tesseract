# Monitoring

Set up monitoring and alerting for Tesseract deployments.

---

## Overview

Effective monitoring is critical for production Tesseract deployments:

- **Health Checks**: Verify contracts are responsive
- **Event Monitoring**: Track transaction lifecycle
- **Metrics Collection**: Measure performance
- **Alerting**: Notify on issues

---

## Health Monitoring

### Basic Health Check

```python
from web3 import Web3
import time

class HealthChecker:
    """Monitor Tesseract contract health."""

    def __init__(self, rpc_url: str, contract_address: str, abi: list):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract = self.w3.eth.contract(address=contract_address, abi=abi)

    def check_connectivity(self) -> bool:
        """Check if node is connected."""
        return self.w3.is_connected()

    def check_contract_exists(self) -> bool:
        """Verify contract code exists."""
        code = self.w3.eth.get_code(self.contract.address)
        return len(code) > 0

    def check_owner(self) -> str:
        """Get contract owner."""
        return self.contract.functions.owner().call()

    def check_paused(self) -> bool:
        """Check if contract is paused."""
        try:
            return self.contract.functions.paused().call()
        except:
            return False

    def get_transaction_count(self) -> int:
        """Get total transaction count."""
        return self.contract.functions.transaction_count().call()

    def full_health_check(self) -> dict:
        """Run full health check."""
        return {
            'timestamp': int(time.time()),
            'connected': self.check_connectivity(),
            'contract_exists': self.check_contract_exists(),
            'owner': self.check_owner(),
            'paused': self.check_paused(),
            'transaction_count': self.get_transaction_count(),
            'block_number': self.w3.eth.block_number
        }
```

### Scheduled Health Checks

```python
import schedule
import json

def run_health_checks():
    """Run and log health checks."""

    checker = HealthChecker(RPC_URL, CONTRACT_ADDRESS, ABI)
    result = checker.full_health_check()

    # Log results
    print(json.dumps(result, indent=2))

    # Alert on issues
    if not result['connected']:
        send_alert("Tesseract node disconnected!")
    if result['paused']:
        send_alert("Tesseract contract is paused!")

    return result

# Schedule every minute
schedule.every(1).minutes.do(run_health_checks)

while True:
    schedule.run_pending()
    time.sleep(1)
```

---

## Event Monitoring

### Real-Time Event Tracker

```python
class EventTracker:
    """Track and store Tesseract events."""

    def __init__(self, contract):
        self.contract = contract
        self.events = []

    def start_tracking(self):
        """Start tracking events."""

        buffered_filter = self.contract.events.TransactionBuffered.createFilter(
            fromBlock='latest'
        )
        ready_filter = self.contract.events.TransactionReady.createFilter(
            fromBlock='latest'
        )
        failed_filter = self.contract.events.TransactionFailed.createFilter(
            fromBlock='latest'
        )

        while True:
            # Process buffered
            for event in buffered_filter.get_new_entries():
                self._record_event('buffered', event)

            # Process ready
            for event in ready_filter.get_new_entries():
                self._record_event('ready', event)

            # Process failed
            for event in failed_filter.get_new_entries():
                self._record_event('failed', event)
                self._alert_failure(event)

            time.sleep(2)

    def _record_event(self, event_type: str, event):
        """Record an event."""
        record = {
            'type': event_type,
            'timestamp': int(time.time()),
            'block': event.blockNumber,
            'tx_hash': event.transactionHash.hex(),
            'args': dict(event.args)
        }
        self.events.append(record)
        print(f"Event: {event_type} - {event.args.tx_id.hex()[:16]}...")

    def _alert_failure(self, event):
        """Alert on failed transaction."""
        reason = event.args.reason if hasattr(event.args, 'reason') else 'Unknown'
        send_alert(f"Transaction failed: {event.args.tx_id.hex()[:16]}... Reason: {reason}")
```

---

## Metrics Collection

### Prometheus Metrics

```python
from prometheus_client import start_http_server, Counter, Gauge, Histogram

# Define metrics
TRANSACTIONS_BUFFERED = Counter(
    'tesseract_transactions_buffered_total',
    'Total transactions buffered'
)

TRANSACTIONS_READY = Counter(
    'tesseract_transactions_ready_total',
    'Total transactions ready'
)

TRANSACTIONS_FAILED = Counter(
    'tesseract_transactions_failed_total',
    'Total transactions failed'
)

TRANSACTION_COUNT = Gauge(
    'tesseract_transaction_count',
    'Current transaction count'
)

RESOLUTION_TIME = Histogram(
    'tesseract_resolution_time_seconds',
    'Time from buffer to ready'
)


class MetricsCollector:
    """Collect and expose Prometheus metrics."""

    def __init__(self, contract, port: int = 8000):
        self.contract = contract
        self.buffer_times = {}

        # Start metrics server
        start_http_server(port)
        print(f"Metrics server started on port {port}")

    def on_buffered(self, event):
        tx_id = event.args.tx_id.hex()
        self.buffer_times[tx_id] = time.time()
        TRANSACTIONS_BUFFERED.inc()

    def on_ready(self, event):
        tx_id = event.args.tx_id.hex()
        if tx_id in self.buffer_times:
            duration = time.time() - self.buffer_times[tx_id]
            RESOLUTION_TIME.observe(duration)
            del self.buffer_times[tx_id]
        TRANSACTIONS_READY.inc()

    def on_failed(self, event):
        tx_id = event.args.tx_id.hex()
        if tx_id in self.buffer_times:
            del self.buffer_times[tx_id]
        TRANSACTIONS_FAILED.inc()

    def update_gauge(self):
        count = self.contract.functions.transaction_count().call()
        TRANSACTION_COUNT.set(count)
```

### Grafana Dashboard

Example dashboard JSON:

```json
{
  "title": "Tesseract Monitoring",
  "panels": [
    {
      "title": "Transaction Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(tesseract_transactions_buffered_total[5m])",
          "legendFormat": "Buffered"
        },
        {
          "expr": "rate(tesseract_transactions_ready_total[5m])",
          "legendFormat": "Ready"
        }
      ]
    },
    {
      "title": "Failed Transactions",
      "type": "stat",
      "targets": [
        {
          "expr": "tesseract_transactions_failed_total"
        }
      ]
    },
    {
      "title": "Resolution Time (p99)",
      "type": "gauge",
      "targets": [
        {
          "expr": "histogram_quantile(0.99, tesseract_resolution_time_seconds_bucket)"
        }
      ]
    }
  ]
}
```

---

## Alerting

### Alert Manager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'tesseract-alerts'

receivers:
  - name: 'tesseract-alerts'
    webhook_configs:
      - url: 'http://localhost:5000/alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#tesseract-alerts'
```

### Alert Rules

```yaml
# prometheus_rules.yml
groups:
  - name: tesseract
    rules:
      - alert: TesseractHighFailureRate
        expr: rate(tesseract_transactions_failed_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High transaction failure rate"
          description: "More than 10% of transactions are failing"

      - alert: TesseractSlowResolution
        expr: histogram_quantile(0.95, tesseract_resolution_time_seconds_bucket) > 60
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow transaction resolution"
          description: "P95 resolution time exceeds 60 seconds"

      - alert: TesseractNodeDisconnected
        expr: up{job="tesseract"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Tesseract node disconnected"
```

### Python Alert Handler

```python
import requests

def send_alert(message: str, severity: str = 'warning'):
    """Send alert to notification service."""

    # Slack webhook
    slack_url = os.environ.get('SLACK_WEBHOOK_URL')
    if slack_url:
        requests.post(slack_url, json={
            'text': f"[{severity.upper()}] {message}",
            'icon_emoji': ':warning:' if severity == 'warning' else ':fire:'
        })

    # PagerDuty
    if severity == 'critical':
        pd_key = os.environ.get('PAGERDUTY_KEY')
        if pd_key:
            requests.post(
                'https://events.pagerduty.com/v2/enqueue',
                json={
                    'routing_key': pd_key,
                    'event_action': 'trigger',
                    'payload': {
                        'summary': message,
                        'severity': severity,
                        'source': 'tesseract-monitor'
                    }
                }
            )
```

---

## Logging

### Structured Logging

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name
        }
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        return json.dumps(log_data)

# Configure logging
logger = logging.getLogger('tesseract')
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage
logger.info('Transaction buffered', extra={
    'tx_id': '0x1234...',
    'origin': '0xaaaa...',
    'target': '0xbbbb...'
})
```

---

## Dashboard Summary

Key metrics to display:

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Transactions/min | Buffer rate | < 1 for 5min |
| Success Rate | Ready / Buffered | < 95% |
| Resolution Time (p95) | Buffer to Ready | > 60s |
| Failed Transactions | Total failures | Any new failure |
| Node Status | Connected/Disconnected | Disconnected |

---

## Next Steps

- [Troubleshooting](troubleshooting.md) - Debug common issues
- [Deployment](deployment.md) - Deployment best practices
- [Security](../concepts/security-model.md) - Security monitoring
