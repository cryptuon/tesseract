#!/usr/bin/env python3
"""
Tesseract Initialization Script
Sets up roles and initial configuration for the deployed contract
"""

import os
import json
import sys
from ape import accounts, Contract, networks

def load_deployment_info():
    """Load deployment information from file."""
    current_network = networks.active_provider.network.name
    filename = f"deployments/{current_network}_deployment.json"

    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Deployment file not found: {filename}")
        print("Please deploy the contract first using: ape run scripts/deploy.py")
        sys.exit(1)

def main():
    """Main initialization function."""
    print("🔧 Starting Tesseract initialization...")

    # Load deployment info
    deployment_info = load_deployment_info()
    contract_address = deployment_info["contract_address"]
    print(f"📍 Contract address: {contract_address}")

    # Load accounts
    try:
        if os.getenv("USE_TEST_ACCOUNT"):
            deployer = accounts.test_accounts[0]
            operator = accounts.test_accounts[1]
            resolver = accounts.test_accounts[2]
            print("📝 Using test accounts for initialization")
        else:
            deployer = accounts.load("deployer")
            operator = accounts.load("operator")
            resolver = accounts.load("resolver")
            print("👤 Using configured accounts")
    except Exception as e:
        print(f"❌ Error loading accounts: {e}")
        print("Please ensure accounts are properly configured")
        return

    # Load contract
    try:
        contract = Contract(contract_address)
        print("📄 Contract loaded successfully")
    except Exception as e:
        print(f"❌ Error loading contract: {e}")
        return

    # Verify contract owner
    current_owner = contract.owner()
    if current_owner != deployer.address:
        print(f"❌ Deployer address mismatch. Expected: {deployer.address}, Got: {current_owner}")
        return

    print("🔑 Setting up roles...")

    try:
        # Get role constants
        buffer_role = contract.BUFFER_ROLE()
        resolve_role = contract.RESOLVE_ROLE()
        admin_role = contract.ADMIN_ROLE()

        # Grant BUFFER_ROLE to operator
        if not contract.has_role(buffer_role, operator.address):
            print(f"👤 Granting BUFFER_ROLE to {operator.address}")
            tx = contract.grant_role(buffer_role, operator.address, sender=deployer)
            print(f"✅ Buffer role granted. Tx: {tx.txn_hash}")
        else:
            print(f"ℹ️  Operator already has BUFFER_ROLE")

        # Grant RESOLVE_ROLE to resolver
        if not contract.has_role(resolve_role, resolver.address):
            print(f"👤 Granting RESOLVE_ROLE to {resolver.address}")
            tx = contract.grant_role(resolve_role, resolver.address, sender=deployer)
            print(f"✅ Resolve role granted. Tx: {tx.txn_hash}")
        else:
            print(f"ℹ️  Resolver already has RESOLVE_ROLE")

        # Grant ADMIN_ROLE to operator (for operational management)
        if not contract.has_role(admin_role, operator.address):
            print(f"👤 Granting ADMIN_ROLE to {operator.address}")
            tx = contract.grant_role(admin_role, operator.address, sender=deployer)
            print(f"✅ Admin role granted. Tx: {tx.txn_hash}")
        else:
            print(f"ℹ️  Operator already has ADMIN_ROLE")

    except Exception as e:
        print(f"❌ Error setting up roles: {e}")
        return

    print("⚙️  Configuring system parameters...")

    try:
        # Set coordination window (30 seconds default)
        coordination_window = int(os.getenv("COORDINATION_WINDOW", "30"))
        if contract.coordination_window() != coordination_window:
            print(f"⏱️  Setting coordination window to {coordination_window} seconds")
            tx = contract.set_coordination_window(coordination_window, sender=deployer)
            print(f"✅ Coordination window set. Tx: {tx.txn_hash}")

        # Set max payload size
        max_payload_size = int(os.getenv("MAX_PAYLOAD_SIZE", "2048"))
        if contract.max_payload_size() != max_payload_size:
            print(f"📦 Setting max payload size to {max_payload_size} bytes")
            tx = contract.set_max_payload_size(max_payload_size, sender=deployer)
            print(f"✅ Max payload size set. Tx: {tx.txn_hash}")

        # Set circuit breaker threshold
        circuit_breaker_threshold = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "50"))
        if contract.circuit_breaker_threshold() != circuit_breaker_threshold:
            print(f"🔄 Setting circuit breaker threshold to {circuit_breaker_threshold}")
            tx = contract.set_circuit_breaker_threshold(circuit_breaker_threshold, sender=deployer)
            print(f"✅ Circuit breaker threshold set. Tx: {tx.txn_hash}")

        # Set emergency admin if different from deployer
        emergency_admin = os.getenv("EMERGENCY_ADMIN", deployer.address)
        if contract.emergency_admin() != emergency_admin:
            print(f"🚨 Setting emergency admin to {emergency_admin}")
            tx = contract.set_emergency_admin(emergency_admin, sender=deployer)
            print(f"✅ Emergency admin set. Tx: {tx.txn_hash}")

    except Exception as e:
        print(f"❌ Error configuring parameters: {e}")
        return

    print("🔍 Verifying configuration...")

    # Verify roles
    print(f"👤 Operator BUFFER_ROLE: {contract.has_role(buffer_role, operator.address)}")
    print(f"👤 Resolver RESOLVE_ROLE: {contract.has_role(resolve_role, resolver.address)}")
    print(f"👤 Operator ADMIN_ROLE: {contract.has_role(admin_role, operator.address)}")

    # Verify parameters
    print(f"⏱️  Coordination window: {contract.coordination_window()} seconds")
    print(f"📦 Max payload size: {contract.max_payload_size()} bytes")
    print(f"🔄 Circuit breaker threshold: {contract.circuit_breaker_threshold()}")
    print(f"🚨 Emergency admin: {contract.emergency_admin()}")
    print(f"⏸️  Contract paused: {contract.paused()}")

    # Save initialization info
    init_info = {
        **deployment_info,
        "initialized": True,
        "operator_address": str(operator.address),
        "resolver_address": str(resolver.address),
        "coordination_window": contract.coordination_window(),
        "max_payload_size": contract.max_payload_size(),
        "circuit_breaker_threshold": contract.circuit_breaker_threshold(),
        "emergency_admin": contract.emergency_admin()
    }

    current_network = networks.active_provider.network.name
    filename = f"deployments/{current_network}_deployment.json"
    with open(filename, "w") as f:
        json.dump(init_info, f, indent=2)

    print(f"💾 Configuration saved to: {filename}")

    print("\n✅ Tesseract initialization completed!")
    print("\n🎯 Next steps:")
    print("1. Run tests to verify functionality")
    print("2. Set up monitoring and alerts")
    print("3. Configure cross-chain coordination")
    print("4. Deploy to other networks if needed")

if __name__ == "__main__":
    main()