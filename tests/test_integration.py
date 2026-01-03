"""
Integration tests for TesseractBuffer.vy

Tests full transaction lifecycle and multi-transaction scenarios.
"""

import pytest
from web3 import Web3
from eth_tester.exceptions import TransactionFailed
import os


def generate_unique_tx_id(index: int) -> bytes:
    """Generate a unique transaction ID"""
    return Web3.keccak(text=f"integration_test_{index}_{os.urandom(4).hex()}")


@pytest.mark.integration
class TestFullTransactionLifecycle:
    """Test complete transaction lifecycle end-to-end"""

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_full_lifecycle_no_dependency(
        self, contract_with_operator, w3, operator, origin_rollup, target_rollup, payload
    ):
        """Test complete lifecycle: EMPTY -> BUFFERED -> READY -> EXECUTED"""
        tx_id = generate_unique_tx_id(1)

        # Initial state is EMPTY (0)
        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 0  # EMPTY

        # Buffer transaction
        current_ts = w3.eth.get_block('latest').timestamp + 1
        contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, current_ts
        ).transact({'from': operator})

        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 1  # BUFFERED

        # Resolve dependency
        contract_with_operator.functions.resolve_dependency(tx_id).transact({'from': operator})

        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 2  # READY

        # Mark as executed
        contract_with_operator.functions.mark_transaction_executed(tx_id).transact({'from': operator})

        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 3  # EXECUTED

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_full_lifecycle_with_dependency(
        self, contract_with_operator, w3, operator, origin_rollup, target_rollup, payload
    ):
        """Test lifecycle with dependency resolution"""
        tx_id_a = generate_unique_tx_id(10)
        tx_id_b = generate_unique_tx_id(11)

        current_ts = w3.eth.get_block('latest').timestamp + 1

        # Buffer transaction A (no dependency)
        contract_with_operator.functions.buffer_transaction(
            tx_id_a, origin_rollup, target_rollup, payload, b'\x00' * 32, current_ts
        ).transact({'from': operator})

        # Buffer transaction B (depends on A)
        contract_with_operator.functions.buffer_transaction(
            tx_id_b, origin_rollup, target_rollup, payload, tx_id_a, current_ts + 1
        ).transact({'from': operator})

        # B should not be resolvable yet (dependency not ready)
        # Resolve A first
        contract_with_operator.functions.resolve_dependency(tx_id_a).transact({'from': operator})
        state_a = contract_with_operator.functions.get_transaction_state(tx_id_a).call()
        assert state_a == 2  # READY

        # Now B can be resolved
        contract_with_operator.functions.resolve_dependency(tx_id_b).transact({'from': operator})
        state_b = contract_with_operator.functions.get_transaction_state(tx_id_b).call()
        assert state_b == 2  # READY


@pytest.mark.integration
class TestMultipleOperators:
    """Test scenarios with multiple operators"""

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_different_operators_can_buffer_and_resolve(
        self, contract, w3, owner, operator, resolver, origin_rollup, target_rollup, payload, buffer_role, resolve_role
    ):
        """Different operators can buffer and resolve transactions"""
        # Grant roles to different accounts
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        contract.functions.grant_role(resolve_role, resolver).transact({'from': owner})

        tx_id = generate_unique_tx_id(20)
        current_ts = w3.eth.get_block('latest').timestamp + 1

        # Operator buffers
        contract.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, current_ts
        ).transact({'from': operator})

        state = contract.functions.get_transaction_state(tx_id).call()
        assert state == 1  # BUFFERED

        # Resolver resolves
        contract.functions.resolve_dependency(tx_id).transact({'from': resolver})

        state = contract.functions.get_transaction_state(tx_id).call()
        assert state == 2  # READY


@pytest.mark.integration
class TestEmergencyScenarios:
    """Test emergency pause scenarios"""

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_pause_during_transaction_processing(
        self, contract_with_operator, w3, owner, operator, origin_rollup, target_rollup, payload
    ):
        """Pause should prevent further operations on buffered transaction"""
        tx_id = generate_unique_tx_id(30)
        current_ts = w3.eth.get_block('latest').timestamp + 1

        # Buffer transaction
        contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, current_ts
        ).transact({'from': operator})

        # Pause contract
        contract_with_operator.functions.emergency_pause().transact({'from': owner})

        # Resolution should fail
        with pytest.raises(TransactionFailed):
            contract_with_operator.functions.resolve_dependency(tx_id).transact({'from': operator})

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_resume_after_unpause(
        self, contract_with_operator, w3, owner, operator, origin_rollup, target_rollup, payload
    ):
        """Should be able to continue after unpause"""
        tx_id = generate_unique_tx_id(31)
        current_ts = w3.eth.get_block('latest').timestamp + 1

        # Buffer transaction
        contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, current_ts
        ).transact({'from': operator})

        # Pause and unpause
        contract_with_operator.functions.emergency_pause().transact({'from': owner})
        contract_with_operator.functions.emergency_unpause().transact({'from': owner})

        # Should be able to resolve now
        contract_with_operator.functions.resolve_dependency(tx_id).transact({'from': operator})

        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 2  # READY


@pytest.mark.integration
class TestRoleManagement:
    """Test role management scenarios"""

    def test_add_and_remove_operator(self, contract, owner, operator, buffer_role, resolve_role):
        """Test adding and removing operator roles"""
        # Grant both roles
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        contract.functions.grant_role(resolve_role, operator).transact({'from': owner})

        assert contract.functions.has_role(buffer_role, operator).call() is True
        assert contract.functions.has_role(resolve_role, operator).call() is True

        # Revoke buffer role
        contract.functions.revoke_role(buffer_role, operator).transact({'from': owner})

        assert contract.functions.has_role(buffer_role, operator).call() is False
        assert contract.functions.has_role(resolve_role, operator).call() is True

        # Revoke resolve role
        contract.functions.revoke_role(resolve_role, operator).transact({'from': owner})

        assert contract.functions.has_role(buffer_role, operator).call() is False
        assert contract.functions.has_role(resolve_role, operator).call() is False

    def test_transfer_ownership_maintains_roles(
        self, contract, owner, operator, unauthorized_user, buffer_role
    ):
        """Ownership transfer should not affect existing role grants"""
        # Grant role
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})

        # Transfer ownership
        contract.functions.transfer_ownership(unauthorized_user).transact({'from': owner})

        # Role should still be active
        assert contract.functions.has_role(buffer_role, operator).call() is True

        # New owner can revoke
        contract.functions.revoke_role(buffer_role, operator).transact({'from': unauthorized_user})
        assert contract.functions.has_role(buffer_role, operator).call() is False


@pytest.mark.integration
class TestGasEstimation:
    """Test gas usage for various operations"""

    def test_grant_role_gas(self, contract, w3, owner, operator, buffer_role):
        """Grant role should use reasonable gas"""
        tx_hash = contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Grant role should use less than 100k gas
        assert receipt.gasUsed < 100000

    def test_revoke_role_gas(self, contract, w3, owner, operator, buffer_role):
        """Revoke role should use reasonable gas"""
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        tx_hash = contract.functions.revoke_role(buffer_role, operator).transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Revoke role should use less than 50k gas
        assert receipt.gasUsed < 50000

    def test_emergency_pause_gas(self, contract, w3, owner):
        """Emergency pause should use reasonable gas"""
        tx_hash = contract.functions.emergency_pause().transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Emergency pause should use less than 50k gas
        assert receipt.gasUsed < 50000

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_buffer_transaction_gas(
        self, contract_with_operator, w3, operator, origin_rollup, target_rollup, payload
    ):
        """Buffer transaction should use reasonable gas"""
        tx_id = generate_unique_tx_id(40)
        future_ts = w3.eth.get_block('latest').timestamp + 1000

        tx_hash = contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, future_ts
        ).transact({'from': operator})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Buffer transaction should use less than 200k gas
        assert receipt.gasUsed < 200000
