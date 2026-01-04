#!/usr/bin/env python3
"""
Full Tesseract Testnet Deployment

Deploys the complete Tesseract ecosystem:
1. Core contracts (TesseractBuffer, AtomicSwapCoordinator)
2. Tokenomics (TESS, Staking, FeeCollector, RelayerRegistry, Governor)
3. Configures all contract connections

Usage:
    python scripts/deploy_full_testnet.py <network>
    python scripts/deploy_full_testnet.py sepolia

Environment variables:
    DEPLOYER_PRIVATE_KEY - Private key for deployment
    COMMUNITY_WALLET - Wallet for community token allocation
    TREASURY_WALLET - Wallet for treasury allocation
    <NETWORK>_RPC_URL - RPC endpoint for the network
"""

import json
import os
import sys
from datetime import datetime
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
        "name": "Ethereum Sepolia",
    },
    "polygon_amoy": {
        "rpc_url": os.getenv("POLYGON_AMOY_RPC_URL", "https://rpc-amoy.polygon.technology"),
        "chain_id": 80002,
        "explorer": "https://amoy.polygonscan.com",
        "name": "Polygon Amoy",
    },
    "arbitrum_sepolia": {
        "rpc_url": os.getenv("ARBITRUM_SEPOLIA_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc"),
        "chain_id": 421614,
        "explorer": "https://sepolia.arbiscan.io",
        "name": "Arbitrum Sepolia",
    },
    "optimism_sepolia": {
        "rpc_url": os.getenv("OPTIMISM_SEPOLIA_RPC_URL", "https://sepolia.optimism.io"),
        "chain_id": 11155420,
        "explorer": "https://sepolia-optimism.etherscan.io",
        "name": "Optimism Sepolia",
    },
    "base_sepolia": {
        "rpc_url": os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org"),
        "chain_id": 84532,
        "explorer": "https://sepolia.basescan.org",
        "name": "Base Sepolia",
    },
}

# All contracts to deploy
CONTRACTS = {
    # Core
    "TesseractBuffer": "contracts/TesseractBuffer.vy",
    "AtomicSwapCoordinator": "contracts/AtomicSwapCoordinator.vy",
    # Tokenomics
    "TesseractToken": "contracts/TesseractToken.vy",
    "TesseractStaking": "contracts/TesseractStaking.vy",
    "FeeCollector": "contracts/FeeCollector.vy",
    "RelayerRegistry": "contracts/RelayerRegistry.vy",
    "TesseractGovernor": "contracts/TesseractGovernor.vy",
}


class Deployer:
    """Handles contract deployment and configuration."""

    def __init__(self, network: str, private_key: str):
        self.network = network
        self.config = NETWORKS[network]
        self.w3 = Web3(Web3.HTTPProvider(self.config["rpc_url"]))
        self.private_key = private_key
        self.deployer = self.w3.eth.account.from_key(private_key).address
        self.compiled = {}
        self.deployed = {}
        self.nonce = self.w3.eth.get_transaction_count(self.deployer)

    def compile_all(self):
        """Compile all contracts."""
        print("\n[*] Compiling contracts...")
        for name, path in CONTRACTS.items():
            print(f"    {name}...", end=" ")
            with open(path) as f:
                source = f.read()
            self.compiled[name] = vyper.compile_code(
                source, output_formats=["abi", "bytecode"]
            )
            bytecode_len = len(self.compiled[name]["bytecode"]) // 2 - 1
            print(f"({bytecode_len:,} bytes)")
        print("    All contracts compiled!")

    def deploy(self, name: str, *args) -> str:
        """Deploy a contract."""
        print(f"\n    Deploying {name}...", end=" ")

        compiled = self.compiled[name]
        contract = self.w3.eth.contract(
            abi=compiled["abi"],
            bytecode=compiled["bytecode"]
        )

        tx = contract.constructor(*args).build_transaction({
            "from": self.deployer,
            "nonce": self.nonce,
            "gas": 6_000_000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.config["chain_id"],
        })
        self.nonce += 1

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status != 1:
            raise Exception(f"Deployment failed: {name}")

        address = receipt.contractAddress
        self.deployed[name] = {
            "address": address,
            "tx_hash": tx_hash.hex(),
            "abi": compiled["abi"],
        }

        print(f"{address}")
        return address

    def call(self, name: str, function: str, *args):
        """Call a contract function."""
        contract = self.w3.eth.contract(
            address=self.deployed[name]["address"],
            abi=self.deployed[name]["abi"]
        )

        func = getattr(contract.functions, function)
        tx = func(*args).build_transaction({
            "from": self.deployer,
            "nonce": self.nonce,
            "gas": 200_000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.config["chain_id"],
        })
        self.nonce += 1

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise Exception(f"Call failed: {name}.{function}")

        return receipt

    def get_balance(self) -> float:
        """Get deployer balance in ETH."""
        return self.w3.from_wei(
            self.w3.eth.get_balance(self.deployer), "ether"
        )

    def save_deployment(self):
        """Save deployment info."""
        deployments_dir = Path("deployments")
        deployments_dir.mkdir(exist_ok=True)

        deployment = {
            "network": self.network,
            "chain_id": self.config["chain_id"],
            "deployer": self.deployer,
            "timestamp": datetime.utcnow().isoformat(),
            "contracts": {
                name: {
                    "address": info["address"],
                    "tx_hash": info["tx_hash"],
                }
                for name, info in self.deployed.items()
            },
        }

        filepath = deployments_dir / f"{self.network}_full_deployment.json"
        with open(filepath, "w") as f:
            json.dump(deployment, f, indent=2)

        print(f"\n    Deployment saved to {filepath}")
        return deployment


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/deploy_full_testnet.py <network>")
        print(f"Available networks: {', '.join(NETWORKS.keys())}")
        sys.exit(1)

    network = sys.argv[1].lower()
    if network not in NETWORKS:
        print(f"Unknown network: {network}")
        sys.exit(1)

    private_key = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not private_key:
        print("Error: DEPLOYER_PRIVATE_KEY not set")
        sys.exit(1)

    community_wallet = os.getenv("COMMUNITY_WALLET")
    treasury_wallet = os.getenv("TREASURY_WALLET")

    # Initialize deployer
    deployer = Deployer(network, private_key)

    if not deployer.w3.is_connected():
        print(f"Failed to connect to {deployer.config['rpc_url']}")
        sys.exit(1)

    # Use deployer address if wallets not specified
    if not community_wallet:
        community_wallet = deployer.deployer
    if not treasury_wallet:
        treasury_wallet = deployer.deployer

    print(f"\n{'='*70}")
    print(f"TESSERACT FULL DEPLOYMENT - {deployer.config['name']}")
    print(f"{'='*70}")
    print(f"Network:          {network}")
    print(f"Chain ID:         {deployer.config['chain_id']}")
    print(f"Deployer:         {deployer.deployer}")
    print(f"Balance:          {deployer.get_balance():.4f} ETH")
    print(f"Community Wallet: {community_wallet}")
    print(f"Treasury Wallet:  {treasury_wallet}")
    print(f"{'='*70}")

    # Compile
    deployer.compile_all()

    # ==================== DEPLOY TOKENOMICS ====================
    print(f"\n{'='*70}")
    print("PHASE 1: TOKENOMICS")
    print(f"{'='*70}")

    # 1. TESS Token
    token = deployer.deploy("TesseractToken", community_wallet, treasury_wallet)

    # 2. Staking
    staking = deployer.deploy("TesseractStaking", token)

    # 3. Relayer Registry
    registry = deployer.deploy("RelayerRegistry", token)

    # 4. Fee Collector
    fee_collector = deployer.deploy("FeeCollector", staking, registry, treasury_wallet)

    # 5. Governor
    governor = deployer.deploy("TesseractGovernor", token)

    # ==================== DEPLOY CORE CONTRACTS ====================
    print(f"\n{'='*70}")
    print("PHASE 2: CORE CONTRACTS")
    print(f"{'='*70}")

    # 6. TesseractBuffer
    buffer = deployer.deploy("TesseractBuffer")

    # 7. AtomicSwapCoordinator
    coordinator = deployer.deploy("AtomicSwapCoordinator")

    # ==================== CONFIGURE CONNECTIONS ====================
    print(f"\n{'='*70}")
    print("PHASE 3: CONFIGURATION")
    print(f"{'='*70}")

    print("\n    Configuring contract connections...")

    # Staking -> Fee Collector
    print("    - Setting staking fee distributor...")
    deployer.call("TesseractStaking", "set_fee_distributor", fee_collector)

    # Registry -> Fee Collector
    print("    - Setting registry fee collector...")
    deployer.call("RelayerRegistry", "set_fee_collector", fee_collector)

    # Coordinator -> Fee system
    print("    - Setting coordinator fee collector...")
    deployer.call("AtomicSwapCoordinator", "set_fee_collector", fee_collector)

    print("    - Setting coordinator TESS token...")
    deployer.call("AtomicSwapCoordinator", "set_tess_token", token)

    print("    - Setting coordinator staking contract...")
    deployer.call("AtomicSwapCoordinator", "set_staking_contract", staking)

    # Coordinator -> Buffer
    print("    - Setting coordinator buffer...")
    deployer.call("AtomicSwapCoordinator", "set_tesseract_buffer", buffer)

    # Authorize fee collector
    print("    - Authorizing coordinator as fee collector...")
    deployer.call("FeeCollector", "authorize_collector", coordinator, True)

    # Grant roles on buffer
    print("    - Granting buffer roles to deployer...")
    # BUFFER_ROLE = keccak256("BUFFER_ROLE")
    BUFFER_ROLE = "0x" + "1" * 64  # Simplified for now
    deployer.call("TesseractBuffer", "grant_role", BUFFER_ROLE, deployer.deployer)

    print("\n    Configuration complete!")

    # ==================== SAVE & SUMMARY ====================
    deployment = deployer.save_deployment()

    print(f"\n{'='*70}")
    print("DEPLOYMENT COMPLETE!")
    print(f"{'='*70}")

    print("\n Contract Addresses:")
    print("─" * 50)
    for name, info in deployer.deployed.items():
        print(f"  {name:25} {info['address']}")

    explorer = deployer.config.get("explorer")
    if explorer:
        print(f"\n View on {explorer}:")
        print("─" * 50)
        for name, info in deployer.deployed.items():
            print(f"  {name}: {explorer}/address/{info['address']}")

    print(f"\n{'='*70}")
    print("NEXT STEPS")
    print(f"{'='*70}")
    print("""
1. Verify contracts on block explorer:
   python scripts/verify_on_explorer.py {network} TesseractBuffer
   python scripts/verify_on_explorer.py {network} AtomicSwapCoordinator
   ...

2. Create vesting schedules for team/investors

3. Configure relayer with contract addresses

4. Start relayer:
   cd relayer && cargo run

5. Monitor via Grafana dashboard

6. Execute test swaps

7. After testing, transfer ownership to governance
""".format(network=network))

    remaining_balance = deployer.get_balance()
    print(f"\nRemaining balance: {remaining_balance:.4f} ETH")


if __name__ == "__main__":
    main()
