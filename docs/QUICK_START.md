# Tesseract Quick Start Guide

## Overview

This guide will help you quickly deploy and test the Tesseract cross-rollup transaction coordination system on testnet networks.

## Prerequisites

- Python 3.11+
- Git
- Node.js 18+ (optional, for additional tooling)

## Step 1: Environment Setup

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/tesseract.git
cd tesseract

# Install dependencies using Poetry
poetry install

# Activate the virtual environment
poetry shell

# Install required Ape plugins
ape plugins install vyper alchemy hardhat
```

### Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your configuration
nano .env
```

**Minimum required configuration:**
```bash
# Get your Alchemy API key from https://dashboard.alchemy.com/
ALCHEMY_API_KEY=your_alchemy_api_key_here

# For testnet deployment, you can generate test private keys
# NEVER use these keys on mainnet!
DEPLOYER_PRIVATE_KEY=0x...
OPERATOR_PRIVATE_KEY=0x...
```

### Generate Test Accounts (Recommended)

```bash
# Generate deployer account
ape accounts generate deployer

# Generate operator account
ape accounts generate operator

# Generate resolver account
ape accounts generate resolver
```

## Step 2: Get Testnet Funds

You'll need testnet ETH on the networks you want to deploy to:

### Ethereum Sepolia
- Faucet: https://sepoliafaucet.com/
- Amount needed: ~0.1 ETH

### Polygon Mumbai
- Faucet: https://faucet.polygon.technology/
- Amount needed: ~1 MATIC

### Arbitrum Goerli
- Faucet: https://bridge.arbitrum.io/
- Amount needed: ~0.1 ETH

### Optimism Goerli
- Faucet: https://app.optimism.io/bridge
- Amount needed: ~0.1 ETH

## Step 3: Deploy to Single Network (Sepolia)

```bash
# Compile contracts
ape compile

# Deploy to Sepolia
ape run scripts/deploy.py --network ethereum:sepolia:alchemy

# Initialize the contract
ape run scripts/initialize.py --network ethereum:sepolia:alchemy
```

Expected output:
```
Starting Tesseract deployment...
Deployer address: 0x...
Deploying to network: sepolia
Compiling and deploying TesseractBuffer...
Contract deployed successfully!
Contract address: 0x...
```

## Step 4: Test Basic Functionality

Create a test script to verify deployment:

```python
# test_deployment.py
from ape import networks, accounts, Contract
from hexbytes import HexBytes
import time

def test_basic_functionality():
    with networks.ethereum.sepolia.alchemy:
        # Load accounts
        operator = accounts.load("operator")

        # Load deployed contract
        # Replace with your actual contract address
        contract = Contract("0x...")

        # Test transaction buffering
        tx_id = HexBytes("0x" + "1" * 64)

        receipt = contract.buffer_transaction(
            tx_id,
            operator.address,
            "0x" + "a" * 40,  # target rollup
            b"test payload",
            HexBytes("0x" + "0" * 64),  # no dependency
            int(time.time()) + 60,  # 1 minute from now
            sender=operator
        )

        print(f"Transaction buffered: {receipt.txn_hash}")

        # Check if transaction exists
        tx_data = contract.get_transaction(tx_id)
        print(f"Transaction state: {tx_data.state}")

        # Try to resolve dependency
        contract.resolve_dependency(tx_id, sender=operator)

        # Check if ready
        ready = contract.is_transaction_ready(tx_id)
        print(f"Transaction ready: {ready}")

if __name__ == "__main__":
    test_basic_functionality()
```

Run the test:
```bash
ape run test_deployment.py --network ethereum:sepolia:alchemy
```

## Step 5: Multi-Chain Deployment (Optional)

Deploy to all testnets simultaneously:

```bash
# Deploy to all configured testnets
ape run scripts/deploy_multichain.py

# Initialize all deployments
bash scripts/initialize_all.sh
```

## Step 6: Monitor Your Deployment

### Check Contract Status

```python
# monitor.py
from ape import networks, Contract

def check_contract_status(contract_address):
    with networks.ethereum.sepolia.alchemy:
        contract = Contract(contract_address)

        print(f"Contract: {contract_address}")
        print(f"Owner: {contract.owner()}")
        print(f"Transaction count: {contract.transaction_count()}")
        print(f"Paused: {contract.paused()}")
        print(f"🔄 Circuit breaker active: {contract.circuit_breaker_active()}")

if __name__ == "__main__":
    check_contract_status("0x...")  # Your contract address
```

### Monitor Events

```python
# event_monitor.py
from ape import networks, Contract
import time

def monitor_events(contract_address):
    with networks.ethereum.sepolia.alchemy:
        contract = Contract(contract_address)

        # Monitor new transactions
        event_filter = contract.TransactionBuffered.createFilter(fromBlock='latest')

        print("🔍 Monitoring for new transactions...")

        while True:
            for event in event_filter.get_new_entries():
                print(f"New transaction: {event.tx_id.hex()}")
                print(f"   Origin: {event.origin_rollup}")
                print(f"   Target: {event.target_rollup}")

            time.sleep(10)

if __name__ == "__main__":
    monitor_events("0x...")  # Your contract address
```

## Common Issues and Solutions

### 1. Compilation Errors
```bash
# Clear compilation cache
ape compile --force

# Check Vyper version
vyper --version

# Reinstall vyper plugin
ape plugins install vyper --upgrade
```

### 2. Network Connection Issues
```bash
# Test network connection
ape console --network ethereum:sepolia:alchemy

# In console:
>>> web3.is_connected()
>>> web3.eth.block_number
```

### 3. Account Issues
```bash
# List accounts
ape accounts list

# Check account balance
ape console --network ethereum:sepolia:alchemy
>>> accounts.load("deployer").balance
```

### 4. Gas Estimation Failures
```bash
# Check current gas prices
ape console --network ethereum:sepolia:alchemy
>>> web3.eth.gas_price

# Use manual gas limit
contract.buffer_transaction(..., gas_limit=500000)
```

## Next Steps

1. **Run Tests**: Execute the full test suite
   ```bash
   ape test
   ```

2. **Set Up Monitoring**: Configure alerts and monitoring dashboards

3. **Cross-Chain Testing**: Test transaction coordination across multiple rollups

4. **Security Audit**: Ensure your deployment is secure before mainnet

5. **Documentation**: Read the full documentation in `/docs/`

## Support and Resources

- **Documentation**: `/docs/` directory
- **Examples**: `/examples/` directory
- **Issues**: GitHub issues page
- **Discord**: [Tesseract Community](https://discord.gg/tesseract)

## Security Reminders

**IMPORTANT SECURITY NOTES:**

1. **Never commit private keys** to version control
2. **Use hardware wallets** for mainnet deployments
3. **Test thoroughly** on testnets before mainnet
4. **Keep dependencies updated** and audit regularly
5. **Monitor contracts** continuously for unusual activity

---

**Congratulations!** You now have a working Tesseract deployment on testnet. Continue with the full documentation for advanced features and production deployment.