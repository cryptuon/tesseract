#!/usr/bin/env python3
"""
Tesseract Operator Management Script

Manages operator roles for the TesseractBuffer contract.
- Add operators (grant BUFFER_ROLE + RESOLVE_ROLE)
- Remove operators (revoke roles)
- List current operators and their roles
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# Role constants
BUFFER_ROLE = Web3.keccak(text="BUFFER_ROLE")
RESOLVE_ROLE = Web3.keccak(text="RESOLVE_ROLE")
ADMIN_ROLE = Web3.keccak(text="ADMIN_ROLE")

ROLE_NAMES = {
    BUFFER_ROLE.hex(): "BUFFER_ROLE",
    RESOLVE_ROLE.hex(): "RESOLVE_ROLE",
    ADMIN_ROLE.hex(): "ADMIN_ROLE",
}


def load_contract(network: str):
    """Load contract and web3 instance"""
    config_path = Path("config/networks.json")
    with open(config_path) as f:
        config = json.load(f)["networks"].get(network)

    if not config:
        raise ValueError(f"Unknown network: {network}")

    if "rpc_url" in config:
        rpc_url = config["rpc_url"]
    else:
        api_key = os.getenv("ALCHEMY_API_KEY", "")
        rpc_url = config["rpc_url_template"].replace("{ALCHEMY_API_KEY}", api_key)

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to {network}")

    # Load deployment
    deployment_file = Path(f"deployments/{network}_deployment.json")
    abi_file = Path("deployments/TesseractBuffer_abi.json")

    if not deployment_file.exists() or not abi_file.exists():
        raise FileNotFoundError("Deployment files not found")

    with open(deployment_file) as f:
        deployment = json.load(f)

    with open(abi_file) as f:
        abi = json.load(f)

    contract = w3.eth.contract(
        address=deployment['contract_address'],
        abi=abi
    )

    return w3, contract


def get_account(w3, network: str):
    """Get account for transactions"""
    if network == "local":
        return w3.eth.accounts[0], None
    else:
        private_key = os.getenv("DEPLOYER_PRIVATE_KEY")
        if not private_key:
            raise ValueError("DEPLOYER_PRIVATE_KEY not set")
        account = w3.eth.account.from_key(private_key)
        return account.address, account


def send_transaction(w3, contract, func, account_address, account):
    """Send a transaction"""
    if account:
        # Sign and send for testnet/mainnet
        nonce = w3.eth.get_transaction_count(account_address)
        tx = func.build_transaction({
            'from': account_address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    else:
        # Direct transact for local
        tx_hash = func.transact({'from': account_address})

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def add_operator(network: str, operator_address: str):
    """Add an operator with both BUFFER_ROLE and RESOLVE_ROLE"""
    print(f"Adding operator: {operator_address}")

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Check current owner
    owner = contract.functions.owner().call()
    if account_address.lower() != owner.lower():
        print(f"[ERROR] Only owner can add operators")
        print(f"        Owner: {owner}")
        print(f"        Your address: {account_address}")
        return False

    # Check if already has roles
    has_buffer = contract.functions.has_role(BUFFER_ROLE, operator_address).call()
    has_resolve = contract.functions.has_role(RESOLVE_ROLE, operator_address).call()

    if has_buffer and has_resolve:
        print("[INFO] Operator already has both roles")
        return True

    # Grant BUFFER_ROLE
    if not has_buffer:
        print("Granting BUFFER_ROLE...")
        receipt = send_transaction(
            w3, contract,
            contract.functions.grant_role(BUFFER_ROLE, operator_address),
            account_address, account
        )
        print(f"  TX: {receipt.transactionHash.hex()}")
        print(f"  Gas: {receipt.gasUsed:,}")

    # Grant RESOLVE_ROLE
    if not has_resolve:
        print("Granting RESOLVE_ROLE...")
        receipt = send_transaction(
            w3, contract,
            contract.functions.grant_role(RESOLVE_ROLE, operator_address),
            account_address, account
        )
        print(f"  TX: {receipt.transactionHash.hex()}")
        print(f"  Gas: {receipt.gasUsed:,}")

    print(f"[OK] Operator added successfully")
    return True


def remove_operator(network: str, operator_address: str):
    """Remove an operator (revoke both roles)"""
    print(f"Removing operator: {operator_address}")

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Check current owner
    owner = contract.functions.owner().call()
    if account_address.lower() != owner.lower():
        print(f"[ERROR] Only owner can remove operators")
        return False

    # Check current roles
    has_buffer = contract.functions.has_role(BUFFER_ROLE, operator_address).call()
    has_resolve = contract.functions.has_role(RESOLVE_ROLE, operator_address).call()

    if not has_buffer and not has_resolve:
        print("[INFO] Address has no operator roles")
        return True

    # Revoke BUFFER_ROLE
    if has_buffer:
        print("Revoking BUFFER_ROLE...")
        receipt = send_transaction(
            w3, contract,
            contract.functions.revoke_role(BUFFER_ROLE, operator_address),
            account_address, account
        )
        print(f"  TX: {receipt.transactionHash.hex()}")
        print(f"  Gas: {receipt.gasUsed:,}")

    # Revoke RESOLVE_ROLE
    if has_resolve:
        print("Revoking RESOLVE_ROLE...")
        receipt = send_transaction(
            w3, contract,
            contract.functions.revoke_role(RESOLVE_ROLE, operator_address),
            account_address, account
        )
        print(f"  TX: {receipt.transactionHash.hex()}")
        print(f"  Gas: {receipt.gasUsed:,}")

    print(f"[OK] Operator removed successfully")
    return True


def check_roles(network: str, address: str):
    """Check roles for an address"""
    w3, contract = load_contract(network)

    print(f"Checking roles for: {address}")
    print()

    has_buffer = contract.functions.has_role(BUFFER_ROLE, address).call()
    has_resolve = contract.functions.has_role(RESOLVE_ROLE, address).call()
    has_admin = contract.functions.has_role(ADMIN_ROLE, address).call()

    print(f"  BUFFER_ROLE:  {'Yes' if has_buffer else 'No'}")
    print(f"  RESOLVE_ROLE: {'Yes' if has_resolve else 'No'}")
    print(f"  ADMIN_ROLE:   {'Yes' if has_admin else 'No'}")

    owner = contract.functions.owner().call()
    emergency_admin = contract.functions.emergency_admin().call()

    print()
    if address.lower() == owner.lower():
        print("  [Owner of contract]")
    if address.lower() == emergency_admin.lower():
        print("  [Emergency admin]")


def list_info(network: str):
    """List contract info and key addresses"""
    w3, contract = load_contract(network)

    print("Contract Information")
    print("-" * 40)
    print(f"Address: {contract.address}")
    print(f"Network: {network}")
    print()

    owner = contract.functions.owner().call()
    emergency_admin = contract.functions.emergency_admin().call()

    print("Key Addresses")
    print("-" * 40)
    print(f"Owner:           {owner}")
    print(f"Emergency Admin: {emergency_admin}")
    print()

    print("To check roles for a specific address:")
    print(f"  python scripts/manage_operators.py {network} check <address>")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Manage Tesseract operators")
    parser.add_argument("network", help="Network (local, sepolia, mumbai)")
    parser.add_argument("action", nargs="?", default="list",
                        help="Action: add, remove, check, list")
    parser.add_argument("address", nargs="?", help="Operator address")

    args = parser.parse_args()

    print("=" * 50)
    print("Tesseract Operator Management")
    print("=" * 50)
    print()

    try:
        if args.action == "list":
            list_info(args.network)

        elif args.action == "add":
            if not args.address:
                print("[ERROR] Address required for 'add' action")
                sys.exit(1)
            if not Web3.is_address(args.address):
                print("[ERROR] Invalid address format")
                sys.exit(1)
            add_operator(args.network, Web3.to_checksum_address(args.address))

        elif args.action == "remove":
            if not args.address:
                print("[ERROR] Address required for 'remove' action")
                sys.exit(1)
            if not Web3.is_address(args.address):
                print("[ERROR] Invalid address format")
                sys.exit(1)
            remove_operator(args.network, Web3.to_checksum_address(args.address))

        elif args.action == "check":
            if not args.address:
                print("[ERROR] Address required for 'check' action")
                sys.exit(1)
            if not Web3.is_address(args.address):
                print("[ERROR] Invalid address format")
                sys.exit(1)
            check_roles(args.network, Web3.to_checksum_address(args.address))

        else:
            print(f"[ERROR] Unknown action: {args.action}")
            print("        Valid actions: add, remove, check, list")
            sys.exit(1)

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
