#!/usr/bin/env python3
"""
Tesseract Emergency Procedures Script

Emergency controls for the TesseractBuffer contract.
- Pause contract (stops all transaction processing)
- Unpause contract (resumes operations)
- Reset circuit breaker
- Transfer ownership

IMPORTANT: These are emergency procedures. Use with caution.
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()


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


def send_transaction(w3, contract, func, account_address, account, gas_limit=100000):
    """Send a transaction"""
    if account:
        nonce = w3.eth.get_transaction_count(account_address)
        tx = func.build_transaction({
            'from': account_address,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': w3.eth.gas_price
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    else:
        tx_hash = func.transact({'from': account_address})

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def status(network: str):
    """Show current contract status"""
    w3, contract = load_contract(network)

    print("Contract Status")
    print("-" * 40)
    print(f"Address: {contract.address}")
    print()

    paused = contract.functions.paused().call()
    cb_active = contract.functions.circuit_breaker_active().call()
    owner = contract.functions.owner().call()
    emergency_admin = contract.functions.emergency_admin().call()

    print(f"Paused:          {'YES' if paused else 'No'}")
    print(f"Circuit Breaker: {'ACTIVE' if cb_active else 'Inactive'}")
    print()
    print(f"Owner:           {owner}")
    print(f"Emergency Admin: {emergency_admin}")

    if paused:
        print()
        print("[!] CONTRACT IS PAUSED - No transactions can be processed")

    if cb_active:
        print()
        print("[!] CIRCUIT BREAKER ACTIVE - Too many failures detected")


def pause(network: str, confirm: bool = False):
    """Pause the contract"""
    if not confirm:
        print("[!] EMERGENCY PAUSE")
        print("    This will stop ALL transaction processing.")
        print()
        print("    To confirm, run:")
        print(f"    python scripts/emergency.py {network} pause --confirm")
        return

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Check if already paused
    if contract.functions.paused().call():
        print("[INFO] Contract is already paused")
        return

    # Check authorization
    owner = contract.functions.owner().call()
    emergency_admin = contract.functions.emergency_admin().call()

    if account_address.lower() not in [owner.lower(), emergency_admin.lower()]:
        print("[ERROR] Only owner or emergency admin can pause")
        return

    print("Pausing contract...")
    receipt = send_transaction(
        w3, contract,
        contract.functions.emergency_pause(),
        account_address, account
    )

    print(f"[OK] Contract PAUSED")
    print(f"     TX: {receipt.transactionHash.hex()}")
    print(f"     Gas: {receipt.gasUsed:,}")


def unpause(network: str, confirm: bool = False):
    """Unpause the contract"""
    if not confirm:
        print("[!] UNPAUSE CONTRACT")
        print("    This will resume transaction processing.")
        print()
        print("    To confirm, run:")
        print(f"    python scripts/emergency.py {network} unpause --confirm")
        return

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Check if paused
    if not contract.functions.paused().call():
        print("[INFO] Contract is not paused")
        return

    # Only owner can unpause
    owner = contract.functions.owner().call()
    if account_address.lower() != owner.lower():
        print("[ERROR] Only owner can unpause (not emergency admin)")
        print(f"        Owner: {owner}")
        return

    print("Unpausing contract...")
    receipt = send_transaction(
        w3, contract,
        contract.functions.emergency_unpause(),
        account_address, account
    )

    print(f"[OK] Contract UNPAUSED")
    print(f"     TX: {receipt.transactionHash.hex()}")
    print(f"     Gas: {receipt.gasUsed:,}")


def reset_circuit_breaker(network: str, confirm: bool = False):
    """Reset the circuit breaker"""
    if not confirm:
        print("[!] RESET CIRCUIT BREAKER")
        print("    This clears the failure counter and deactivates the circuit breaker.")
        print("    Note: There is a 1-hour cooldown between resets.")
        print()
        print("    To confirm, run:")
        print(f"    python scripts/emergency.py {network} reset-cb --confirm")
        return

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Only owner can reset
    owner = contract.functions.owner().call()
    if account_address.lower() != owner.lower():
        print("[ERROR] Only owner can reset circuit breaker")
        return

    print("Resetting circuit breaker...")
    try:
        receipt = send_transaction(
            w3, contract,
            contract.functions.reset_circuit_breaker(),
            account_address, account
        )
        print(f"[OK] Circuit breaker RESET")
        print(f"     TX: {receipt.transactionHash.hex()}")
        print(f"     Gas: {receipt.gasUsed:,}")
    except Exception as e:
        if "Cooldown not elapsed" in str(e):
            print("[ERROR] Cooldown period not elapsed (1 hour required)")
        else:
            raise


def transfer_ownership(network: str, new_owner: str, confirm: bool = False):
    """Transfer contract ownership"""
    if not confirm:
        print("[!] TRANSFER OWNERSHIP")
        print(f"    New owner will be: {new_owner}")
        print()
        print("    WARNING: This action is IRREVERSIBLE!")
        print("    The new owner will have full control of the contract.")
        print()
        print("    To confirm, run:")
        print(f"    python scripts/emergency.py {network} transfer {new_owner} --confirm")
        return

    if not Web3.is_address(new_owner):
        print("[ERROR] Invalid address format")
        return

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Only owner can transfer
    owner = contract.functions.owner().call()
    if account_address.lower() != owner.lower():
        print("[ERROR] Only owner can transfer ownership")
        return

    new_owner = Web3.to_checksum_address(new_owner)

    print(f"Transferring ownership to: {new_owner}")
    receipt = send_transaction(
        w3, contract,
        contract.functions.transfer_ownership(new_owner),
        account_address, account
    )

    print(f"[OK] Ownership TRANSFERRED")
    print(f"     New owner: {new_owner}")
    print(f"     TX: {receipt.transactionHash.hex()}")
    print(f"     Gas: {receipt.gasUsed:,}")


def set_emergency_admin(network: str, new_admin: str, confirm: bool = False):
    """Set emergency admin"""
    if not confirm:
        print("[!] SET EMERGENCY ADMIN")
        print(f"    New emergency admin will be: {new_admin}")
        print()
        print("    Emergency admin can PAUSE but cannot UNPAUSE the contract.")
        print()
        print("    To confirm, run:")
        print(f"    python scripts/emergency.py {network} set-admin {new_admin} --confirm")
        return

    if not Web3.is_address(new_admin):
        print("[ERROR] Invalid address format")
        return

    w3, contract = load_contract(network)
    account_address, account = get_account(w3, network)

    # Only owner can set emergency admin
    owner = contract.functions.owner().call()
    if account_address.lower() != owner.lower():
        print("[ERROR] Only owner can set emergency admin")
        return

    new_admin = Web3.to_checksum_address(new_admin)

    print(f"Setting emergency admin to: {new_admin}")
    receipt = send_transaction(
        w3, contract,
        contract.functions.set_emergency_admin(new_admin),
        account_address, account
    )

    print(f"[OK] Emergency admin SET")
    print(f"     New admin: {new_admin}")
    print(f"     TX: {receipt.transactionHash.hex()}")
    print(f"     Gas: {receipt.gasUsed:,}")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Tesseract emergency procedures")
    parser.add_argument("network", help="Network (local, sepolia, mumbai)")
    parser.add_argument("action", nargs="?", default="status",
                        help="Action: status, pause, unpause, reset-cb, transfer, set-admin")
    parser.add_argument("address", nargs="?", help="Address for transfer/set-admin")
    parser.add_argument("--confirm", action="store_true", help="Confirm dangerous actions")

    args = parser.parse_args()

    print("=" * 50)
    print("Tesseract Emergency Procedures")
    print("=" * 50)
    print()

    try:
        if args.action == "status":
            status(args.network)

        elif args.action == "pause":
            pause(args.network, args.confirm)

        elif args.action == "unpause":
            unpause(args.network, args.confirm)

        elif args.action == "reset-cb":
            reset_circuit_breaker(args.network, args.confirm)

        elif args.action == "transfer":
            if not args.address:
                print("[ERROR] Address required for 'transfer' action")
                sys.exit(1)
            transfer_ownership(args.network, args.address, args.confirm)

        elif args.action == "set-admin":
            if not args.address:
                print("[ERROR] Address required for 'set-admin' action")
                sys.exit(1)
            set_emergency_admin(args.network, args.address, args.confirm)

        else:
            print(f"[ERROR] Unknown action: {args.action}")
            print("        Valid actions: status, pause, unpause, reset-cb, transfer, set-admin")
            sys.exit(1)

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
