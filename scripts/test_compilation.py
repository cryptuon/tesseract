#!/usr/bin/env python3
"""
Simple compilation test for Tesseract contract
Tests only compilation and ABI generation
"""

import json
from vyper import compile_code
from pathlib import Path

def main():
    """Test contract compilation and generate deployment artifacts"""
    print("🔨 Tesseract Compilation Test")
    print("=" * 35)

    try:
        # Read contract source
        contract_path = Path("contracts/TesseractSimple.vy")
        print(f"📄 Reading contract: {contract_path}")

        if not contract_path.exists():
            print(f"❌ Contract file not found: {contract_path}")
            return False

        with open(contract_path, 'r') as f:
            source_code = f.read()

        # Compile contract
        print("⚙️  Compiling contract...")
        compiled = compile_code(
            source_code,
            output_formats=['bytecode', 'abi']
        )

        print("✅ Compilation successful!")

        # Display results
        bytecode = compiled['bytecode']
        abi = compiled['abi']

        print(f"📦 Bytecode length: {len(bytecode)} bytes")
        print(f"🔧 ABI items: {len(abi)}")

        # Show functions
        functions = [item['name'] for item in abi if item['type'] == 'function']
        print(f"🛠️  Functions: {', '.join(functions)}")

        # Save compilation artifacts
        artifacts = {
            'contractName': 'TesseractSimple',
            'abi': abi,
            'bytecode': bytecode,
            'compiler': 'vyper',
            'version': '0.3.10'
        }

        # Create artifacts directory
        artifacts_dir = Path('artifacts')
        artifacts_dir.mkdir(exist_ok=True)

        artifact_file = artifacts_dir / 'TesseractSimple.json'
        with open(artifact_file, 'w') as f:
            json.dump(artifacts, f, indent=2)

        print(f"💾 Artifacts saved to: {artifact_file}")

        # Test basic contract construction
        print("\n🧪 Testing contract construction...")

        # Check that constructor exists
        constructor_abi = [item for item in abi if item['type'] == 'constructor']
        print(f"🏗️  Constructor found: {len(constructor_abi) > 0}")

        # Check required functions exist
        required_functions = [
            'owner', 'buffer_transaction', 'resolve_dependency',
            'is_transaction_ready', 'get_transaction_state'
        ]

        missing_functions = set(required_functions) - set(functions)
        if missing_functions:
            print(f"❌ Missing required functions: {', '.join(missing_functions)}")
            return False

        print("✅ All required functions present!")

        # Show contract size info
        print(f"\n📊 Contract Statistics:")
        print(f"   📦 Bytecode size: {len(bytecode):,} bytes")
        print(f"   🔧 Functions: {len(functions)}")
        print(f"   📋 Events: {len([item for item in abi if item['type'] == 'event'])}")

        print("\n🎉 Compilation test completed successfully!")
        print("\n🎯 Next steps:")
        print("   1. Deploy to local test network")
        print("   2. Test transaction buffering")
        print("   3. Deploy to testnet")

        return True

    except Exception as e:
        print(f"❌ Compilation failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)