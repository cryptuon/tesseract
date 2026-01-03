"""
Test suite for Tesseract contract compilation (TesseractBuffer.vy)
"""

import pytest
from pathlib import Path
from vyper import compile_code


CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "TesseractBuffer.vy"


@pytest.fixture(scope="module")
def compiled_contract():
    """Compile TesseractBuffer.vy once for all tests in this module"""
    with open(CONTRACT_PATH, 'r') as f:
        source_code = f.read()
    return compile_code(source_code, output_formats=['bytecode', 'abi'])


@pytest.fixture(scope="module")
def contract_abi(compiled_contract):
    """Extract ABI from compiled contract"""
    return compiled_contract['abi']


@pytest.fixture(scope="module")
def function_names(contract_abi):
    """Extract function names from ABI"""
    return [item['name'] for item in contract_abi if item['type'] == 'function']


@pytest.fixture(scope="module")
def event_names(contract_abi):
    """Extract event names from ABI"""
    return [item['name'] for item in contract_abi if item['type'] == 'event']


class TestContractCompilation:
    """Test contract compilation"""

    def test_contract_file_exists(self):
        """Test that contract file exists"""
        assert CONTRACT_PATH.exists(), f"Contract file not found: {CONTRACT_PATH}"

    def test_contract_compiles_successfully(self, compiled_contract):
        """Test that TesseractBuffer.vy compiles successfully"""
        assert 'bytecode' in compiled_contract
        assert 'abi' in compiled_contract
        assert len(compiled_contract['bytecode']) > 0
        assert len(compiled_contract['abi']) > 0

    def test_bytecode_is_reasonable_size(self, compiled_contract):
        """Test that bytecode is within expected size range"""
        bytecode = compiled_contract['bytecode']
        # Should be larger than TesseractSimple (7,276 bytes) but reasonable
        assert len(bytecode) > 5000, "Bytecode suspiciously small"
        assert len(bytecode) < 50000, "Bytecode suspiciously large"


class TestContractFunctions:
    """Test contract ABI functions"""

    def test_has_constructor(self, contract_abi):
        """Test that contract has constructor"""
        constructors = [item for item in contract_abi if item['type'] == 'constructor']
        assert len(constructors) == 1, "Contract should have exactly one constructor"

    def test_core_transaction_functions(self, function_names):
        """Test core transaction functions exist"""
        expected = [
            'buffer_transaction',
            'resolve_dependency',
            'is_transaction_ready',
            'get_transaction_state',
            'get_transaction',
            'mark_transaction_executed'
        ]
        for func in expected:
            assert func in function_names, f"Missing core function: {func}"

    def test_access_control_functions(self, function_names):
        """Test access control functions exist"""
        expected = [
            'owner',
            'grant_role',
            'revoke_role',
            'has_role',
            'transfer_ownership'
        ]
        for func in expected:
            assert func in function_names, f"Missing access control function: {func}"

    def test_emergency_functions(self, function_names):
        """Test emergency functions exist"""
        expected = [
            'emergency_admin',
            'paused',
            'emergency_pause',
            'emergency_unpause',
            'reset_circuit_breaker',
            'circuit_breaker_active',
            'circuit_breaker_threshold',
            'set_emergency_admin'
        ]
        for func in expected:
            assert func in function_names, f"Missing emergency function: {func}"

    def test_configuration_functions(self, function_names):
        """Test configuration functions exist"""
        expected = [
            'coordination_window',
            'set_coordination_window',
            'max_payload_size',
            'set_max_payload_size',
            'set_circuit_breaker_threshold'
        ]
        for func in expected:
            assert func in function_names, f"Missing configuration function: {func}"


class TestContractEvents:
    """Test contract ABI events"""

    def test_transaction_events(self, event_names):
        """Test transaction-related events exist"""
        expected = [
            'TransactionBuffered',
            'TransactionReady',
            'TransactionFailed'
        ]
        for event in expected:
            assert event in event_names, f"Missing transaction event: {event}"

    def test_emergency_events(self, event_names):
        """Test emergency events exist"""
        expected = [
            'EmergencyPause',
            'EmergencyUnpause'
        ]
        for event in expected:
            assert event in event_names, f"Missing emergency event: {event}"

    def test_access_control_events(self, event_names):
        """Test access control events exist"""
        expected = [
            'RoleGranted',
            'RoleRevoked'
        ]
        for event in expected:
            assert event in event_names, f"Missing access control event: {event}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])