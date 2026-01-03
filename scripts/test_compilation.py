#!/usr/bin/env python3
"""
Compilation test for Tesseract contracts
Tests compilation and ABI generation for production contract (TesseractBuffer.vy)
"""

import json
from vyper import compile_code
from pathlib import Path

def main():
    """Test contract compilation and generate deployment artifacts"""
    print("Tesseract Compilation Test")
    print("=" * 35)

    try:
        # Read contract source - using TesseractBuffer.vy for production
        contract_path = Path("contracts/TesseractBuffer.vy")
        print(f"Reading contract: {contract_path}")

        if not contract_path.exists():
            print(f"[ERROR] Contract file not found: {contract_path}")
            return False

        with open(contract_path, 'r') as f:
            source_code = f.read()

        # Compile contract
        print("Compiling contract...")
        compiled = compile_code(
            source_code,
            output_formats=['bytecode', 'abi']
        )

        print("[OK] Compilation successful!")

        # Display results
        bytecode = compiled['bytecode']
        abi = compiled['abi']

        print(f"Bytecode length: {len(bytecode)} bytes")
        print(f"ABI items: {len(abi)}")

        # Show functions
        functions = [item['name'] for item in abi if item['type'] == 'function']
        print(f"Functions: {', '.join(functions)}")

        # Save compilation artifacts
        artifacts = {
            'contractName': 'TesseractBuffer',
            'abi': abi,
            'bytecode': bytecode,
            'compiler': 'vyper',
            'version': '0.3.10'
        }

        # Create artifacts directory
        artifacts_dir = Path('artifacts')
        artifacts_dir.mkdir(exist_ok=True)

        artifact_file = artifacts_dir / 'TesseractBuffer.json'
        with open(artifact_file, 'w') as f:
            json.dump(artifacts, f, indent=2)

        print(f"Artifacts saved to: {artifact_file}")

        # Test basic contract construction
        print("\nTesting contract construction...")

        # Check that constructor exists
        constructor_abi = [item for item in abi if item['type'] == 'constructor']
        print(f"Constructor found: {len(constructor_abi) > 0}")

        # Check required functions exist (TesseractBuffer.vy functions)
        required_functions = [
            'owner', 'emergency_admin', 'paused',
            'buffer_transaction', 'resolve_dependency',
            'is_transaction_ready', 'get_transaction_state', 'get_transaction',
            'mark_transaction_executed',
            'grant_role', 'revoke_role', 'has_role',
            'emergency_pause', 'emergency_unpause', 'reset_circuit_breaker',
            'set_coordination_window', 'set_max_payload_size',
            'set_circuit_breaker_threshold', 'set_emergency_admin',
            'transfer_ownership'
        ]

        missing_functions = set(required_functions) - set(functions)
        if missing_functions:
            print(f"[ERROR] Missing required functions: {', '.join(missing_functions)}")
            return False

        print("[OK] All required functions present!")

        # Check required events
        events = [item['name'] for item in abi if item['type'] == 'event']
        required_events = [
            'TransactionBuffered', 'TransactionReady', 'TransactionFailed',
            'EmergencyPause', 'EmergencyUnpause',
            'RoleGranted', 'RoleRevoked'
        ]

        missing_events = set(required_events) - set(events)
        if missing_events:
            print(f"[ERROR] Missing required events: {', '.join(missing_events)}")
            return False

        print("[OK] All required events present!")

        # Show contract size info
        print(f"\nContract Statistics:")
        print(f"   Bytecode size: {len(bytecode):,} bytes")
        print(f"   Functions: {len(functions)}")
        print(f"   Events: {len(events)}")

        print("\n[SUCCESS] Compilation test completed!")
        print("\nNext steps:")
        print("   1. Run pytest tests")
        print("   2. Deploy to local test network")
        print("   3. Deploy to testnet")

        return True

    except Exception as e:
        print(f"[ERROR] Compilation failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)