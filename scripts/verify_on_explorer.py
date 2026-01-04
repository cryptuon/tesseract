#!/usr/bin/env python3
"""
Contract Verification Script for Block Explorers

Submits Vyper contracts for verification on Etherscan, Polygonscan, and other
block explorers. Supports Sepolia, Mumbai, and mainnet networks.

Usage:
    python scripts/verify_on_explorer.py <network>
    python scripts/verify_on_explorer.py sepolia
    python scripts/verify_on_explorer.py mainnet
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# Block explorer API configurations
EXPLORER_APIS = {
    # Ethereum
    "sepolia": {
        "name": "Etherscan Sepolia",
        "api_url": "https://api-sepolia.etherscan.io/api",
        "explorer_url": "https://sepolia.etherscan.io",
        "api_key_env": "ETHERSCAN_API_KEY",
    },
    "mainnet": {
        "name": "Etherscan",
        "api_url": "https://api.etherscan.io/api",
        "explorer_url": "https://etherscan.io",
        "api_key_env": "ETHERSCAN_API_KEY",
    },
    # Polygon
    "polygon": {
        "name": "Polygonscan",
        "api_url": "https://api.polygonscan.com/api",
        "explorer_url": "https://polygonscan.com",
        "api_key_env": "POLYGONSCAN_API_KEY",
    },
    "polygon_amoy": {
        "name": "Polygonscan Amoy",
        "api_url": "https://api-amoy.polygonscan.com/api",
        "explorer_url": "https://amoy.polygonscan.com",
        "api_key_env": "POLYGONSCAN_API_KEY",
    },
    # Arbitrum
    "arbitrum": {
        "name": "Arbiscan",
        "api_url": "https://api.arbiscan.io/api",
        "explorer_url": "https://arbiscan.io",
        "api_key_env": "ARBISCAN_API_KEY",
    },
    "arbitrum_sepolia": {
        "name": "Arbiscan Sepolia",
        "api_url": "https://api-sepolia.arbiscan.io/api",
        "explorer_url": "https://sepolia.arbiscan.io",
        "api_key_env": "ARBISCAN_API_KEY",
    },
    # Optimism
    "optimism": {
        "name": "Optimistic Etherscan",
        "api_url": "https://api-optimistic.etherscan.io/api",
        "explorer_url": "https://optimistic.etherscan.io",
        "api_key_env": "OPTIMISTIC_ETHERSCAN_API_KEY",
    },
    "optimism_sepolia": {
        "name": "Optimistic Etherscan Sepolia",
        "api_url": "https://api-sepolia-optimistic.etherscan.io/api",
        "explorer_url": "https://sepolia-optimism.etherscan.io",
        "api_key_env": "OPTIMISTIC_ETHERSCAN_API_KEY",
    },
    # Base
    "base": {
        "name": "Basescan",
        "api_url": "https://api.basescan.org/api",
        "explorer_url": "https://basescan.org",
        "api_key_env": "BASESCAN_API_KEY",
    },
    "base_sepolia": {
        "name": "Basescan Sepolia",
        "api_url": "https://api-sepolia.basescan.org/api",
        "explorer_url": "https://sepolia.basescan.org",
        "api_key_env": "BASESCAN_API_KEY",
    },
}

# All Tesseract contracts
CONTRACTS = {
    "TesseractBuffer": "contracts/TesseractBuffer.vy",
    "AtomicSwapCoordinator": "contracts/AtomicSwapCoordinator.vy",
    "TesseractToken": "contracts/TesseractToken.vy",
    "TesseractStaking": "contracts/TesseractStaking.vy",
    "FeeCollector": "contracts/FeeCollector.vy",
    "RelayerRegistry": "contracts/RelayerRegistry.vy",
    "TesseractGovernor": "contracts/TesseractGovernor.vy",
}


def load_deployment_info(network: str) -> dict:
    """Load deployment information from saved file."""
    deployments_dir = Path("deployments")

    # Try different file naming patterns
    patterns = [
        f"{network}_deployment.json",
        f"{network}_TesseractBuffer.json",
        f"deployment_{network}.json",
    ]

    for pattern in patterns:
        filepath = deployments_dir / pattern
        if filepath.exists():
            with open(filepath) as f:
                return json.load(f)

    # If no file found, list available files
    if deployments_dir.exists():
        files = list(deployments_dir.glob("*.json"))
        if files:
            print(f"Available deployment files: {[f.name for f in files]}")

    raise FileNotFoundError(f"No deployment file found for network: {network}")


def load_contract_source(contract_name: str = "TesseractBuffer") -> str:
    """Load Vyper contract source code."""
    if contract_name in CONTRACTS:
        filepath = Path(CONTRACTS[contract_name])
    else:
        filepath = Path("contracts") / f"{contract_name}.vy"

    if not filepath.exists():
        raise FileNotFoundError(f"Contract not found: {filepath}")

    with open(filepath) as f:
        return f.read()


def submit_verification(
    network: str,
    contract_address: str,
    source_code: str,
    contract_name: str = "TesseractBuffer",
    compiler_version: str = "v0.3.10",
) -> str:
    """Submit contract for verification."""
    config = EXPLORER_APIS.get(network)
    if not config:
        raise ValueError(f"Unsupported network: {network}. Supported: {list(EXPLORER_APIS.keys())}")

    api_key = os.getenv(config["api_key_env"])
    if not api_key:
        raise ValueError(f"Missing API key. Set {config['api_key_env']} environment variable.")

    print(f"[*] Submitting verification to {config['name']}...")
    print(f"    Contract: {contract_address}")
    print(f"    Compiler: Vyper {compiler_version}")

    # Prepare verification request
    data = {
        "apikey": api_key,
        "module": "contract",
        "action": "verifysourcecode",
        "contractaddress": contract_address,
        "sourceCode": source_code,
        "codeformat": "vyper-single-file",
        "contractname": contract_name,
        "compilerversion": compiler_version,
        "optimizationUsed": "0",
        "runs": "0",
        "constructorArguements": "",  # Note: Etherscan has a typo in their API
        "evmversion": "shanghai",
        "licenseType": "3",  # MIT License
    }

    try:
        response = requests.post(config["api_url"], data=data, timeout=60)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"API request failed: {e}")

    if result.get("status") == "1":
        guid = result.get("result")
        print(f"[+] Verification submitted successfully!")
        print(f"    GUID: {guid}")
        return guid
    else:
        error_msg = result.get("result", "Unknown error")

        # Handle common error cases
        if "already verified" in error_msg.lower():
            print(f"[*] Contract is already verified!")
            return None
        elif "unable to locate" in error_msg.lower():
            print(f"[!] Contract not found. It may take a few minutes for the contract to be indexed.")
            print(f"    Please try again later.")
            return None
        else:
            raise RuntimeError(f"Verification failed: {error_msg}")


def check_verification_status(network: str, guid: str, max_attempts: int = 10) -> bool:
    """Check verification status until complete or timeout."""
    config = EXPLORER_APIS.get(network)
    api_key = os.getenv(config["api_key_env"])

    print(f"\n[*] Checking verification status...")

    for attempt in range(1, max_attempts + 1):
        time.sleep(5)  # Wait between checks

        try:
            response = requests.get(
                config["api_url"],
                params={
                    "apikey": api_key,
                    "module": "contract",
                    "action": "checkverifystatus",
                    "guid": guid,
                },
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as e:
            print(f"    Attempt {attempt}/{max_attempts}: Request failed - {e}")
            continue

        status = result.get("result", "")

        if result.get("status") == "1":
            print(f"[+] Verification successful!")
            return True
        elif "pending" in status.lower():
            print(f"    Attempt {attempt}/{max_attempts}: Pending...")
        elif "fail" in status.lower():
            print(f"[-] Verification failed: {status}")
            return False
        else:
            print(f"    Attempt {attempt}/{max_attempts}: {status}")

    print(f"[-] Verification check timed out after {max_attempts} attempts")
    return False


def verify_contract(network: str, contract_name: str = "TesseractBuffer"):
    """Main verification workflow."""
    print(f"\n{'='*60}")
    print(f"Contract Verification - {network.upper()}")
    print(f"{'='*60}\n")

    # Load deployment info
    try:
        deployment = load_deployment_info(network)
    except FileNotFoundError as e:
        print(f"[-] {e}")
        print(f"    Make sure you have deployed the contract first.")
        return False

    contract_address = deployment.get("contract_address") or deployment.get("address")
    if not contract_address:
        print(f"[-] No contract address found in deployment file")
        return False

    # Load source code
    try:
        source_code = load_contract_source(contract_name)
    except FileNotFoundError as e:
        print(f"[-] {e}")
        return False

    # Get compiler version from deployment or default
    compiler_version = deployment.get("compiler_version", "v0.3.10")

    # Submit verification
    try:
        guid = submit_verification(
            network=network,
            contract_address=contract_address,
            source_code=source_code,
            contract_name=contract_name,
            compiler_version=compiler_version,
        )
    except (ValueError, RuntimeError) as e:
        print(f"[-] {e}")
        return False

    if guid is None:
        # Already verified or needs retry
        return True

    # Check status
    success = check_verification_status(network, guid)

    if success:
        config = EXPLORER_APIS.get(network)
        print(f"\n[+] View verified contract:")
        print(f"    {config['explorer_url']}/address/{contract_address}#code")

    return success


def verify_all_contracts(network: str):
    """Verify all deployed contracts for a network."""
    print(f"\n{'='*60}")
    print(f"Verifying All Contracts - {network.upper()}")
    print(f"{'='*60}\n")

    results = {}
    for contract_name in CONTRACTS.keys():
        try:
            print(f"\n--- {contract_name} ---")
            success = verify_contract(network, contract_name)
            results[contract_name] = "VERIFIED" if success else "FAILED"
        except Exception as e:
            results[contract_name] = f"ERROR: {e}"

    # Summary
    print(f"\n{'='*60}")
    print("Verification Summary")
    print(f"{'='*60}")
    for name, status in results.items():
        print(f"  {name:30} {status}")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_on_explorer.py <network> [contract_name]")
        print(f"Supported networks: {', '.join(EXPLORER_APIS.keys())}")
        print(f"Available contracts: {', '.join(CONTRACTS.keys())}")
        print("\nUse 'all' as contract_name to verify all contracts")
        sys.exit(1)

    network = sys.argv[1].lower()
    contract_name = sys.argv[2] if len(sys.argv) > 2 else "TesseractBuffer"

    if contract_name.lower() == "all":
        results = verify_all_contracts(network)
        success = all(r == "VERIFIED" for r in results.values())
    else:
        success = verify_contract(network, contract_name)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
