# Multi-Chain Setup

Configure Tesseract for cross-chain operations across multiple rollups.

---

## Overview

Tesseract is designed to coordinate transactions across multiple networks. This guide covers:

- Deploying to multiple chains
- Configuring cross-chain operators
- Setting up coordination infrastructure

---

## Network Configuration

### Supported Networks

| Network | Chain ID | RPC Endpoint |
|---------|----------|--------------|
| Ethereum Sepolia | 11155111 | sepolia.infura.io |
| Polygon Mumbai | 80001 | polygon-mumbai.infura.io |
| Arbitrum Goerli | 421613 | arb-goerli.g.alchemy.com |
| Optimism Goerli | 420 | opt-goerli.g.alchemy.com |

### Configuration File

Create `config/networks.json`:

```json
{
  "networks": {
    "sepolia": {
      "chain_id": 11155111,
      "rpc_url": "${SEPOLIA_RPC_URL}",
      "explorer": "https://sepolia.etherscan.io",
      "contract": null
    },
    "mumbai": {
      "chain_id": 80001,
      "rpc_url": "${MUMBAI_RPC_URL}",
      "explorer": "https://mumbai.polygonscan.com",
      "contract": null
    },
    "arbitrum_goerli": {
      "chain_id": 421613,
      "rpc_url": "${ARBITRUM_RPC_URL}",
      "explorer": "https://goerli.arbiscan.io",
      "contract": null
    },
    "optimism_goerli": {
      "chain_id": 420,
      "rpc_url": "${OPTIMISM_RPC_URL}",
      "explorer": "https://goerli-optimism.etherscan.io",
      "contract": null
    }
  }
}
```

---

## Multi-Chain Deployment

### Deploy to All Networks

```python
#!/usr/bin/env python3
"""Deploy Tesseract to all networks."""

import os
import json
from web3 import Web3
import vyper
from dotenv import load_dotenv

load_dotenv()

def load_config():
    with open('config/networks.json', 'r') as f:
        config = json.load(f)

    # Substitute environment variables
    for network in config['networks'].values():
        if network['rpc_url'].startswith('${'):
            env_var = network['rpc_url'][2:-1]
            network['rpc_url'] = os.environ.get(env_var, '')

    return config


def deploy_to_network(network_name: str, config: dict) -> str:
    """Deploy to a single network."""

    rpc_url = config['rpc_url']
    if not rpc_url:
        print(f"Skipping {network_name}: No RPC URL configured")
        return None

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print(f"Skipping {network_name}: Cannot connect")
        return None

    private_key = os.environ['DEPLOYER_PRIVATE_KEY']
    account = w3.eth.account.from_key(private_key)

    # Check balance
    balance = w3.eth.get_balance(account.address)
    if balance < w3.to_wei(0.01, 'ether'):
        print(f"Skipping {network_name}: Insufficient balance")
        return None

    print(f"\nDeploying to {network_name}...")
    print(f"  Account: {account.address}")
    print(f"  Balance: {balance / 1e18:.4f}")

    # Compile
    with open('contracts/TesseractSimple.vy', 'r') as f:
        source = f.read()

    compiled = vyper.compile_code(source, output_formats=['abi', 'bytecode'])

    # Deploy
    Contract = w3.eth.contract(abi=compiled['abi'], bytecode=compiled['bytecode'])

    tx = Contract.constructor().build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price
    })

    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"  Deployed: {receipt.contractAddress}")

    return receipt.contractAddress


def deploy_all():
    """Deploy to all configured networks."""

    config = load_config()
    deployments = {}

    for network_name, network_config in config['networks'].items():
        try:
            address = deploy_to_network(network_name, network_config)
            if address:
                deployments[network_name] = {
                    'address': address,
                    'chain_id': network_config['chain_id'],
                    'explorer': network_config['explorer']
                }
        except Exception as e:
            print(f"Failed to deploy to {network_name}: {e}")

    # Save deployments
    with open('artifacts/multi-chain-deployments.json', 'w') as f:
        json.dump(deployments, f, indent=2)

    print("\n=== Deployment Summary ===")
    for network, info in deployments.items():
        print(f"{network}: {info['address']}")

    return deployments


if __name__ == "__main__":
    deploy_all()
```

---

## Operator Configuration

### Add Operators to All Networks

```python
def add_operators_all_networks(operator_address: str):
    """Add operator to all deployed contracts."""

    with open('artifacts/multi-chain-deployments.json', 'r') as f:
        deployments = json.load(f)

    with open('artifacts/TesseractSimple.json', 'r') as f:
        abi = json.load(f)['abi']

    config = load_config()
    private_key = os.environ['DEPLOYER_PRIVATE_KEY']

    for network_name, deployment in deployments.items():
        print(f"\nAdding operator on {network_name}...")

        rpc_url = config['networks'][network_name]['rpc_url']
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        account = w3.eth.account.from_key(private_key)

        contract = w3.eth.contract(
            address=deployment['address'],
            abi=abi
        )

        tx = contract.functions.add_operator(operator_address).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)

        print(f"  Operator added: {operator_address}")
```

---

## Cross-Chain Coordinator

### Coordinator Service

```python
import asyncio
from web3 import Web3
import json

class CrossChainCoordinator:
    """Coordinates transactions across multiple chains."""

    def __init__(self, config_path: str = 'artifacts/multi-chain-deployments.json'):
        with open(config_path, 'r') as f:
            self.deployments = json.load(f)

        with open('artifacts/TesseractSimple.json', 'r') as f:
            self.abi = json.load(f)['abi']

        self.clients = {}
        self._init_clients()

    def _init_clients(self):
        """Initialize Web3 clients for each network."""
        config = load_config()

        for network, deployment in self.deployments.items():
            rpc_url = config['networks'][network]['rpc_url']
            w3 = Web3(Web3.HTTPProvider(rpc_url))

            self.clients[network] = {
                'w3': w3,
                'contract': w3.eth.contract(
                    address=deployment['address'],
                    abi=self.abi
                )
            }

    def get_contract(self, network: str):
        """Get contract instance for network."""
        return self.clients[network]['contract']

    def buffer_cross_chain(
        self,
        origin_network: str,
        target_network: str,
        tx_id: bytes,
        payload: bytes,
        operator_key: str
    ):
        """Buffer a cross-chain transaction."""

        origin = self.clients[origin_network]
        target_address = self.deployments[target_network]['address']

        w3 = origin['w3']
        contract = origin['contract']
        account = w3.eth.account.from_key(operator_key)

        tx = contract.functions.buffer_transaction(
            tx_id,
            contract.address,  # Origin
            target_address,    # Target
            payload,
            b'\x00' * 32,      # No dependency
            int(time.time()) + 60
        ).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        signed = w3.eth.account.sign_transaction(tx, operator_key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

        return w3.eth.wait_for_transaction_receipt(tx_hash)

    def sync_status(self):
        """Get status across all networks."""

        status = {}
        for network, client in self.clients.items():
            contract = client['contract']
            status[network] = {
                'address': contract.address,
                'owner': contract.functions.owner().call(),
                'tx_count': contract.functions.transaction_count().call(),
                'connected': client['w3'].is_connected()
            }
        return status
```

---

## Event Aggregation

### Multi-Chain Event Monitor

```python
class MultiChainEventMonitor:
    """Monitor events across all chains."""

    def __init__(self, coordinator: CrossChainCoordinator):
        self.coordinator = coordinator
        self.event_handlers = []

    def add_handler(self, handler):
        self.event_handlers.append(handler)

    def _process_event(self, network: str, event_type: str, event):
        """Process a single event."""
        event_data = {
            'network': network,
            'type': event_type,
            'tx_id': event.args.tx_id.hex() if hasattr(event.args, 'tx_id') else None,
            'block': event.blockNumber,
            'raw': dict(event.args)
        }

        for handler in self.event_handlers:
            handler(event_data)

    def start(self):
        """Start monitoring all chains."""

        filters = {}

        for network, client in self.coordinator.clients.items():
            contract = client['contract']
            filters[network] = {
                'buffered': contract.events.TransactionBuffered.createFilter(
                    fromBlock='latest'
                ),
                'ready': contract.events.TransactionReady.createFilter(
                    fromBlock='latest'
                ),
                'failed': contract.events.TransactionFailed.createFilter(
                    fromBlock='latest'
                )
            }

        print("Monitoring events on all chains...")

        while True:
            for network, network_filters in filters.items():
                for event_type, filter in network_filters.items():
                    for event in filter.get_new_entries():
                        self._process_event(network, event_type, event)

            time.sleep(2)


# Usage
coordinator = CrossChainCoordinator()
monitor = MultiChainEventMonitor(coordinator)

def log_event(event):
    print(f"[{event['network']}] {event['type']}: {event['tx_id'][:16]}...")

monitor.add_handler(log_event)
monitor.start()
```

---

## Health Monitoring

### Multi-Chain Health Check

```python
def health_check_all():
    """Check health of all deployments."""

    coordinator = CrossChainCoordinator()
    status = coordinator.sync_status()

    print("\n=== Multi-Chain Health Check ===\n")

    all_healthy = True
    for network, info in status.items():
        healthy = info['connected']
        status_icon = "OK" if healthy else "FAIL"

        print(f"{network}:")
        print(f"  Status: {status_icon}")
        print(f"  Address: {info['address']}")
        print(f"  Owner: {info['owner']}")
        print(f"  Transactions: {info['tx_count']}")
        print()

        if not healthy:
            all_healthy = False

    return all_healthy
```

---

## Best Practices

1. **Use same operator keys** across all networks for simplicity
2. **Monitor all chains** with unified event aggregation
3. **Test cross-chain flows** on testnets before production
4. **Implement alerting** for failed cross-chain transactions
5. **Document network-specific** gas and timing considerations

---

## Next Steps

- [Monitoring](monitoring.md) - Production monitoring setup
- [Troubleshooting](troubleshooting.md) - Common issues
- [Examples](../examples/cross-chain-defi.md) - Cross-chain examples
