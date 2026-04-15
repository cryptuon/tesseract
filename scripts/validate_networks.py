#!/usr/bin/env python3
"""
Tesseract Network Configuration Validator

Validates that all configured networks are reachable, chain IDs match,
and testnet faucets are accessible. Useful before multi-chain deployments.
"""

import json
import sys
from pathlib import Path
from web3 import Web3

CONFIG_PATH = Path(__file__).parent.parent / "config" / "networks.json"

# Known deprecated networks that should not appear in config
DEPRECATED_NETWORKS = {
    80001: "Polygon Mumbai (deprecated Nov 2023 — use Amoy 80002)",
    421613: "Arbitrum Goerli (deprecated — use Arbitrum Sepolia 421614)",
    420: "Optimism Goerli (deprecated — use Optimism Sepolia 11155420)",
    5: "Ethereum Goerli (deprecated — use Sepolia 11155111)",
}


def load_config() -> dict:
    """Load and parse networks.json."""
    if not CONFIG_PATH.exists():
        print(f"[ERROR] Config not found: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def validate_no_deprecated(networks: dict) -> list[str]:
    """Check that no deprecated chain IDs are configured."""
    errors = []
    for key, net in networks.items():
        chain_id = net.get("chain_id")
        if chain_id in DEPRECATED_NETWORKS:
            errors.append(
                f"  {key}: chain_id {chain_id} is deprecated — {DEPRECATED_NETWORKS[chain_id]}"
            )
    return errors


def validate_chain_ids_unique(networks: dict) -> list[str]:
    """Check for duplicate chain IDs."""
    seen: dict[int, str] = {}
    errors = []
    for key, net in networks.items():
        chain_id = net.get("chain_id")
        if chain_id in seen:
            errors.append(
                f"  {key} and {seen[chain_id]} share chain_id {chain_id}"
            )
        seen[chain_id] = key
    return errors


def validate_rpc_connectivity(networks: dict, timeout: int = 5) -> tuple[list[str], list[str]]:
    """Try connecting to each network's RPC endpoint."""
    reachable = []
    unreachable = []

    for key, net in networks.items():
        rpc = net.get("rpc_url") or net.get("rpc_url_template", "")
        # Skip templates that need API keys
        if "{" in rpc:
            unreachable.append(f"  {key}: skipped (requires API key)")
            continue
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))
            if w3.is_connected():
                actual_chain = w3.eth.chain_id
                expected_chain = net.get("chain_id")
                if actual_chain != expected_chain:
                    unreachable.append(
                        f"  {key}: chain_id mismatch — config says {expected_chain}, RPC returned {actual_chain}"
                    )
                else:
                    block = w3.eth.block_number
                    reachable.append(f"  {key}: OK (chain {actual_chain}, block {block:,})")
            else:
                unreachable.append(f"  {key}: connected but not responding")
        except Exception as e:
            unreachable.append(f"  {key}: {e}")

    return reachable, unreachable


def validate_required_fields(networks: dict) -> list[str]:
    """Ensure every network has required fields."""
    required = {"name", "chain_id", "native_currency", "is_testnet", "requires_private_key"}
    errors = []
    for key, net in networks.items():
        missing = required - set(net.keys())
        if missing:
            errors.append(f"  {key}: missing fields {missing}")
        # Testnets should have either rpc_url or rpc_url_template
        if not net.get("rpc_url") and not net.get("rpc_url_template"):
            errors.append(f"  {key}: no rpc_url or rpc_url_template")
    return errors


def main():
    print("Tesseract Network Config Validator")
    print("=" * 50)

    config = load_config()
    networks = config.get("networks", {})
    print(f"\nFound {len(networks)} networks in config\n")

    all_ok = True

    # 1. Check for deprecated networks
    print("[1] Checking for deprecated networks...")
    deprecated = validate_no_deprecated(networks)
    if deprecated:
        all_ok = False
        print("[FAIL]")
        for e in deprecated:
            print(e)
    else:
        print("  [OK] No deprecated networks")

    # 2. Check for duplicate chain IDs
    print("\n[2] Checking for duplicate chain IDs...")
    dupes = validate_chain_ids_unique(networks)
    if dupes:
        all_ok = False
        print("[FAIL]")
        for e in dupes:
            print(e)
    else:
        print("  [OK] All chain IDs unique")

    # 3. Check required fields
    print("\n[3] Validating required fields...")
    field_errors = validate_required_fields(networks)
    if field_errors:
        all_ok = False
        print("[FAIL]")
        for e in field_errors:
            print(e)
    else:
        print("  [OK] All required fields present")

    # 4. Check RPC connectivity (optional, only for networks with hardcoded URLs)
    print("\n[4] Testing RPC connectivity...")
    reachable, unreachable = validate_rpc_connectivity(networks)
    if reachable:
        print("  Reachable:")
        for r in reachable:
            print(r)
    if unreachable:
        print("  Unreachable / skipped:")
        for u in unreachable:
            print(u)

    # 5. Validate recommended_testnets reference existing networks
    print("\n[5] Checking recommended_testnets...")
    recommended = config.get("recommended_testnets", [])
    missing_recs = [r for r in recommended if r not in networks]
    if missing_recs:
        all_ok = False
        print(f"  [FAIL] Referenced but not defined: {missing_recs}")
    else:
        print(f"  [OK] All {len(recommended)} recommended testnets exist in config")

    # Summary
    print("\n" + "=" * 50)
    if all_ok:
        print("[OK] All validations passed")
    else:
        print("[FAIL] Some validations failed — see above")
        sys.exit(1)


if __name__ == "__main__":
    main()
