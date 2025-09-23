#!/usr/bin/env python3
"""
Simple Tesseract Deployment Script
A minimal deployment script that works with the Poetry environment
"""

import json
import time
from web3 import Web3
from vyper import compile_code
from pathlib import Path
import os

def compile_contract():
    """Compile the Vyper contract"""
    print("📦 Compiling Tesseract contract...")

    contract_path = Path("contracts/TesseractSimple.vy")
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    with open(contract_path, 'r') as f:
        source_code = f.read()

    # Compile contract
    compiled = compile_code(source_code, output_formats=['bytecode', 'abi'])

    print("✅ Contract compiled successfully!")
    return compiled['bytecode'], compiled['abi']

def deploy_to_local():
    """Deploy to local hardhat network"""
    print("🌐 Deploying to local network...")

    # Connect to local network
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

    if not w3.is_connected():
        print("❌ Cannot connect to local network")
        print("💡 Start local network with: npx hardhat node")
        return None

    print(f"📡 Connected to network (Chain ID: {w3.eth.chain_id})")

    # Get deployer account
    accounts = w3.eth.accounts
    if not accounts:
        print("❌ No accounts available")
        return None

    deployer = accounts[0]
    balance = w3.eth.get_balance(deployer)
    print(f"👤 Deployer: {deployer}")
    print(f"💰 Balance: {w3.from_wei(balance, 'ether')} ETH")

    # Compile contract
    bytecode, abi = compile_contract()

    # Create contract instance
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Deploy contract
    print("🚀 Deploying contract...")
    tx_hash = contract.constructor().transact({'from': deployer})

    # Wait for transaction
    print(f"⏳ Waiting for transaction: {tx_hash.hex()}")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if tx_receipt.status == 1:
        print("✅ Contract deployed successfully!")
        contract_address = tx_receipt.contractAddress
        print(f"📍 Contract address: {contract_address}")
        print(f"⛽ Gas used: {tx_receipt.gasUsed:,}")

        # Save deployment info
        deployment_info = {
            'network': 'local',
            'contract_address': contract_address,
            'deployer': deployer,
            'transaction_hash': tx_hash.hex(),
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'abi': abi,
            'deployment_time': int(time.time())
        }

        os.makedirs('deployments', exist_ok=True)
        with open('deployments/local_deployment.json', 'w') as f:
            json.dump(deployment_info, f, indent=2)

        print("💾 Deployment info saved to deployments/local_deployment.json")

        return w3.eth.contract(address=contract_address, abi=abi)
    else:
        print("❌ Deployment failed!")
        return None

def test_basic_functionality(contract, w3):
    """Test basic contract functionality"""
    print("\n🧪 Testing basic functionality...")

    deployer = w3.eth.accounts[0]
    operator = w3.eth.accounts[1] if len(w3.eth.accounts) > 1 else deployer

    try:
        # Check initial state
        owner = contract.functions.owner().call()
        print(f"👑 Contract owner: {owner}")

        coordination_window = contract.functions.coordination_window().call()
        print(f"⏱️  Coordination window: {coordination_window} seconds")

        # Add operator
        if operator != deployer:
            print(f"👥 Adding operator: {operator}")
            tx_hash = contract.functions.add_operator(operator).transact({'from': deployer})
            w3.eth.wait_for_transaction_receipt(tx_hash)
            print("✅ Operator added")

        # Test transaction buffering
        print("📦 Testing transaction buffering...")

        tx_id = b'\x01' * 32  # Simple test transaction ID
        origin_rollup = deployer
        target_rollup = operator
        payload = b"test payload"
        dependency_tx_id = b'\x00' * 32  # No dependency
        timestamp = int(time.time()) + 10  # 10 seconds from now

        tx_hash = contract.functions.buffer_transaction(
            tx_id,
            origin_rollup,
            target_rollup,
            payload,
            dependency_tx_id,
            timestamp
        ).transact({'from': operator})

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"✅ Transaction buffered (Gas: {receipt.gasUsed:,})")

        # Check transaction state
        state = contract.functions.get_transaction_state(tx_id).call()
        print(f"📊 Transaction state: {state} (1=BUFFERED)")

        # Check transaction count
        count = contract.functions.transaction_count().call()
        print(f"📈 Total transactions: {count}")

        # Test dependency resolution
        print("🔄 Testing dependency resolution...")
        tx_hash = contract.functions.resolve_dependency(tx_id).transact({'from': operator})
        w3.eth.wait_for_transaction_receipt(tx_hash)

        # Check if ready
        is_ready = contract.functions.is_transaction_ready(tx_id).call()
        state = contract.functions.get_transaction_state(tx_id).call()
        print(f"🎯 Transaction ready: {is_ready}")
        print(f"📊 Transaction state: {state} (4=READY)")

        print("\n🎉 All tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main deployment function"""
    print("🚀 Tesseract Simple Deployment")
    print("=" * 40)

    try:
        # Deploy contract
        contract = deploy_to_local()
        if not contract:
            return

        # Test functionality
        w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
        success = test_basic_functionality(contract, w3)

        if success:
            print("\n✅ Deployment and testing completed successfully!")
            print("\n🎯 Next steps:")
            print("1. Deploy to testnet with real API keys")
            print("2. Set up monitoring and alerts")
            print("3. Test cross-rollup functionality")
        else:
            print("\n❌ Some tests failed - check the logs")

    except Exception as e:
        print(f"❌ Deployment failed: {e}")

if __name__ == "__main__":
    main()