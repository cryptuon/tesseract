#!/usr/bin/env python3
"""
Tesseract Post-Deployment Verification Script

Verifies that a deployed contract is functioning correctly.
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()


def load_deployment_info(network: str):
    """Load deployment information"""
    deployment_file = Path(f"deployments/{network}_deployment.json")
    if not deployment_file.exists():
        print(f"[ERROR] Deployment file not found: {deployment_file}")
        print("        Run deploy_simple.py first")
        return None

    with open(deployment_file) as f:
        return json.load(f)


def load_abi():
    """Load contract ABI"""
    abi_file = Path("deployments/TesseractBuffer_abi.json")
    if not abi_file.exists():
        print("[ERROR] ABI file not found")
        return None

    with open(abi_file) as f:
        return json.load(f)


def get_web3(network: str):
    """Get Web3 instance for network"""
    config_path = Path("config/networks.json")
    with open(config_path) as f:
        networks = json.load(f)["networks"]

    net_config = networks[network]

    if "rpc_url" in net_config:
        rpc_url = net_config["rpc_url"]
    else:
        api_key = os.getenv("ALCHEMY_API_KEY", "")
        rpc_url = net_config["rpc_url_template"].replace("{ALCHEMY_API_KEY}", api_key)

    return Web3(Web3.HTTPProvider(rpc_url))


def verify_contract_exists(w3, address: str):
    """Verify contract code exists at address"""
    print(f"Verifying contract at {address}...")

    code = w3.eth.get_code(address)
    if len(code) <= 2:  # Empty code is '0x' or b''
        print("[ERROR] No contract code at address")
        return False

    print(f"[OK] Contract code exists ({len(code):,} bytes)")
    return True


def verify_owner(contract, expected_owner: str = None):
    """Verify contract owner"""
    owner = contract.functions.owner().call()
    print(f"Contract owner: {owner}")

    if expected_owner:
        if owner.lower() == expected_owner.lower():
            print("[OK] Owner matches expected deployer")
            return True
        else:
            print(f"[WARN] Owner mismatch! Expected: {expected_owner}")
            return False

    return True


def verify_initial_state(contract):
    """Verify contract initial state"""
    print()
    print("Checking initial state...")

    checks = []

    # Check paused state
    paused = contract.functions.paused().call()
    if not paused:
        print("[OK] Contract is not paused")
        checks.append(True)
    else:
        print("[WARN] Contract is paused!")
        checks.append(False)

    # Check circuit breaker
    cb_active = contract.functions.circuit_breaker_active().call()
    if not cb_active:
        print("[OK] Circuit breaker is not active")
        checks.append(True)
    else:
        print("[WARN] Circuit breaker is active!")
        checks.append(False)

    # Check coordination window
    window = contract.functions.coordination_window().call()
    print(f"[INFO] Coordination window: {window} seconds")
    checks.append(True)

    # Check transaction count
    tx_count = contract.functions.transaction_count().call()
    print(f"[INFO] Transaction count: {tx_count}")
    checks.append(True)

    # Check max payload size
    max_payload = contract.functions.max_payload_size().call()
    print(f"[INFO] Max payload size: {max_payload} bytes")
    checks.append(True)

    # Check circuit breaker threshold
    cb_threshold = contract.functions.circuit_breaker_threshold().call()
    print(f"[INFO] Circuit breaker threshold: {cb_threshold}")
    checks.append(True)

    return all(checks)


def verify_read_functions(contract):
    """Verify read-only functions work"""
    print()
    print("Testing read functions...")

    try:
        # Test owner
        owner = contract.functions.owner().call()
        print(f"  owner(): {owner}")

        # Test emergency admin
        emergency_admin = contract.functions.emergency_admin().call()
        print(f"  emergency_admin(): {emergency_admin}")

        # Test paused
        paused = contract.functions.paused().call()
        print(f"  paused(): {paused}")

        # Test transaction count
        count = contract.functions.transaction_count().call()
        print(f"  transaction_count(): {count}")

        # Test get_transaction_state for non-existent tx
        empty_state = contract.functions.get_transaction_state(b'\x01' * 32).call()
        print(f"  get_transaction_state(): {empty_state} (EMPTY)")

        print("[OK] All read functions working")
        return True

    except Exception as e:
        print(f"[ERROR] Read function failed: {e}")
        return False


def verify_events(w3, contract, from_block: int):
    """Verify events can be retrieved"""
    print()
    print("Checking events...")

    try:
        # Get all events from deployment block
        events = []

        # Check for RoleGranted events
        role_granted = contract.events.RoleGranted.get_logs(fromBlock=from_block)
        events.extend(role_granted)
        print(f"  RoleGranted events: {len(role_granted)}")

        print(f"[OK] Event retrieval working ({len(events)} total events)")
        return True

    except Exception as e:
        print(f"[WARN] Event retrieval failed: {e}")
        return False


def main():
    """Main verification function"""
    print("=" * 50)
    print("Tesseract Deployment Verification")
    print("=" * 50)
    print()

    # Parse arguments
    network = sys.argv[1] if len(sys.argv) > 1 else "local"
    print(f"Network: {network}")
    print()

    # Load deployment info
    deployment = load_deployment_info(network)
    if not deployment:
        sys.exit(1)

    print(f"Contract: {deployment['contract_address']}")
    print(f"Deployed at block: {deployment['block_number']}")
    print()

    # Load ABI
    abi = load_abi()
    if not abi:
        sys.exit(1)

    # Connect to network
    w3 = get_web3(network)
    if not w3.is_connected():
        print("[ERROR] Cannot connect to network")
        sys.exit(1)

    print(f"[OK] Connected to network (Chain ID: {w3.eth.chain_id})")
    print()

    # Get contract instance
    contract = w3.eth.contract(
        address=deployment['contract_address'],
        abi=abi
    )

    # Run verifications
    results = {
        "code_exists": verify_contract_exists(w3, deployment['contract_address']),
        "owner": verify_owner(contract, deployment.get('deployer')),
        "initial_state": verify_initial_state(contract),
        "read_functions": verify_read_functions(contract),
        "events": verify_events(w3, contract, deployment['block_number']),
    }

    # Summary
    print()
    print("=" * 50)
    print("Verification Summary")
    print("=" * 50)

    all_ok = all(results.values())
    for check, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")

    print()
    if all_ok:
        print("Deployment verification PASSED!")
        print()
        print("Contract is ready for use.")
        print(f"Address: {deployment['contract_address']}")
        if deployment.get('network') != 'local':
            config_path = Path("config/networks.json")
            with open(config_path) as f:
                networks = json.load(f)["networks"]
            explorer = networks.get(network, {}).get('explorer_url')
            if explorer:
                print(f"Explorer: {explorer}/address/{deployment['contract_address']}")
    else:
        print("Deployment verification FAILED!")
        print("Some checks did not pass. Review the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
