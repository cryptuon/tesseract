"""
Test suite for Tesseract contract compilation
"""

import pytest
from pathlib import Path
from vyper import compile_code


def test_contract_compilation():
    """Test that TesseractSimple.vy compiles successfully"""
    contract_path = Path(__file__).parent.parent / "contracts" / "TesseractSimple.vy"

    with open(contract_path, 'r') as f:
        source_code = f.read()

    # Compile contract
    compiled = compile_code(
        source_code,
        output_formats=['bytecode', 'abi']
    )

    # Verify compilation
    assert 'bytecode' in compiled
    assert 'abi' in compiled
    assert len(compiled['bytecode']) > 0
    assert len(compiled['abi']) > 0


def test_contract_abi_functions():
    """Test that contract ABI contains expected functions"""
    contract_path = Path(__file__).parent.parent / "contracts" / "TesseractSimple.vy"

    with open(contract_path, 'r') as f:
        source_code = f.read()

    compiled = compile_code(source_code, output_formats=['abi'])
    abi = compiled['abi']

    # Extract function names
    function_names = [item['name'] for item in abi if item['type'] == 'function']

    # Expected functions
    expected_functions = [
        'add_operator',
        'remove_operator',
        'buffer_transaction',
        'resolve_dependency',
        'is_transaction_ready',
        'get_transaction_state',
        'get_transaction_details',
        'mark_executed',
        'set_coordination_window'
    ]

    for func in expected_functions:
        assert func in function_names, f"Function {func} not found in ABI"


def test_contract_events():
    """Test that contract ABI contains expected events"""
    contract_path = Path(__file__).parent.parent / "contracts" / "TesseractSimple.vy"

    with open(contract_path, 'r') as f:
        source_code = f.read()

    compiled = compile_code(source_code, output_formats=['abi'])
    abi = compiled['abi']

    # Extract event names
    event_names = [item['name'] for item in abi if item['type'] == 'event']

    # Expected events
    expected_events = [
        'TransactionBuffered',
        'TransactionReady',
        'TransactionFailed'
    ]

    for event in expected_events:
        assert event in event_names, f"Event {event} not found in ABI"


if __name__ == "__main__":
    test_contract_compilation()
    test_contract_abi_functions()
    test_contract_events()
    print("All compilation tests passed!")