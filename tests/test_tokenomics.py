"""
Test suite for Tesseract tokenomics contracts.

Tests:
- TESS token functionality
- Staking and fee distribution
- Fee collector
- Relayer registry
- Governance
"""

import pytest
from eth_tester import EthereumTester
from web3 import Web3
import vyper


# Constants for testing
TOTAL_SUPPLY = 1_000_000_000 * 10**18
COMMUNITY_ALLOCATION = 500_000_000 * 10**18
INVESTOR_ALLOCATION = 200_000_000 * 10**18
TEAM_ALLOCATION = 150_000_000 * 10**18
TREASURY_ALLOCATION = 150_000_000 * 10**18


@pytest.fixture
def w3():
    """Create Web3 instance with EthereumTester."""
    tester = EthereumTester()
    return Web3(Web3.EthereumTesterProvider(tester))


@pytest.fixture
def accounts(w3):
    """Get test accounts."""
    return w3.eth.accounts


@pytest.fixture
def deployer(accounts):
    """Deployer account."""
    return accounts[0]


@pytest.fixture
def community_wallet(accounts):
    """Community wallet."""
    return accounts[1]


@pytest.fixture
def treasury_wallet(accounts):
    """Treasury wallet."""
    return accounts[2]


@pytest.fixture
def user1(accounts):
    """Test user 1."""
    return accounts[3]


@pytest.fixture
def user2(accounts):
    """Test user 2."""
    return accounts[4]


def compile_contract(contract_path):
    """Compile a Vyper contract."""
    with open(contract_path) as f:
        source = f.read()
    return vyper.compile_code(source, output_formats=["abi", "bytecode"])


def deploy_contract(w3, compiled, deployer, *args):
    """Deploy a compiled contract."""
    contract = w3.eth.contract(
        abi=compiled["abi"],
        bytecode=compiled["bytecode"]
    )
    tx_hash = contract.constructor(*args).transact({"from": deployer})
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return w3.eth.contract(
        address=tx_receipt.contractAddress,
        abi=compiled["abi"]
    )


class TestTesseractToken:
    """Tests for TesseractToken contract."""

    @pytest.fixture
    def token_compiled(self):
        """Compile TESS token contract."""
        return compile_contract("contracts/TesseractToken.vy")

    @pytest.fixture
    def token(self, w3, token_compiled, deployer, community_wallet, treasury_wallet):
        """Deploy TESS token."""
        return deploy_contract(
            w3, token_compiled, deployer,
            community_wallet, treasury_wallet
        )

    def test_initial_supply(self, token):
        """Test total supply equals 1 billion."""
        assert token.functions.totalSupply().call() == TOTAL_SUPPLY

    def test_community_allocation(self, token, community_wallet):
        """Test community wallet receives 50%."""
        balance = token.functions.balanceOf(community_wallet).call()
        assert balance == COMMUNITY_ALLOCATION

    def test_treasury_allocation(self, token, treasury_wallet):
        """Test treasury receives 15%."""
        balance = token.functions.balanceOf(treasury_wallet).call()
        assert balance == TREASURY_ALLOCATION

    def test_vesting_pool(self, token):
        """Test remaining tokens held by contract for vesting."""
        contract_balance = token.functions.balanceOf(token.address).call()
        expected = INVESTOR_ALLOCATION + TEAM_ALLOCATION
        assert contract_balance == expected

    def test_transfer(self, token, community_wallet, user1, w3):
        """Test basic transfer."""
        amount = 1000 * 10**18
        token.functions.transfer(user1, amount).transact({"from": community_wallet})
        assert token.functions.balanceOf(user1).call() == amount

    def test_approve_and_transfer_from(self, token, community_wallet, user1, user2, w3):
        """Test approve and transferFrom."""
        amount = 1000 * 10**18
        token.functions.approve(user1, amount).transact({"from": community_wallet})
        token.functions.transferFrom(community_wallet, user2, amount).transact({"from": user1})
        assert token.functions.balanceOf(user2).call() == amount

    def test_vesting_schedule_creation(self, token, deployer, user1, w3):
        """Test creating vesting schedule."""
        amount = 1_000_000 * 10**18
        cliff = 365 * 86400  # 1 year
        vest = 730 * 86400   # 2 years

        token.functions.create_vesting_schedule(
            user1, amount, cliff, vest, True
        ).transact({"from": deployer})

        schedule = token.functions.vesting_schedules(user1).call()
        assert schedule[0] == amount  # total_amount

    def test_cannot_claim_before_cliff(self, token, deployer, user1, w3):
        """Test cannot claim vested tokens before cliff."""
        amount = 1_000_000 * 10**18
        cliff = 365 * 86400
        vest = 730 * 86400

        token.functions.create_vesting_schedule(
            user1, amount, cliff, vest, True
        ).transact({"from": deployer})

        with pytest.raises(Exception):
            token.functions.claim_vested_tokens().transact({"from": user1})


class TestTesseractStaking:
    """Tests for TesseractStaking contract."""

    @pytest.fixture
    def token_compiled(self):
        return compile_contract("contracts/TesseractToken.vy")

    @pytest.fixture
    def staking_compiled(self):
        return compile_contract("contracts/TesseractStaking.vy")

    @pytest.fixture
    def token(self, w3, token_compiled, deployer, community_wallet, treasury_wallet):
        return deploy_contract(
            w3, token_compiled, deployer,
            community_wallet, treasury_wallet
        )

    @pytest.fixture
    def staking(self, w3, staking_compiled, deployer, token):
        return deploy_contract(w3, staking_compiled, deployer, token.address)

    def test_stake(self, token, staking, community_wallet, user1, w3):
        """Test staking tokens."""
        stake_amount = 50_000 * 10**18

        # Transfer tokens to user
        token.functions.transfer(user1, stake_amount).transact({"from": community_wallet})

        # Approve staking
        token.functions.approve(staking.address, stake_amount).transact({"from": user1})

        # Stake
        staking.functions.stake(stake_amount).transact({"from": user1})

        # Check stake
        info = staking.functions.get_stake_info(user1).call()
        assert info[0] > 0  # shares
        assert info[1] == stake_amount  # staked amount

    def test_unstake_cooldown(self, token, staking, community_wallet, user1, w3):
        """Test unstaking requires cooldown."""
        stake_amount = 50_000 * 10**18

        # Setup stake
        token.functions.transfer(user1, stake_amount).transact({"from": community_wallet})
        token.functions.approve(staking.address, stake_amount).transact({"from": user1})
        staking.functions.stake(stake_amount).transact({"from": user1})

        shares = staking.functions.get_stake_info(user1).call()[0]

        # Request unstake
        staking.functions.request_unstake(shares).transact({"from": user1})

        # Cannot unstake immediately
        with pytest.raises(Exception):
            staking.functions.unstake().transact({"from": user1})


class TestFeeCollector:
    """Tests for FeeCollector contract."""

    @pytest.fixture
    def fee_collector_compiled(self):
        return compile_contract("contracts/FeeCollector.vy")

    @pytest.fixture
    def fee_collector(self, w3, fee_collector_compiled, deployer, treasury_wallet):
        # Deploy with placeholder addresses
        return deploy_contract(
            w3, fee_collector_compiled, deployer,
            deployer,  # staking (placeholder)
            deployer,  # relayer registry (placeholder)
            treasury_wallet
        )

    def test_fee_rates(self, fee_collector):
        """Test default fee rates."""
        rates = fee_collector.functions.get_fee_rates().call()
        assert rates[0] == 6000  # staker 60%
        assert rates[1] == 3000  # relayer 30%
        assert rates[2] == 1000  # treasury 10%

    def test_update_fee_rates(self, fee_collector, deployer):
        """Test updating fee rates."""
        fee_collector.functions.set_fee_rates(5500, 3500, 1000).transact({"from": deployer})
        rates = fee_collector.functions.get_fee_rates().call()
        assert rates[0] == 5500
        assert rates[1] == 3500


class TestRelayerRegistry:
    """Tests for RelayerRegistry contract."""

    @pytest.fixture
    def token_compiled(self):
        return compile_contract("contracts/TesseractToken.vy")

    @pytest.fixture
    def registry_compiled(self):
        return compile_contract("contracts/RelayerRegistry.vy")

    @pytest.fixture
    def token(self, w3, token_compiled, deployer, community_wallet, treasury_wallet):
        return deploy_contract(
            w3, token_compiled, deployer,
            community_wallet, treasury_wallet
        )

    @pytest.fixture
    def registry(self, w3, registry_compiled, deployer, token):
        return deploy_contract(w3, registry_compiled, deployer, token.address)

    def test_register_relayer(self, token, registry, community_wallet, user1, w3):
        """Test relayer registration."""
        stake_amount = 50_000 * 10**18
        chains = [1, 137, 42161]  # ETH, Polygon, Arbitrum

        # Transfer and approve
        token.functions.transfer(user1, stake_amount).transact({"from": community_wallet})
        token.functions.approve(registry.address, stake_amount).transact({"from": user1})

        # Register
        registry.functions.register(stake_amount, chains).transact({"from": user1})

        # Check registration
        info = registry.functions.get_relayer_info(user1).call()
        assert info[0] == stake_amount  # stake_amount
        assert info[7] == True  # is_active

    def test_minimum_stake_required(self, token, registry, community_wallet, user1, w3):
        """Test minimum stake requirement."""
        low_stake = 10_000 * 10**18  # Below 50k minimum
        chains = [1]

        token.functions.transfer(user1, low_stake).transact({"from": community_wallet})
        token.functions.approve(registry.address, low_stake).transact({"from": user1})

        with pytest.raises(Exception):
            registry.functions.register(low_stake, chains).transact({"from": user1})

    def test_heartbeat(self, token, registry, community_wallet, user1, w3):
        """Test relayer heartbeat."""
        stake_amount = 50_000 * 10**18

        token.functions.transfer(user1, stake_amount).transact({"from": community_wallet})
        token.functions.approve(registry.address, stake_amount).transact({"from": user1})
        registry.functions.register(stake_amount, [1]).transact({"from": user1})

        # Send heartbeat
        registry.functions.heartbeat().transact({"from": user1})

        # Should be eligible
        assert registry.functions.is_eligible(user1).call() == True


class TestGovernance:
    """Tests for TesseractGovernor contract."""

    @pytest.fixture
    def token_compiled(self):
        return compile_contract("contracts/TesseractToken.vy")

    @pytest.fixture
    def governor_compiled(self):
        return compile_contract("contracts/TesseractGovernor.vy")

    @pytest.fixture
    def token(self, w3, token_compiled, deployer, community_wallet, treasury_wallet):
        return deploy_contract(
            w3, token_compiled, deployer,
            community_wallet, treasury_wallet
        )

    @pytest.fixture
    def governor(self, w3, governor_compiled, deployer, token):
        return deploy_contract(w3, governor_compiled, deployer, token.address)

    def test_proposal_threshold(self, governor):
        """Test proposal threshold is 100k TESS."""
        threshold = governor.functions.proposal_threshold().call()
        assert threshold == 100_000 * 10**18

    def test_quorum(self, governor):
        """Test quorum is 4%."""
        quorum_bps = governor.functions.quorum_bps().call()
        assert quorum_bps == 400


class TestAtomicSwapFees:
    """Tests for fee integration in AtomicSwapCoordinator."""

    @pytest.fixture
    def coordinator_compiled(self):
        return compile_contract("contracts/AtomicSwapCoordinator.vy")

    @pytest.fixture
    def coordinator(self, w3, coordinator_compiled, deployer):
        return deploy_contract(w3, coordinator_compiled, deployer)

    def test_default_protocol_fee(self, coordinator):
        """Test default protocol fee is 0.2%."""
        fee_bps = coordinator.functions.protocol_fee_bps().call()
        assert fee_bps == 20  # 0.2%

    def test_fee_calculation_preview(self, coordinator, user1):
        """Test fee calculation."""
        amount = 10_000 * 10**18  # 10k tokens
        fee, has_discount = coordinator.functions.calculate_fee_preview(amount, user1).call()

        # 0.2% of 10,000 = 20
        assert fee == 20 * 10**18
        assert has_discount == False

    def test_set_protocol_fee(self, coordinator, deployer):
        """Test setting protocol fee."""
        coordinator.functions.set_protocol_fee(25).transact({"from": deployer})
        assert coordinator.functions.protocol_fee_bps().call() == 25

    def test_fee_bounds(self, coordinator, deployer):
        """Test fee cannot exceed bounds."""
        # Cannot set below 0.1% (10 bps)
        with pytest.raises(Exception):
            coordinator.functions.set_protocol_fee(5).transact({"from": deployer})

        # Cannot set above 0.3% (30 bps)
        with pytest.raises(Exception):
            coordinator.functions.set_protocol_fee(50).transact({"from": deployer})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
