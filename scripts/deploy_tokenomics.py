#!/usr/bin/env python3
"""
Deploy Tesseract tokenomics contracts.

Deployment order:
1. TesseractToken (TESS)
2. TesseractStaking
3. FeeCollector
4. RelayerRegistry
5. TesseractGovernor
6. Configure connections between contracts

Usage:
    python scripts/deploy_tokenomics.py <network>
    python scripts/deploy_tokenomics.py sepolia
"""

import json
import os
import sys
from pathlib import Path

import vyper
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# Network configurations
NETWORKS = {
    "sepolia": {
        "rpc_url": os.getenv("SEPOLIA_RPC_URL", "https://rpc.sepolia.org"),
        "chain_id": 11155111,
        "explorer": "https://sepolia.etherscan.io",
    },
    "polygon_amoy": {
        "rpc_url": os.getenv("POLYGON_AMOY_RPC_URL", "https://rpc-amoy.polygon.technology"),
        "chain_id": 80002,
        "explorer": "https://amoy.polygonscan.com",
    },
    "arbitrum_sepolia": {
        "rpc_url": os.getenv("ARBITRUM_SEPOLIA_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc"),
        "chain_id": 421614,
        "explorer": "https://sepolia.arbiscan.io",
    },
    "base_sepolia": {
        "rpc_url": os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org"),
        "chain_id": 84532,
        "explorer": "https://sepolia.basescan.org",
    },
    "local": {
        "rpc_url": "http://localhost:8545",
        "chain_id": 31337,
        "explorer": None,
    },
}

# Contract paths
CONTRACTS = {
    "TesseractToken": "contracts/TesseractToken.vy",
    "TesseractStaking": "contracts/TesseractStaking.vy",
    "FeeCollector": "contracts/FeeCollector.vy",
    "RelayerRegistry": "contracts/RelayerRegistry.vy",
    "TesseractGovernor": "contracts/TesseractGovernor.vy",
}


def compile_contract(contract_path: str) -> dict:
    """Compile a Vyper contract."""
    print(f"  Compiling {contract_path}...")
    with open(contract_path) as f:
        source = f.read()
    return vyper.compile_code(source, output_formats=["abi", "bytecode"])


def deploy_contract(w3: Web3, compiled: dict, deployer: str, private_key: str, *args) -> str:
    """Deploy a compiled contract and return the address."""
    contract = w3.eth.contract(abi=compiled["abi"], bytecode=compiled["bytecode"])

    # Build transaction
    nonce = w3.eth.get_transaction_count(deployer)
    tx = contract.constructor(*args).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": 5_000_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })

    # Sign and send
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"    Transaction: {tx_hash.hex()}")

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if receipt.status != 1:
        raise Exception(f"Deployment failed: {receipt}")

    return receipt.contractAddress


def save_deployment(network: str, deployment: dict):
    """Save deployment info to file."""
    deployments_dir = Path("deployments")
    deployments_dir.mkdir(exist_ok=True)

    filepath = deployments_dir / f"{network}_tokenomics.json"
    with open(filepath, "w") as f:
        json.dump(deployment, f, indent=2)

    print(f"\nDeployment saved to {filepath}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/deploy_tokenomics.py <network>")
        print(f"Available networks: {', '.join(NETWORKS.keys())}")
        sys.exit(1)

    network = sys.argv[1].lower()
    if network not in NETWORKS:
        print(f"Unknown network: {network}")
        print(f"Available networks: {', '.join(NETWORKS.keys())}")
        sys.exit(1)

    config = NETWORKS[network]

    # Get deployer private key
    private_key = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not private_key:
        print("Error: DEPLOYER_PRIVATE_KEY environment variable not set")
        sys.exit(1)

    # Connect to network
    w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
    if not w3.is_connected():
        print(f"Failed to connect to {config['rpc_url']}")
        sys.exit(1)

    deployer = w3.eth.account.from_key(private_key).address
    balance = w3.eth.get_balance(deployer)

    print(f"\n{'='*60}")
    print(f"Tesseract Tokenomics Deployment")
    print(f"{'='*60}")
    print(f"Network: {network}")
    print(f"Chain ID: {config['chain_id']}")
    print(f"Deployer: {deployer}")
    print(f"Balance: {w3.from_wei(balance, 'ether')} ETH")
    print(f"{'='*60}\n")

    # Wallet addresses (for initial distribution)
    community_wallet = os.getenv("COMMUNITY_WALLET", deployer)
    treasury_wallet = os.getenv("TREASURY_WALLET", deployer)

    print(f"Community wallet: {community_wallet}")
    print(f"Treasury wallet: {treasury_wallet}")

    deployment = {
        "network": network,
        "chain_id": config["chain_id"],
        "deployer": deployer,
        "contracts": {},
    }

    # Compile all contracts
    print("\n[1/6] Compiling contracts...")
    compiled = {}
    for name, path in CONTRACTS.items():
        compiled[name] = compile_contract(path)
    print("  All contracts compiled successfully!")

    # Deploy TesseractToken
    print("\n[2/6] Deploying TesseractToken (TESS)...")
    token_address = deploy_contract(
        w3, compiled["TesseractToken"], deployer, private_key,
        community_wallet, treasury_wallet
    )
    print(f"  TesseractToken deployed at: {token_address}")
    deployment["contracts"]["TesseractToken"] = token_address

    # Deploy TesseractStaking
    print("\n[3/6] Deploying TesseractStaking...")
    staking_address = deploy_contract(
        w3, compiled["TesseractStaking"], deployer, private_key,
        token_address
    )
    print(f"  TesseractStaking deployed at: {staking_address}")
    deployment["contracts"]["TesseractStaking"] = staking_address

    # Deploy RelayerRegistry
    print("\n[4/6] Deploying RelayerRegistry...")
    registry_address = deploy_contract(
        w3, compiled["RelayerRegistry"], deployer, private_key,
        token_address
    )
    print(f"  RelayerRegistry deployed at: {registry_address}")
    deployment["contracts"]["RelayerRegistry"] = registry_address

    # Deploy FeeCollector
    print("\n[5/6] Deploying FeeCollector...")
    fee_collector_address = deploy_contract(
        w3, compiled["FeeCollector"], deployer, private_key,
        staking_address, registry_address, treasury_wallet
    )
    print(f"  FeeCollector deployed at: {fee_collector_address}")
    deployment["contracts"]["FeeCollector"] = fee_collector_address

    # Deploy TesseractGovernor
    print("\n[6/6] Deploying TesseractGovernor...")
    governor_address = deploy_contract(
        w3, compiled["TesseractGovernor"], deployer, private_key,
        token_address
    )
    print(f"  TesseractGovernor deployed at: {governor_address}")
    deployment["contracts"]["TesseractGovernor"] = governor_address

    # Configure connections
    print("\n[*] Configuring contract connections...")

    # Set fee distributor on staking contract
    staking = w3.eth.contract(address=staking_address, abi=compiled["TesseractStaking"]["abi"])
    nonce = w3.eth.get_transaction_count(deployer)
    tx = staking.functions.set_fee_distributor(fee_collector_address).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("  Staking fee distributor set")

    # Set fee collector on registry
    registry = w3.eth.contract(address=registry_address, abi=compiled["RelayerRegistry"]["abi"])
    nonce = w3.eth.get_transaction_count(deployer)
    tx = registry.functions.set_fee_collector(fee_collector_address).build_transaction({
        "from": deployer,
        "nonce": nonce,
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("  Registry fee collector set")

    # Save deployment
    save_deployment(network, deployment)

    print(f"\n{'='*60}")
    print("DEPLOYMENT COMPLETE!")
    print(f"{'='*60}")
    print("\nContract Addresses:")
    for name, address in deployment["contracts"].items():
        print(f"  {name}: {address}")

    if config["explorer"]:
        print(f"\nView on explorer:")
        for name, address in deployment["contracts"].items():
            print(f"  {name}: {config['explorer']}/address/{address}")

    print("\nNext steps:")
    print("  1. Verify contracts on block explorer")
    print("  2. Create vesting schedules for team/investors")
    print("  3. Configure AtomicSwapCoordinator with fee collector")
    print("  4. Transfer ownership to governance (after testing)")


if __name__ == "__main__":
    main()
