#!/usr/bin/env python3
"""
Tesseract Multi-Chain Deployment Script
Deploys TesseractBuffer contract across multiple networks
"""

import os
import json
import time
from ape import accounts, project, networks

# Supported testnet networks
NETWORKS = [
    "ethereum:sepolia:alchemy",
    "polygon:amoy:alchemy",
    "arbitrum:arbitrum-sepolia:alchemy",
    "optimism:optimism-sepolia:alchemy",
    "base:base-sepolia:alchemy"
]

def deploy_to_network(network_name: str) -> dict:
    """Deploy contract to a specific network."""
    print(f"\n🌐 Deploying to {network_name}...")

    try:
        with networks.parse_network_choice(network_name):
            # Load deployer account
            if os.getenv("USE_TEST_ACCOUNT"):
                deployer = accounts.test_accounts[0]
            else:
                deployer = accounts.load("deployer")

            print(f"👤 Deployer: {deployer.address}")

            # Check balance
            balance = deployer.balance
            print(f"💰 Balance: {balance / 10**18:.4f} ETH")

            if balance < 10**17:  # 0.1 ETH
                print("⚠️  Low balance warning - deployment may fail")

            # Deploy contract
            print("⚙️  Deploying contract...")
            contract = deployer.deploy(project.TesseractBuffer)

            deployment_info = {
                "network": network_name,
                "contract_address": str(contract.address),
                "deployer": str(deployer.address),
                "transaction_hash": str(contract.txn_hash),
                "block_number": contract.receipt.block_number,
                "deployment_timestamp": contract.receipt.timestamp,
                "gas_used": contract.receipt.gas_used,
                "gas_price": contract.receipt.gas_price if hasattr(contract.receipt, 'gas_price') else 0
            }

            print(f"✅ Deployed to {network_name}")
            print(f"📍 Contract: {contract.address}")
            print(f"⛽ Gas used: {deployment_info['gas_used']:,}")

            return deployment_info

    except Exception as e:
        print(f"❌ Failed to deploy to {network_name}: {e}")
        return {
            "network": network_name,
            "error": str(e),
            "deployed": False
        }

def main():
    """Main multi-chain deployment function."""
    print("🚀 Starting multi-chain Tesseract deployment...")

    # Create deployments directory
    os.makedirs("deployments", exist_ok=True)

    all_deployments = {}
    successful_deployments = []
    failed_deployments = []

    for network in NETWORKS:
        deployment_info = deploy_to_network(network)

        if "error" in deployment_info:
            failed_deployments.append(deployment_info)
        else:
            successful_deployments.append(deployment_info)

            # Save individual deployment file
            network_safe_name = network.replace(":", "_")
            filename = f"deployments/{network_safe_name}_deployment.json"

            with open(filename, "w") as f:
                json.dump(deployment_info, f, indent=2)

            print(f"💾 Saved deployment info: {filename}")

        all_deployments[network] = deployment_info

        # Add delay between deployments to avoid rate limiting
        if network != NETWORKS[-1]:
            print("⏱️  Waiting 10 seconds before next deployment...")
            time.sleep(10)

    # Save summary file
    summary = {
        "total_networks": len(NETWORKS),
        "successful_deployments": len(successful_deployments),
        "failed_deployments": len(failed_deployments),
        "deployments": all_deployments,
        "deployment_timestamp": int(time.time())
    }

    with open("deployments/multi_chain_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Print summary
    print("\n" + "="*60)
    print("📊 DEPLOYMENT SUMMARY")
    print("="*60)

    if successful_deployments:
        print(f"✅ Successful deployments ({len(successful_deployments)}):")
        for deployment in successful_deployments:
            network = deployment['network'].split(':')[0].upper()
            address = deployment['contract_address']
            gas_used = deployment.get('gas_used', 'N/A')
            print(f"  • {network}: {address} (Gas: {gas_used:,})")

    if failed_deployments:
        print(f"\n❌ Failed deployments ({len(failed_deployments)}):")
        for deployment in failed_deployments:
            network = deployment['network'].split(':')[0].upper()
            error = deployment['error']
            print(f"  • {network}: {error}")

    print(f"\n💾 Summary saved to: deployments/multi_chain_summary.json")

    if successful_deployments:
        print("\n🎯 Next steps:")
        print("1. Initialize contracts on each network:")
        for deployment in successful_deployments:
            network_name = deployment['network']
            print(f"   ape run scripts/initialize.py --network {network_name}")

        print("\n2. Set up cross-chain coordination")
        print("3. Configure monitoring for all networks")
        print("4. Run cross-chain tests")

        # Generate initialization script
        generate_init_script(successful_deployments)

    return all_deployments

def generate_init_script(deployments):
    """Generate a script to initialize all deployed contracts."""
    script_content = """#!/bin/bash
# Auto-generated multi-chain initialization script

echo "🔧 Initializing all deployed Tesseract contracts..."

"""

    for deployment in deployments:
        network = deployment['network']
        script_content += f"""
echo "🌐 Initializing {network}..."
ape run scripts/initialize.py --network {network}
if [ $? -eq 0 ]; then
    echo "✅ {network} initialized successfully"
else
    echo "❌ Failed to initialize {network}"
fi
"""

    script_content += """
echo "🎉 Multi-chain initialization completed!"
"""

    with open("scripts/initialize_all.sh", "w") as f:
        f.write(script_content)

    os.chmod("scripts/initialize_all.sh", 0o755)
    print("📝 Generated initialization script: scripts/initialize_all.sh")

if __name__ == "__main__":
    main()