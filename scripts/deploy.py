#!/usr/bin/env python3
"""
Tesseract Deployment Script
Deploys the TesseractBuffer contract with proper configuration
"""

import os
import json
from ape import accounts, project, networks

def main():
    """Main deployment function."""
    print("🚀 Starting Tesseract deployment...")

    # Load deployer account
    try:
        if os.getenv("USE_TEST_ACCOUNT"):
            deployer = accounts.test_accounts[0]
            print("📝 Using test account for deployment")
        else:
            deployer = accounts.load("deployer")
            print(f"👤 Deployer address: {deployer.address}")
    except Exception as e:
        print(f"❌ Error loading deployer account: {e}")
        return

    # Get current network info
    current_network = networks.active_provider.network.name
    print(f"🌐 Deploying to network: {current_network}")

    # Deploy the main contract
    try:
        print("⚙️  Compiling and deploying TesseractBuffer...")
        contract = deployer.deploy(project.TesseractBuffer)

        print(f"✅ Contract deployed successfully!")
        print(f"📍 Contract address: {contract.address}")
        print(f"🔗 Transaction hash: {contract.txn_hash}")

        # Verify deployment
        owner = contract.owner()
        print(f"👑 Contract owner: {owner}")

        # Save deployment info
        deployment_info = {
            "network": current_network,
            "contract_address": str(contract.address),
            "deployer": str(deployer.address),
            "transaction_hash": str(contract.txn_hash),
            "block_number": contract.receipt.block_number,
            "deployment_timestamp": contract.receipt.timestamp
        }

        # Create deployments directory if it doesn't exist
        os.makedirs("deployments", exist_ok=True)

        # Save to file
        filename = f"deployments/{current_network}_deployment.json"
        with open(filename, "w") as f:
            json.dump(deployment_info, f, indent=2)

        print(f"💾 Deployment info saved to: {filename}")

        # Display next steps
        print("\n🎯 Next steps:")
        print("1. Initialize the contract with proper roles")
        print("2. Configure system parameters")
        print("3. Set up monitoring and alerts")
        print(f"4. Run: ape run scripts/initialize.py --network {current_network}")

        return contract

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return None

if __name__ == "__main__":
    main()