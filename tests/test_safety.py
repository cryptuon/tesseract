"""
Unit tests for safety mechanisms in TesseractBuffer.vy

Tests emergency pause, circuit breaker, and rate limiting.
"""

import pytest
from web3 import Web3
from eth_tester.exceptions import TransactionFailed


@pytest.mark.unit
class TestEmergencyPause:
    """Test emergency pause functionality"""

    def test_contract_not_paused_by_default(self, contract):
        """Contract should not be paused initially"""
        assert contract.functions.paused().call() is False

    def test_owner_can_pause(self, contract, owner):
        """Owner should be able to pause contract"""
        contract.functions.emergency_pause().transact({'from': owner})
        assert contract.functions.paused().call() is True

    def test_owner_can_unpause(self, contract, owner):
        """Owner should be able to unpause contract"""
        contract.functions.emergency_pause().transact({'from': owner})
        contract.functions.emergency_unpause().transact({'from': owner})
        assert contract.functions.paused().call() is False

    def test_pause_emits_event(self, contract, w3, owner):
        """EmergencyPause event should be emitted"""
        tx_hash = contract.functions.emergency_pause().transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        events = contract.events.EmergencyPause().process_receipt(receipt)
        assert len(events) == 1
        assert events[0]['args']['caller'] == owner

    def test_unpause_emits_event(self, contract, w3, owner):
        """EmergencyUnpause event should be emitted"""
        contract.functions.emergency_pause().transact({'from': owner})
        tx_hash = contract.functions.emergency_unpause().transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        events = contract.events.EmergencyUnpause().process_receipt(receipt)
        assert len(events) == 1
        assert events[0]['args']['caller'] == owner

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_cannot_buffer_when_paused(
        self, contract_with_operator, w3, owner, operator, tx_id, origin_rollup, target_rollup, payload
    ):
        """Cannot buffer transactions when contract is paused"""
        contract_with_operator.functions.emergency_pause().transact({'from': owner})
        future_ts = w3.eth.get_block('latest').timestamp + 1000

        with pytest.raises(TransactionFailed):
            contract_with_operator.functions.buffer_transaction(
                tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, future_ts
            ).transact({'from': operator})

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_can_buffer_after_unpause(
        self, contract_with_operator, w3, owner, operator, tx_id, origin_rollup, target_rollup, payload
    ):
        """Can buffer transactions after unpause"""
        contract_with_operator.functions.emergency_pause().transact({'from': owner})
        contract_with_operator.functions.emergency_unpause().transact({'from': owner})

        future_ts = w3.eth.get_block('latest').timestamp + 1000
        contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, future_ts
        ).transact({'from': operator})

        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 1  # BUFFERED


@pytest.mark.unit
class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def test_circuit_breaker_not_active_by_default(self, contract):
        """Circuit breaker should not be active initially"""
        assert contract.functions.circuit_breaker_active().call() is False

    def test_default_circuit_breaker_threshold(self, contract):
        """Default circuit breaker threshold should be 50"""
        assert contract.functions.circuit_breaker_threshold().call() == 50

    def test_owner_can_set_threshold(self, contract, owner):
        """Owner should be able to set circuit breaker threshold"""
        contract.functions.set_circuit_breaker_threshold(100).transact({'from': owner})
        assert contract.functions.circuit_breaker_threshold().call() == 100

    def test_non_owner_cannot_set_threshold(self, contract, unauthorized_user):
        """Non-owner should not be able to set circuit breaker threshold"""
        with pytest.raises(TransactionFailed):
            contract.functions.set_circuit_breaker_threshold(100).transact({'from': unauthorized_user})

    def test_owner_can_reset_circuit_breaker_after_cooldown(self, contract, w3, owner):
        """Owner should be able to reset circuit breaker after cooldown"""
        # Circuit breaker reset has a cooldown period (1 hour by default)
        # We need to advance time past the cooldown
        current_time = w3.eth.get_block('latest').timestamp
        # Advance time by 1 hour + 1 second
        w3.testing.timeTravel(current_time + 3601)
        w3.testing.mine()

        contract.functions.reset_circuit_breaker().transact({'from': owner})
        assert contract.functions.circuit_breaker_active().call() is False

    def test_non_owner_cannot_reset_circuit_breaker(self, contract, unauthorized_user):
        """Non-owner should not be able to reset circuit breaker"""
        with pytest.raises(TransactionFailed):
            contract.functions.reset_circuit_breaker().transact({'from': unauthorized_user})


@pytest.mark.unit
class TestEmergencyAdmin:
    """Test emergency admin functionality"""

    def test_emergency_admin_is_owner_by_default(self, contract, owner):
        """Emergency admin should be owner by default"""
        assert contract.functions.emergency_admin().call() == owner

    def test_owner_can_set_emergency_admin(self, contract, owner, emergency_admin):
        """Owner should be able to set emergency admin"""
        contract.functions.set_emergency_admin(emergency_admin).transact({'from': owner})
        assert contract.functions.emergency_admin().call() == emergency_admin

    def test_emergency_admin_can_pause(self, contract, owner, emergency_admin):
        """Emergency admin should be able to pause contract"""
        contract.functions.set_emergency_admin(emergency_admin).transact({'from': owner})
        contract.functions.emergency_pause().transact({'from': emergency_admin})
        assert contract.functions.paused().call() is True

    def test_emergency_admin_cannot_unpause(self, contract, owner, emergency_admin):
        """Emergency admin should NOT be able to unpause (only owner can)"""
        contract.functions.set_emergency_admin(emergency_admin).transact({'from': owner})
        contract.functions.emergency_pause().transact({'from': emergency_admin})

        with pytest.raises(TransactionFailed):
            contract.functions.emergency_unpause().transact({'from': emergency_admin})

    def test_non_owner_cannot_set_emergency_admin(self, contract, unauthorized_user, emergency_admin):
        """Non-owner should not be able to set emergency admin"""
        with pytest.raises(TransactionFailed):
            contract.functions.set_emergency_admin(emergency_admin).transact({'from': unauthorized_user})

    def test_cannot_set_zero_address_as_emergency_admin(self, contract, owner):
        """Cannot set zero address as emergency admin"""
        zero_address = "0x" + "0" * 40
        with pytest.raises(TransactionFailed):
            contract.functions.set_emergency_admin(zero_address).transact({'from': owner})


@pytest.mark.unit
class TestOwnershipTransfer:
    """Test ownership transfer functionality"""

    def test_owner_can_transfer_ownership(self, contract, owner, operator):
        """Owner should be able to transfer ownership"""
        contract.functions.transfer_ownership(operator).transact({'from': owner})
        assert contract.functions.owner().call() == operator

    def test_non_owner_cannot_transfer_ownership(self, contract, unauthorized_user, operator):
        """Non-owner should not be able to transfer ownership"""
        with pytest.raises(TransactionFailed):
            contract.functions.transfer_ownership(operator).transact({'from': unauthorized_user})

    def test_cannot_transfer_to_zero_address(self, contract, owner):
        """Cannot transfer ownership to zero address"""
        zero_address = "0x" + "0" * 40
        with pytest.raises(TransactionFailed):
            contract.functions.transfer_ownership(zero_address).transact({'from': owner})

    def test_new_owner_can_act_as_owner(self, contract, owner, operator, unauthorized_user, buffer_role):
        """New owner should be able to perform owner actions"""
        contract.functions.transfer_ownership(operator).transact({'from': owner})

        # New owner can grant roles
        contract.functions.grant_role(buffer_role, unauthorized_user).transact({'from': operator})
        assert contract.functions.has_role(buffer_role, unauthorized_user).call() is True

    def test_old_owner_cannot_act_after_transfer(self, contract, owner, operator, unauthorized_user, buffer_role):
        """Old owner should not be able to perform owner actions after transfer"""
        contract.functions.transfer_ownership(operator).transact({'from': owner})

        # Old owner cannot grant roles
        with pytest.raises(TransactionFailed):
            contract.functions.grant_role(buffer_role, unauthorized_user).transact({'from': owner})
