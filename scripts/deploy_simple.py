#!/usr/bin/env python3
"""
Tesseract Deployment Script
Deploys TesseractBuffer.vy to local or testnet environments
"""

import json
import time
from web3 import Web3
from vyper import compile_code
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Role constants
BUFFER_ROLE = Web3.keccak(text="BUFFER_ROLE")
RESOLVE_ROLE = Web3.keccak(text="RESOLVE_ROLE")
ADMIN_ROLE = Web3.keccak(text="ADMIN_ROLE")


def compile_contract():
    """Compile the Vyper contract"""
    print("Compiling TesseractBuffer contract...")

    contract_path = Path("contracts/TesseractBuffer.vy")
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    with open(contract_path, 'r') as f:
        source_code = f.read()

    # Compile contract
    compiled = compile_code(source_code, output_formats=['bytecode', 'abi'])

    print("[OK] Contract compiled successfully!")
    return compiled['bytecode'], compiled['abi']

def get_network_config(network: str = "local"):
    """Get network configuration"""
    networks = {
        "local": {
            "rpc_url": "http://127.0.0.1:8545",
            "chain_id": 31337,
            "name": "Local Hardhat"
        },
        "sepolia": {
            "rpc_url": f"https://eth-sepolia.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY', '')}",
            "chain_id": 11155111,
            "name": "Ethereum Sepolia"
        },
        "mumbai": {
            "rpc_url": f"https://polygon-mumbai.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY', '')}",
            "chain_id": 80001,
            "name": "Polygon Mumbai"
        }
    }
    return networks.get(network, networks["local"])


def deploy_contract(network: str = "local"):
    """Deploy to specified network"""
    config = get_network_config(network)
    print(f"Deploying to {config['name']}...")

    # Connect to network
    w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))

    if not w3.is_connected():
        print(f"[ERROR] Cannot connect to {config['name']}")
        if network == "local":
            print("Start local network with: npx hardhat node")
        else:
            print("Check your RPC URL and API key")
        return None, None

    print(f"Connected to network (Chain ID: {w3.eth.chain_id})")

    # Get deployer account
    private_key = os.getenv("DEPLOYER_PRIVATE_KEY")
    if private_key and network != "local":
        account = w3.eth.account.from_key(private_key)
        deployer = account.address
    else:
        accounts = w3.eth.accounts
        if not accounts:
            print("[ERROR] No accounts available")
            return None, None
        deployer = accounts[0]
        account = None

    balance = w3.eth.get_balance(deployer)
    print(f"Deployer: {deployer}")
    print(f"Balance: {w3.from_wei(balance, 'ether')} ETH")

    # Compile contract
    bytecode, abi = compile_contract()

    # Create contract instance
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Build deployment transaction
    print("Deploying contract...")

    if account:
        # Sign transaction for testnet
        nonce = w3.eth.get_transaction_count(deployer)
        tx = Contract.constructor().build_transaction({
            'from': deployer,
            'nonce': nonce,
            'gas': 3000000,
            'gasPrice': w3.eth.gas_price
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    else:
        # Direct transact for local
        tx_hash = Contract.constructor().transact({'from': deployer})

    print(f"Waiting for transaction: {tx_hash.hex()}")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if tx_receipt.status == 1:
        print("[OK] Contract deployed successfully!")
        contract_address = tx_receipt.contractAddress
        print(f"Contract address: {contract_address}")
        print(f"Gas used: {tx_receipt.gasUsed:,}")

        # Save deployment info
        deployment_info = {
            'network': network,
            'network_name': config['name'],
            'chain_id': config['chain_id'],
            'contract_name': 'TesseractBuffer',
            'contract_address': contract_address,
            'deployer': deployer,
            'transaction_hash': tx_hash.hex(),
            'block_number': tx_receipt.blockNumber,
            'gas_used': tx_receipt.gasUsed,
            'deployment_time': int(time.time())
        }

        os.makedirs('deployments', exist_ok=True)
        deployment_file = f'deployments/{network}_deployment.json'
        with open(deployment_file, 'w') as f:
            json.dump(deployment_info, f, indent=2)

        # Also save ABI separately
        with open('deployments/TesseractBuffer_abi.json', 'w') as f:
            json.dump(abi, f, indent=2)

        print(f"Deployment info saved to {deployment_file}")

        return w3.eth.contract(address=contract_address, abi=abi), w3
    else:
        print("[ERROR] Deployment failed!")
        return None, None

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
    import sys

    print("Tesseract Deployment Script")
    print("=" * 40)

    # Parse command line arguments
    network = "local"
    if len(sys.argv) > 1:
        network = sys.argv[1]

    print(f"Target network: {network}")

    try:
        # Deploy contract
        contract, w3 = deploy_contract(network)
        if not contract:
            return

        # Test functionality (only on local network)
        if network == "local":
            success = test_basic_functionality(contract, w3)

            if success:
                print("\n[OK] Deployment and testing completed successfully!")
                print("\nNext steps:")
                print("1. Deploy to testnet with real API keys")
                print("2. Set up monitoring and alerts")
                print("3. Test cross-rollup functionality")
            else:
                print("\n[ERROR] Some tests failed - check the logs")
        else:
            print("\n[OK] Contract deployed to testnet!")
            print("Run health_check.py to verify deployment")

    except Exception as e:
        print(f"[ERROR] Deployment failed: {e}")

if __name__ == "__main__":
    main()