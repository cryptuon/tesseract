"""
Unit tests for access control in TesseractBuffer.vy

Tests owner-only functions, role-based access, and permission management.
"""

import pytest
from web3 import Web3
from eth_tester.exceptions import TransactionFailed

# Role constants
BUFFER_ROLE = Web3.keccak(text="BUFFER_ROLE")
RESOLVE_ROLE = Web3.keccak(text="RESOLVE_ROLE")
ADMIN_ROLE = Web3.keccak(text="ADMIN_ROLE")


@pytest.mark.unit
class TestOwnerFunctions:
    """Test owner-only functions"""

    def test_owner_is_set_on_deploy(self, contract, owner):
        """Owner should be set to deployer on deployment"""
        assert contract.functions.owner().call() == owner

    def test_owner_can_grant_role(self, contract, owner, operator, buffer_role):
        """Owner should be able to grant roles"""
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        assert contract.functions.has_role(buffer_role, operator).call() is True

    def test_owner_can_revoke_role(self, contract, owner, operator, buffer_role):
        """Owner should be able to revoke roles"""
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        contract.functions.revoke_role(buffer_role, operator).transact({'from': owner})
        assert contract.functions.has_role(buffer_role, operator).call() is False

    def test_non_owner_cannot_grant_role(self, contract, operator, unauthorized_user, buffer_role):
        """Non-owner should not be able to grant roles"""
        with pytest.raises(TransactionFailed):
            contract.functions.grant_role(buffer_role, operator).transact({'from': unauthorized_user})

    def test_non_owner_cannot_revoke_role(self, contract, owner, operator, unauthorized_user, buffer_role):
        """Non-owner should not be able to revoke roles"""
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        with pytest.raises(TransactionFailed):
            contract.functions.revoke_role(buffer_role, operator).transact({'from': unauthorized_user})

    def test_owner_can_transfer_ownership(self, contract, owner, operator):
        """Owner should be able to transfer ownership"""
        contract.functions.transfer_ownership(operator).transact({'from': owner})
        assert contract.functions.owner().call() == operator

    def test_non_owner_cannot_transfer_ownership(self, contract, owner, unauthorized_user, operator):
        """Non-owner should not be able to transfer ownership"""
        with pytest.raises(TransactionFailed):
            contract.functions.transfer_ownership(operator).transact({'from': unauthorized_user})

    def test_cannot_transfer_ownership_to_zero_address(self, contract, owner):
        """Should not allow transferring ownership to zero address"""
        zero_address = "0x" + "0" * 40
        with pytest.raises(TransactionFailed):
            contract.functions.transfer_ownership(zero_address).transact({'from': owner})

    def test_owner_can_set_coordination_window(self, contract, owner):
        """Owner should be able to set coordination window"""
        contract.functions.set_coordination_window(60).transact({'from': owner})
        assert contract.functions.coordination_window().call() == 60

    def test_non_owner_cannot_set_coordination_window(self, contract, unauthorized_user):
        """Non-owner should not be able to set coordination window"""
        with pytest.raises(TransactionFailed):
            contract.functions.set_coordination_window(60).transact({'from': unauthorized_user})

    def test_owner_can_set_max_payload_size(self, contract, owner):
        """Owner should be able to set max payload size"""
        contract.functions.set_max_payload_size(1024).transact({'from': owner})
        assert contract.functions.max_payload_size().call() == 1024

    def test_owner_can_set_circuit_breaker_threshold(self, contract, owner):
        """Owner should be able to set circuit breaker threshold"""
        contract.functions.set_circuit_breaker_threshold(100).transact({'from': owner})
        assert contract.functions.circuit_breaker_threshold().call() == 100

    def test_owner_can_set_emergency_admin(self, contract, owner, emergency_admin):
        """Owner should be able to set emergency admin"""
        contract.functions.set_emergency_admin(emergency_admin).transact({'from': owner})
        assert contract.functions.emergency_admin().call() == emergency_admin


@pytest.mark.unit
class TestRoleBasedAccess:
    """Test role-based access control"""

    def test_deployer_has_admin_role(self, contract, owner, admin_role):
        """Deployer should have ADMIN_ROLE by default"""
        assert contract.functions.has_role(admin_role, owner).call() is True

    def test_deployer_does_not_have_buffer_role_by_default(self, contract, owner, buffer_role):
        """Deployer should NOT have BUFFER_ROLE by default"""
        assert contract.functions.has_role(buffer_role, owner).call() is False

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_account_without_buffer_role_cannot_buffer(
        self, contract, w3, owner, unauthorized_user, tx_id, origin_rollup, target_rollup, payload
    ):
        """Account without BUFFER_ROLE should not be able to buffer transactions"""
        future_ts = w3.eth.get_block('latest').timestamp + 100
        with pytest.raises(TransactionFailed):
            contract.functions.buffer_transaction(
                tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, future_ts
            ).transact({'from': unauthorized_user})

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_account_with_buffer_role_can_buffer(
        self, contract, w3, owner, operator, tx_id, origin_rollup, target_rollup, payload, buffer_role
    ):
        """Account with BUFFER_ROLE should be able to buffer transactions"""
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        # Get timestamp AFTER role grant (which mines a block)
        future_ts = w3.eth.get_block('latest').timestamp + 1000
        contract.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, future_ts
        ).transact({'from': operator})

        state = contract.functions.get_transaction_state(tx_id).call()
        assert state == 1  # BUFFERED

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_account_without_resolve_role_cannot_resolve(
        self, contract_with_operator, w3, operator, tx_id, origin_rollup, target_rollup, payload, unauthorized_user
    ):
        """Account without RESOLVE_ROLE should not be able to resolve dependencies"""
        # Get fresh timestamp
        future_ts = w3.eth.get_block('latest').timestamp + 1000
        contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, future_ts
        ).transact({'from': operator})

        # Try to resolve without role
        with pytest.raises(TransactionFailed):
            contract_with_operator.functions.resolve_dependency(tx_id).transact({'from': unauthorized_user})

    @pytest.mark.xfail(reason="py-evm 0.10.x has a bug with Vyper enum comparisons - works on real networks")
    def test_account_with_resolve_role_can_resolve(
        self, contract_with_operator, w3, operator, tx_id, origin_rollup, target_rollup, payload
    ):
        """Account with RESOLVE_ROLE should be able to resolve dependencies"""
        # Get fresh timestamp (immediately resolvable)
        current_ts = w3.eth.get_block('latest').timestamp + 1
        contract_with_operator.functions.buffer_transaction(
            tx_id, origin_rollup, target_rollup, payload, b'\x00' * 32, current_ts
        ).transact({'from': operator})

        # Resolve
        contract_with_operator.functions.resolve_dependency(tx_id).transact({'from': operator})

        state = contract_with_operator.functions.get_transaction_state(tx_id).call()
        assert state == 2  # READY


@pytest.mark.unit
class TestEmergencyAdmin:
    """Test emergency admin permissions"""

    def test_emergency_admin_is_owner_by_default(self, contract, owner):
        """Emergency admin should be owner by default"""
        assert contract.functions.emergency_admin().call() == owner

    def test_owner_can_pause(self, contract, owner):
        """Owner should be able to pause contract"""
        contract.functions.emergency_pause().transact({'from': owner})
        assert contract.functions.paused().call() is True

    def test_emergency_admin_can_pause(self, contract, owner, emergency_admin):
        """Emergency admin should be able to pause contract"""
        contract.functions.set_emergency_admin(emergency_admin).transact({'from': owner})
        contract.functions.emergency_pause().transact({'from': emergency_admin})
        assert contract.functions.paused().call() is True

    def test_non_admin_cannot_pause(self, contract, unauthorized_user):
        """Non-admin should not be able to pause contract"""
        with pytest.raises(TransactionFailed):
            contract.functions.emergency_pause().transact({'from': unauthorized_user})

    def test_only_owner_can_unpause(self, contract, owner, emergency_admin):
        """Only owner (not emergency admin) should be able to unpause"""
        contract.functions.set_emergency_admin(emergency_admin).transact({'from': owner})
        contract.functions.emergency_pause().transact({'from': emergency_admin})

        # Emergency admin cannot unpause
        with pytest.raises(TransactionFailed):
            contract.functions.emergency_unpause().transact({'from': emergency_admin})

        # Owner can unpause
        contract.functions.emergency_unpause().transact({'from': owner})
        assert contract.functions.paused().call() is False


@pytest.mark.unit
class TestRoleEvents:
    """Test role-related events"""

    def test_role_granted_event(self, contract, w3, owner, operator, buffer_role):
        """RoleGranted event should be emitted when granting role"""
        tx_hash = contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Check event was emitted
        events = contract.events.RoleGranted().process_receipt(receipt)
        assert len(events) == 1
        assert events[0]['args']['role'] == buffer_role
        assert events[0]['args']['account'] == operator
        assert events[0]['args']['sender'] == owner

    def test_role_revoked_event(self, contract, w3, owner, operator, buffer_role):
        """RoleRevoked event should be emitted when revoking role"""
        contract.functions.grant_role(buffer_role, operator).transact({'from': owner})
        tx_hash = contract.functions.revoke_role(buffer_role, operator).transact({'from': owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Check event was emitted
        events = contract.events.RoleRevoked().process_receipt(receipt)
        assert len(events) == 1
        assert events[0]['args']['role'] == buffer_role
        assert events[0]['args']['account'] == operator
        assert events[0]['args']['sender'] == owner
