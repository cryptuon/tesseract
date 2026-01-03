#!/usr/bin/env python3
"""
Tesseract Health Check Script

Monitors contract health status including:
- Node connectivity
- Contract responsiveness
- Pause status
- Circuit breaker status
- Transaction metrics
"""

import os
import sys
import json
import time
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()


class HealthChecker:
    def __init__(self, network: str = "local"):
        self.network = network
        self.w3 = None
        self.contract = None
        self.config = None

    def load_config(self):
        """Load network and deployment configuration"""
        config_path = Path("config/networks.json")
        with open(config_path) as f:
            self.config = json.load(f)["networks"].get(self.network)

        if not self.config:
            raise ValueError(f"Unknown network: {self.network}")

        return True

    def connect(self):
        """Connect to network"""
        if "rpc_url" in self.config:
            rpc_url = self.config["rpc_url"]
        else:
            api_key = os.getenv("ALCHEMY_API_KEY", "")
            rpc_url = self.config["rpc_url_template"].replace("{ALCHEMY_API_KEY}", api_key)

        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
        return self.w3.is_connected()

    def load_contract(self):
        """Load deployed contract"""
        deployment_file = Path(f"deployments/{self.network}_deployment.json")
        abi_file = Path("deployments/TesseractBuffer_abi.json")

        if not deployment_file.exists() or not abi_file.exists():
            return False

        with open(deployment_file) as f:
            deployment = json.load(f)

        with open(abi_file) as f:
            abi = json.load(f)

        self.contract = self.w3.eth.contract(
            address=deployment['contract_address'],
            abi=abi
        )
        return True

    def check_connectivity(self):
        """Check node connectivity"""
        result = {
            "check": "connectivity",
            "status": "unknown",
            "details": {}
        }

        try:
            if self.w3.is_connected():
                chain_id = self.w3.eth.chain_id
                block_number = self.w3.eth.block_number
                block = self.w3.eth.get_block('latest')

                result["status"] = "healthy"
                result["details"] = {
                    "chain_id": chain_id,
                    "block_number": block_number,
                    "block_timestamp": block.timestamp,
                    "peer_count": self.w3.net.peer_count if hasattr(self.w3.net, 'peer_count') else "N/A"
                }
            else:
                result["status"] = "unhealthy"
                result["details"]["error"] = "Not connected"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)

        return result

    def check_contract_state(self):
        """Check contract operational state"""
        result = {
            "check": "contract_state",
            "status": "unknown",
            "details": {}
        }

        try:
            paused = self.contract.functions.paused().call()
            cb_active = self.contract.functions.circuit_breaker_active().call()
            owner = self.contract.functions.owner().call()
            emergency_admin = self.contract.functions.emergency_admin().call()

            result["details"] = {
                "paused": paused,
                "circuit_breaker_active": cb_active,
                "owner": owner,
                "emergency_admin": emergency_admin
            }

            if paused:
                result["status"] = "degraded"
                result["details"]["warning"] = "Contract is paused"
            elif cb_active:
                result["status"] = "degraded"
                result["details"]["warning"] = "Circuit breaker is active"
            else:
                result["status"] = "healthy"

        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)

        return result

    def check_transaction_metrics(self):
        """Check transaction metrics"""
        result = {
            "check": "transaction_metrics",
            "status": "unknown",
            "details": {}
        }

        try:
            tx_count = self.contract.functions.transaction_count().call()
            failure_count = self.contract.functions.failure_count().call()
            cb_threshold = self.contract.functions.circuit_breaker_threshold().call()

            failure_ratio = failure_count / max(tx_count, 1)

            result["details"] = {
                "total_transactions": tx_count,
                "failure_count": failure_count,
                "failure_ratio": round(failure_ratio, 4),
                "circuit_breaker_threshold": cb_threshold
            }

            if failure_ratio > 0.1:  # More than 10% failure
                result["status"] = "degraded"
                result["details"]["warning"] = "High failure rate"
            else:
                result["status"] = "healthy"

        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)

        return result

    def check_configuration(self):
        """Check contract configuration"""
        result = {
            "check": "configuration",
            "status": "unknown",
            "details": {}
        }

        try:
            coordination_window = self.contract.functions.coordination_window().call()
            max_payload_size = self.contract.functions.max_payload_size().call()
            cb_threshold = self.contract.functions.circuit_breaker_threshold().call()

            result["details"] = {
                "coordination_window": coordination_window,
                "max_payload_size": max_payload_size,
                "circuit_breaker_threshold": cb_threshold
            }
            result["status"] = "healthy"

        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)

        return result

    def run_all_checks(self):
        """Run all health checks"""
        checks = []

        # Connectivity
        checks.append(self.check_connectivity())

        if self.contract:
            checks.append(self.check_contract_state())
            checks.append(self.check_transaction_metrics())
            checks.append(self.check_configuration())

        return checks


def main():
    """Main health check function"""
    network = sys.argv[1] if len(sys.argv) > 1 else "local"
    output_format = sys.argv[2] if len(sys.argv) > 2 else "text"

    checker = HealthChecker(network)

    try:
        checker.load_config()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if not checker.connect():
        print(f"[ERROR] Cannot connect to {network}")
        sys.exit(1)

    if not checker.load_contract():
        print(f"[WARN] No deployment found for {network}")
        print("       Contract-specific checks will be skipped")

    checks = checker.run_all_checks()

    if output_format == "json":
        # JSON output for automation
        output = {
            "network": network,
            "timestamp": int(time.time()),
            "checks": checks,
            "overall_status": "healthy" if all(c["status"] == "healthy" for c in checks) else "degraded"
        }
        print(json.dumps(output, indent=2))
    else:
        # Text output for humans
        print("=" * 50)
        print(f"Tesseract Health Check - {network}")
        print("=" * 50)
        print()

        all_healthy = True
        for check in checks:
            status = check["status"].upper()
            if status == "HEALTHY":
                status_icon = "[OK]"
            elif status == "DEGRADED":
                status_icon = "[WARN]"
                all_healthy = False
            else:
                status_icon = "[FAIL]"
                all_healthy = False

            print(f"{status_icon} {check['check']}: {status}")

            for key, value in check["details"].items():
                print(f"      {key}: {value}")
            print()

        print("=" * 50)
        if all_healthy:
            print("Overall Status: HEALTHY")
        else:
            print("Overall Status: DEGRADED/UNHEALTHY")
            sys.exit(1)


if __name__ == "__main__":
    main()
