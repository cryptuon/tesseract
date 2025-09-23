# Tesseract Deployment Guide - Updated for Working System

## Overview

This updated deployment guide reflects the current working state of Tesseract with the simplified TesseractSimple.vy contract and Poetry-based environment.

## Prerequisites

### System Requirements
- Python 3.11+
- Poetry (for dependency management)
- Git
- At least 2GB RAM

### Required Setup
- Testnet funds (for deployment)
- RPC provider API key (Alchemy, Infura, etc.)

## Step 1: Environment Setup

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/tesseract.git
cd tesseract

# Install dependencies using Poetry
poetry install

# Verify installation
poetry run python --version
poetry run python -c "import vyper; print(f'Vyper: {vyper.__version__}')"
```

### Verify Contract Compilation

```bash
# Test contract compilation
poetry run python scripts/test_compilation.py

# Expected output:
# Compilation successful!
# Bytecode length: 7,276 bytes
# ABI functions: 18 items
```

## Step 2: Local Development Testing

### Start Local Network (Optional)

```bash
# Option 1: Use Hardhat
npx hardhat node

# Option 2: Use Ganache
ganache-cli --deterministic --accounts 10 --host 0.0.0.0
```

### Test Local Deployment

```bash
# Deploy to local network
poetry run python scripts/deploy_simple.py

# Expected output:
# Deploying to local network...
# Contract deployed successfully!
# Contract address: 0x...
```

## Step 3: Testnet Deployment

### Configure for Testnet

Create `scripts/deploy_testnet.py`:

```python
#!/usr/bin/env python3
"""
Testnet deployment script for Tesseract
"""

import json
import os
from web3 import Web3
from vyper import compile_code
from pathlib import Path
from eth_account import Account

def deploy_to_testnet():
    """Deploy to testnet (Sepolia example)"""

    # Configuration
    RPC_URL = "https://sepolia.infura.io/v3/YOUR_API_KEY"  # Replace with your RPC
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # Load from environment

    if not PRIVATE_KEY:
        print("Please set PRIVATE_KEY environment variable")
        return

    # Connect to network
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("Cannot connect to network")
        return

    account = Account.from_key(PRIVATE_KEY)
    deployer = account.address

    print(f"Connected to network (Chain ID: {w3.eth.chain_id})")
    print(f"Deployer: {deployer}")

    # Check balance
    balance = w3.eth.get_balance(deployer)
    balance_eth = w3.from_wei(balance, 'ether')
    print(f"Balance: {balance_eth:.4f} ETH")

    if balance_eth < 0.01:
        print("Warning: Low balance - may need more testnet ETH")

    # Compile contract
    contract_path = Path("contracts/TesseractSimple.vy")
    with open(contract_path, 'r') as f:
        source_code = f.read()

    print("Compiling contract...")
    compiled = compile_code(source_code, output_formats=['bytecode', 'abi'])

    # Create contract instance
    contract = w3.eth.contract(abi=compiled['abi'], bytecode=compiled['bytecode'])

    # Estimate gas
    gas_estimate = contract.constructor().estimate_gas()
    gas_price = w3.eth.gas_price

    print(f"Estimated gas: {gas_estimate:,}")
    print(f"Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
    print(f"Estimated cost: {w3.from_wei(gas_estimate * gas_price, 'ether'):.6f} ETH")

    # Deploy contract
    print("Deploying contract...")

    # Build transaction
    constructor_tx = contract.constructor().build_transaction({
        'from': deployer,
        'gas': gas_estimate + 50000,  # Add buffer
        'gasPrice': gas_price,
        'nonce': w3.eth.get_transaction_count(deployer),
    })

    # Sign and send transaction
    signed_tx = account.sign_transaction(constructor_tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"Waiting for transaction: {tx_hash.hex()}")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if tx_receipt.status == 1:
        print("Contract deployed successfully!")
        contract_address = tx_receipt.contractAddress
        print(f"Contract address: {contract_address}")
        print(f"Gas used: {tx_receipt.gasUsed:,}")
        print(f"Block number: {tx_receipt.blockNumber}")

        # Save deployment info
        deployment_info = {
            'network': 'sepolia',
            'chain_id': w3.eth.chain_id,
            'contract_address': contract_address,
            'deployer': deployer,
            'transaction_hash': tx_hash.hex(),
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'abi': compiled['abi'],
            'bytecode': compiled['bytecode']
        }

        os.makedirs('deployments', exist_ok=True)
        with open('deployments/sepolia_deployment.json', 'w') as f:
            json.dump(deployment_info, f, indent=2)

        print("Deployment info saved to deployments/sepolia_deployment.json")

        # Test basic functionality
        test_contract_functions(w3, contract_address, compiled['abi'], account)

        return contract_address
    else:
        print("Deployment failed!")
        return None

def test_contract_functions(w3, contract_address, abi, account):
    """Test basic contract functions after deployment"""
    print("\nTesting contract functions...")

    contract = w3.eth.contract(address=contract_address, abi=abi)

    try:
        # Test view functions
        owner = contract.functions.owner().call()
        coordination_window = contract.functions.coordination_window().call()
        transaction_count = contract.functions.transaction_count().call()

        print(f"Owner: {owner}")
        print(f"Coordination window: {coordination_window} seconds")
        print(f"Transaction count: {transaction_count}")

        # Test operator addition (if caller is owner)
        if owner.lower() == account.address.lower():
            print("Testing operator addition...")

            # Add deployer as operator
            tx = contract.functions.add_operator(account.address).build_transaction({
                'from': account.address,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })

            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                print("Operator added successfully")
            else:
                print("Failed to add operator")

        print("Contract functions working correctly!")

    except Exception as e:
        print(f"Function test failed: {e}")

if __name__ == "__main__":
    deploy_to_testnet()
```

### Get Testnet Funds

**Ethereum Sepolia:**
- Faucet: https://sepoliafaucet.com/
- Amount needed: ~0.05 ETH

**Polygon Mumbai:**
- Faucet: https://faucet.polygon.technology/
- Amount needed: ~1 MATIC

### Deploy to Testnet

```bash
# Set environment variables
export PRIVATE_KEY="0x..."  # Your private key
export RPC_URL="https://sepolia.infura.io/v3/YOUR_API_KEY"

# Deploy to testnet
poetry run python scripts/deploy_testnet.py
```

## Step 4: Verify Deployment

### Check Contract on Etherscan

1. Go to https://sepolia.etherscan.io/
2. Search for your contract address
3. Verify the contract is deployed correctly

### Test Contract Interaction

```python
# test_deployed_contract.py
import json
from web3 import Web3
from pathlib import Path

def test_deployed_contract():
    # Load deployment info
    with open('deployments/sepolia_deployment.json', 'r') as f:
        deployment = json.load(f)

    # Connect to network
    w3 = Web3(Web3.HTTPProvider("YOUR_RPC_URL"))
    contract = w3.eth.contract(
        address=deployment['contract_address'],
        abi=deployment['abi']
    )

    # Test basic functions
    print(f"Owner: {contract.functions.owner().call()}")
    print(f"Coordination window: {contract.functions.coordination_window().call()}")
    print(f"Transaction count: {contract.functions.transaction_count().call()}")

if __name__ == "__main__":
    test_deployed_contract()
```

## Step 5: Multi-Network Deployment

### Deploy to Multiple Testnets

Create `scripts/deploy_multi_testnet.py`:

```python
#!/usr/bin/env python3
"""
Multi-testnet deployment script
"""

import json
import os
from web3 import Web3
from vyper import compile_code
from pathlib import Path
from eth_account import Account

# Network configurations
NETWORKS = {
    'sepolia': {
        'name': 'Ethereum Sepolia',
        'rpc_url': 'https://sepolia.infura.io/v3/YOUR_API_KEY',
        'chain_id': 11155111,
        'explorer': 'https://sepolia.etherscan.io'
    },
    'mumbai': {
        'name': 'Polygon Mumbai',
        'rpc_url': 'https://polygon-mumbai.infura.io/v3/YOUR_API_KEY',
        'chain_id': 80001,
        'explorer': 'https://mumbai.polygonscan.com'
    }
}

def deploy_to_all_networks():
    """Deploy to all configured testnets"""
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("Please set PRIVATE_KEY environment variable")
        return

    account = Account.from_key(private_key)
    deployments = {}

    # Compile contract once
    contract_path = Path("contracts/TesseractSimple.vy")
    with open(contract_path, 'r') as f:
        source_code = f.read()

    compiled = compile_code(source_code, output_formats=['bytecode', 'abi'])

    for network_name, config in NETWORKS.items():
        print(f"\nDeploying to {config['name']}...")

        try:
            # Connect to network
            w3 = Web3(Web3.HTTPProvider(config['rpc_url']))
            if not w3.is_connected():
                print(f"Cannot connect to {network_name}")
                continue

            deployer = account.address
            balance = w3.eth.get_balance(deployer)
            balance_eth = w3.from_wei(balance, 'ether')

            print(f"Deployer: {deployer}")
            print(f"Balance: {balance_eth:.4f} ETH")

            if balance_eth < 0.01:
                print(f"Insufficient balance on {network_name}")
                continue

            # Deploy contract
            contract = w3.eth.contract(abi=compiled['abi'], bytecode=compiled['bytecode'])
            gas_estimate = contract.constructor().estimate_gas()

            constructor_tx = contract.constructor().build_transaction({
                'from': deployer,
                'gas': gas_estimate + 50000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(deployer),
            })

            signed_tx = account.sign_transaction(constructor_tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            print(f"Waiting for transaction...")
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

            if tx_receipt.status == 1:
                contract_address = tx_receipt.contractAddress
                print(f"Deployed to {network_name}: {contract_address}")
                print(f"Explorer: {config['explorer']}/address/{contract_address}")

                deployments[network_name] = {
                    'network': config['name'],
                    'chain_id': config['chain_id'],
                    'contract_address': contract_address,
                    'transaction_hash': tx_hash.hex(),
                    'explorer_url': f"{config['explorer']}/address/{contract_address}"
                }
            else:
                print(f"Deployment to {network_name} failed")

        except Exception as e:
            print(f"Error deploying to {network_name}: {e}")

    # Save all deployments
    if deployments:
        with open('deployments/multi_testnet_deployments.json', 'w') as f:
            json.dump(deployments, f, indent=2)

        print(f"\nAll deployments saved to deployments/multi_testnet_deployments.json")
        print("\nMulti-network deployment completed!")

        # Print summary
        print("\nDeployment Summary:")
        for network, info in deployments.items():
            print(f"  {info['network']}: {info['contract_address']}")

if __name__ == "__main__":
    deploy_to_all_networks()
```

## Step 6: Post-Deployment Verification

### Contract Verification on Etherscan

1. Go to your contract on Etherscan
2. Click "Contract" tab
3. Click "Verify and Publish"
4. Choose "Vyper" compiler
5. Upload your source code
6. Complete verification

### Monitoring Setup

Create `scripts/monitor_contract.py`:

```python
#!/usr/bin/env python3
"""
Basic contract monitoring script
"""

import json
import time
from web3 import Web3

def monitor_contract():
    """Monitor contract events and state"""

    # Load deployment info
    with open('deployments/sepolia_deployment.json', 'r') as f:
        deployment = json.load(f)

    # Connect to network
    w3 = Web3(Web3.HTTPProvider("YOUR_RPC_URL"))
    contract = w3.eth.contract(
        address=deployment['contract_address'],
        abi=deployment['abi']
    )

    print(f"Monitoring contract: {deployment['contract_address']}")

    # Monitor events
    event_filter = contract.events.TransactionBuffered.create_filter(fromBlock='latest')

    while True:
        try:
            # Check for new events
            for event in event_filter.get_new_entries():
                print(f"New transaction buffered:")
                print(f"   TX ID: {event.args.tx_id.hex()}")
                print(f"   Origin: {event.args.origin_rollup}")
                print(f"   Target: {event.args.target_rollup}")
                print(f"   Timestamp: {event.args.timestamp}")

            # Check contract state
            tx_count = contract.functions.transaction_count().call()
            print(f"Current transaction count: {tx_count}")

            time.sleep(10)

        except KeyboardInterrupt:
            print("\nMonitoring stopped")
            break
        except Exception as e:
            print(f"Monitoring error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    monitor_contract()
```

## Common Issues and Solutions

### 1. Compilation Errors
```bash
# Clear any cached compilation
rm -rf artifacts/

# Recompile
poetry run python scripts/test_compilation.py
```

### 2. Deployment Failures
```bash
# Check network connection
poetry run python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('YOUR_RPC')); print(w3.is_connected())"

# Check account balance
# Ensure you have sufficient testnet ETH
```

### 3. Transaction Failures
```bash
# Check gas estimation
# Increase gas limit if needed
# Verify contract ABI matches deployed contract
```

## Security Checklist

### Pre-Deployment
- [ ] Contract compilation successful
- [ ] Basic functionality tested
- [ ] Access controls verified
- [ ] Input validation checked

### Post-Deployment
- [ ] Contract address saved securely
- [ ] Private keys secured
- [ ] Monitoring configured
- [ ] Backup procedures documented

## Next Steps

1. **Enhanced Testing**: Test cross-rollup functionality
2. **Monitoring**: Set up comprehensive monitoring
3. **Documentation**: Update API docs with actual contract
4. **Security**: Schedule professional audit
5. **Optimization**: Gas optimization review

This deployment guide reflects the current working state of Tesseract and provides practical steps for real deployment.