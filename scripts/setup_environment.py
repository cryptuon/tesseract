#!/usr/bin/env python3
"""
Tesseract Environment Setup Script

Validates environment configuration and tests network connectivity.
Run this before deploying to ensure everything is configured correctly.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def check_env_file():
    """Check if .env file exists"""
    env_path = Path(".env")
    if not env_path.exists():
        print("[WARN] .env file not found")
        print("       Create a .env file with:")
        print("       DEPLOYER_PRIVATE_KEY=your_private_key")
        print("       ALCHEMY_API_KEY=your_alchemy_api_key")
        return False
    print("[OK] .env file found")
    return True


def check_private_key():
    """Check if deployer private key is configured"""
    private_key = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not private_key:
        print("[WARN] DEPLOYER_PRIVATE_KEY not set")
        print("       Required for testnet/mainnet deployments")
        return False

    # Basic validation (should start with 0x and be 66 chars, or 64 chars without 0x)
    if private_key.startswith("0x"):
        if len(private_key) != 66:
            print("[ERROR] DEPLOYER_PRIVATE_KEY has invalid length")
            return False
    else:
        if len(private_key) != 64:
            print("[ERROR] DEPLOYER_PRIVATE_KEY has invalid length")
            return False

    print("[OK] DEPLOYER_PRIVATE_KEY is configured")
    return True


def check_alchemy_api_key():
    """Check if Alchemy API key is configured"""
    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        print("[WARN] ALCHEMY_API_KEY not set")
        print("       Required for testnet/mainnet deployments")
        print("       Get a free key at: https://www.alchemy.com/")
        return False

    if len(api_key) < 20:
        print("[WARN] ALCHEMY_API_KEY seems too short - verify it's correct")
        return False

    print("[OK] ALCHEMY_API_KEY is configured")
    return True


def check_network_connectivity(network: str = "local"):
    """Test network connectivity"""
    from web3 import Web3

    config_path = Path("config/networks.json")
    if not config_path.exists():
        print("[ERROR] config/networks.json not found")
        return False

    with open(config_path) as f:
        networks = json.load(f)["networks"]

    if network not in networks:
        print(f"[ERROR] Unknown network: {network}")
        print(f"        Available: {', '.join(networks.keys())}")
        return False

    net_config = networks[network]

    # Build RPC URL
    if "rpc_url" in net_config:
        rpc_url = net_config["rpc_url"]
    elif "rpc_url_template" in net_config:
        api_key = os.getenv("ALCHEMY_API_KEY", "")
        if not api_key:
            print(f"[WARN] Cannot test {network} - ALCHEMY_API_KEY not set")
            return False
        rpc_url = net_config["rpc_url_template"].replace("{ALCHEMY_API_KEY}", api_key)
    else:
        print(f"[ERROR] No RPC URL configured for {network}")
        return False

    print(f"Testing connection to {net_config['name']}...")

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
        if w3.is_connected():
            chain_id = w3.eth.chain_id
            block_number = w3.eth.block_number
            print(f"[OK] Connected to {net_config['name']}")
            print(f"     Chain ID: {chain_id}")
            print(f"     Block: {block_number:,}")
            return True
        else:
            print(f"[ERROR] Cannot connect to {net_config['name']}")
            return False
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False


def check_deployer_balance(network: str = "local"):
    """Check deployer account balance"""
    from web3 import Web3

    config_path = Path("config/networks.json")
    with open(config_path) as f:
        networks = json.load(f)["networks"]

    net_config = networks[network]

    # Build RPC URL
    if "rpc_url" in net_config:
        rpc_url = net_config["rpc_url"]
    else:
        api_key = os.getenv("ALCHEMY_API_KEY", "")
        rpc_url = net_config["rpc_url_template"].replace("{ALCHEMY_API_KEY}", api_key)

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print("[ERROR] Cannot connect to network")
        return False

    private_key = os.getenv("DEPLOYER_PRIVATE_KEY")

    if network == "local":
        # Use first account from local node
        accounts = w3.eth.accounts
        if not accounts:
            print("[WARN] No accounts available on local network")
            return False
        deployer = accounts[0]
    elif private_key:
        account = w3.eth.account.from_key(private_key)
        deployer = account.address
    else:
        print("[WARN] Cannot check balance - no private key configured")
        return False

    balance = w3.eth.get_balance(deployer)
    balance_eth = w3.from_wei(balance, 'ether')

    currency = net_config.get("native_currency", "ETH")
    print(f"Deployer: {deployer}")
    print(f"Balance: {balance_eth:.6f} {currency}")

    # Minimum recommended balance for deployment
    min_balance = 0.01 if net_config.get("is_testnet") else 0.1

    if balance_eth < min_balance:
        print(f"[WARN] Low balance! Recommended minimum: {min_balance} {currency}")
        if "faucets" in net_config:
            print("       Get testnet funds from:")
            for faucet in net_config["faucets"]:
                print(f"       - {faucet}")
        return False

    print(f"[OK] Sufficient balance for deployment")
    return True


def check_contract_compilation():
    """Verify contract compiles successfully"""
    from vyper import compile_code
    from pathlib import Path

    contract_path = Path("contracts/TesseractBuffer.vy")
    if not contract_path.exists():
        print("[ERROR] Contract file not found: contracts/TesseractBuffer.vy")
        return False

    print("Compiling contract...")

    try:
        with open(contract_path) as f:
            source_code = f.read()

        compiled = compile_code(source_code, output_formats=['bytecode', 'abi'])

        bytecode_size = len(compiled['bytecode'])
        func_count = len([x for x in compiled['abi'] if x['type'] == 'function'])

        print(f"[OK] Contract compiles successfully")
        print(f"     Bytecode size: {bytecode_size:,} bytes")
        print(f"     Functions: {func_count}")
        return True

    except Exception as e:
        print(f"[ERROR] Compilation failed: {e}")
        return False


def main():
    """Run all environment checks"""
    print("=" * 50)
    print("Tesseract Environment Setup Check")
    print("=" * 50)
    print()

    # Parse arguments
    network = sys.argv[1] if len(sys.argv) > 1 else "local"

    results = {
        "env_file": check_env_file(),
        "contract": check_contract_compilation(),
    }

    print()

    if network != "local":
        results["private_key"] = check_private_key()
        results["api_key"] = check_alchemy_api_key()

    print()
    results["connectivity"] = check_network_connectivity(network)

    if results["connectivity"]:
        print()
        results["balance"] = check_deployer_balance(network)

    # Summary
    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)

    all_ok = all(results.values())
    for check, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")

    print()
    if all_ok:
        print("Environment is ready for deployment!")
        print(f"Run: python scripts/deploy_simple.py {network}")
    else:
        print("Some checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
