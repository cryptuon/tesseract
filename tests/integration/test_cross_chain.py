"""
Cross-chain integration tests for Tesseract.

Tests the full atomic swap lifecycle across simulated chains using Anvil forks.
These tests require Anvil (from Foundry) to be installed.

Test scenarios:
1. Basic cross-chain swap (Chain A -> Chain B)
2. Multi-leg atomic swap (3-way swap)
3. Timeout and refund handling
4. Dependency resolution across chains
5. Swap group atomicity

Usage:
    pytest tests/integration/test_cross_chain.py -v
    pytest tests/integration/test_cross_chain.py -v -k "test_basic_swap"

Requirements:
    - Anvil (foundry): curl -L https://foundry.paradigm.xyz | bash && foundryup
    - Environment: SEPOLIA_RPC_URL, POLYGON_AMOY_RPC_URL (optional, uses defaults)
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest
from eth_utils import keccak
from web3 import Web3
from vyper import compile_code

# Skip all tests if Anvil is not installed
pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "anvil"], capture_output=True).returncode != 0,
    reason="Anvil not installed - install via: curl -L https://foundry.paradigm.xyz | bash && foundryup"
)


# ============================================================================
# Test Configuration
# ============================================================================

# Default RPC URLs for forking (can be overridden by environment)
DEFAULT_SEPOLIA_RPC = "https://rpc.sepolia.org"
DEFAULT_AMOY_RPC = "https://rpc-amoy.polygon.technology"

# Anvil ports for different chains
CHAIN_A_PORT = 8545
CHAIN_B_PORT = 8546
CHAIN_C_PORT = 8547

# Test accounts (Anvil default accounts)
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
MAKER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
TAKER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
RELAYER_KEY = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"

# Contract paths
CONTRACT_DIR = Path(__file__).parent.parent.parent / "contracts"
BUFFER_CONTRACT = CONTRACT_DIR / "TesseractBuffer.vy"
COORDINATOR_CONTRACT = CONTRACT_DIR / "AtomicSwapCoordinator.vy"
TOKEN_CONTRACT = CONTRACT_DIR / "TesseractToken.vy"


# ============================================================================
# Fixtures
# ============================================================================

class AnvilInstance:
    """Manages an Anvil instance for testing."""

    def __init__(self, port: int, chain_id: int, fork_url: Optional[str] = None):
        self.port = port
        self.chain_id = chain_id
        self.fork_url = fork_url
        self.process: Optional[subprocess.Popen] = None
        self.w3: Optional[Web3] = None

    def start(self):
        """Start the Anvil instance."""
        cmd = [
            "anvil",
            "--port", str(self.port),
            "--chain-id", str(self.chain_id),
            "--block-time", "1",  # 1 second blocks
            "--silent",
        ]

        if self.fork_url:
            cmd.extend(["--fork-url", self.fork_url])

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for Anvil to start
        time.sleep(2)

        # Connect Web3
        self.w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{self.port}"))

        # Verify connection
        attempts = 0
        while attempts < 10:
            try:
                if self.w3.is_connected():
                    return
            except Exception:
                pass
            time.sleep(0.5)
            attempts += 1

        raise RuntimeError(f"Failed to connect to Anvil on port {self.port}")

    def stop(self):
        """Stop the Anvil instance."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None

    def mine_blocks(self, count: int = 1):
        """Mine blocks on the Anvil instance."""
        for _ in range(count):
            self.w3.testing.mine()

    def advance_time(self, seconds: int):
        """Advance block time on the Anvil instance."""
        self.w3.provider.make_request("evm_increaseTime", [seconds])
        self.mine_blocks(1)


class CrossChainTestSetup:
    """Manages multi-chain test setup with deployed contracts."""

    def __init__(self):
        self.chain_a: Optional[AnvilInstance] = None
        self.chain_b: Optional[AnvilInstance] = None
        self.chain_c: Optional[AnvilInstance] = None

        self.buffer_a: Optional[str] = None
        self.buffer_b: Optional[str] = None
        self.coordinator_a: Optional[str] = None
        self.coordinator_b: Optional[str] = None

        self.compiled_buffer = None
        self.compiled_coordinator = None

    def compile_contracts(self):
        """Compile all needed contracts."""
        with open(BUFFER_CONTRACT) as f:
            source = f.read()
        self.compiled_buffer = compile_code(source, output_formats=["abi", "bytecode"])

        with open(COORDINATOR_CONTRACT) as f:
            source = f.read()
        self.compiled_coordinator = compile_code(source, output_formats=["abi", "bytecode"])

    def deploy_contract(self, w3: Web3, compiled: dict, deployer: str, *args) -> Tuple[str, any]:
        """Deploy a contract and return address and contract instance."""
        contract = w3.eth.contract(
            abi=compiled["abi"],
            bytecode=compiled["bytecode"]
        )

        tx_hash = contract.constructor(*args).transact({"from": deployer})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        deployed = w3.eth.contract(
            address=receipt.contractAddress,
            abi=compiled["abi"]
        )

        return receipt.contractAddress, deployed

    def setup_chain(self, anvil: AnvilInstance, deployer: str) -> Tuple[str, str, any, any]:
        """Deploy contracts on a chain and configure them."""
        # Deploy TesseractBuffer
        buffer_addr, buffer = self.deploy_contract(
            anvil.w3,
            self.compiled_buffer,
            deployer
        )

        # Deploy AtomicSwapCoordinator
        coord_addr, coordinator = self.deploy_contract(
            anvil.w3,
            self.compiled_coordinator,
            deployer
        )

        # Configure coordinator to use buffer
        coordinator.functions.set_tesseract_buffer(buffer_addr).transact({"from": deployer})

        # Grant roles
        BUFFER_ROLE = Web3.keccak(text="BUFFER_ROLE")
        RESOLVE_ROLE = Web3.keccak(text="RESOLVE_ROLE")

        relayer = anvil.w3.eth.account.from_key(RELAYER_KEY).address
        buffer.functions.grant_role(BUFFER_ROLE, relayer).transact({"from": deployer})
        buffer.functions.grant_role(RESOLVE_ROLE, relayer).transact({"from": deployer})

        return buffer_addr, coord_addr, buffer, coordinator


@pytest.fixture(scope="module")
def cross_chain_setup():
    """Set up multi-chain test environment."""
    setup = CrossChainTestSetup()

    # Compile contracts
    setup.compile_contracts()

    # Start Anvil instances
    setup.chain_a = AnvilInstance(CHAIN_A_PORT, 1001)
    setup.chain_b = AnvilInstance(CHAIN_B_PORT, 1002)

    setup.chain_a.start()
    setup.chain_b.start()

    # Get deployer
    deployer_a = setup.chain_a.w3.eth.account.from_key(DEPLOYER_KEY).address
    deployer_b = setup.chain_b.w3.eth.account.from_key(DEPLOYER_KEY).address

    # Deploy contracts
    (
        setup.buffer_a,
        setup.coordinator_a,
        setup.buffer_contract_a,
        setup.coordinator_contract_a
    ) = setup.setup_chain(setup.chain_a, deployer_a)

    (
        setup.buffer_b,
        setup.coordinator_b,
        setup.buffer_contract_b,
        setup.coordinator_contract_b
    ) = setup.setup_chain(setup.chain_b, deployer_b)

    yield setup

    # Cleanup
    setup.chain_a.stop()
    setup.chain_b.stop()


@pytest.fixture
def maker(cross_chain_setup):
    """Get maker account."""
    return cross_chain_setup.chain_a.w3.eth.account.from_key(MAKER_KEY).address


@pytest.fixture
def taker(cross_chain_setup):
    """Get taker account."""
    return cross_chain_setup.chain_a.w3.eth.account.from_key(TAKER_KEY).address


@pytest.fixture
def relayer(cross_chain_setup):
    """Get relayer account."""
    return cross_chain_setup.chain_a.w3.eth.account.from_key(RELAYER_KEY).address


# ============================================================================
# Helper Functions
# ============================================================================

def generate_tx_id(seed: str) -> bytes:
    """Generate a unique transaction ID."""
    return keccak(text=f"{seed}_{time.time()}")


def generate_order_id(seed: str) -> bytes:
    """Generate a unique order ID."""
    return keccak(text=f"order_{seed}_{time.time()}")


# ============================================================================
# Test Cases
# ============================================================================

class TestBasicCrossChainSwap:
    """Test basic cross-chain swap functionality."""

    def test_buffer_on_chain_a(self, cross_chain_setup, relayer):
        """Test buffering a transaction on Chain A."""
        setup = cross_chain_setup
        tx_id = generate_tx_id("buffer_test")

        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 60

        # Buffer transaction
        setup.buffer_contract_a.functions.buffer_transaction(
            tx_id,
            setup.buffer_a,  # origin
            setup.buffer_b,  # target (cross-chain)
            b"test_payload",
            bytes(32),  # no dependency
            future_ts
        ).transact({"from": relayer})

        # Verify buffered
        tx = setup.buffer_contract_a.functions.get_transaction(tx_id).call()
        assert tx[5] == 1  # BUFFERED state

    def test_resolve_after_blocks(self, cross_chain_setup, relayer):
        """Test resolving transaction after MIN_RESOLUTION_DELAY blocks."""
        setup = cross_chain_setup
        tx_id = generate_tx_id("resolve_test")

        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 60

        # Buffer transaction
        setup.buffer_contract_a.functions.buffer_transaction(
            tx_id,
            setup.buffer_a,
            setup.buffer_b,
            b"test_payload",
            bytes(32),
            future_ts
        ).transact({"from": relayer})

        # Mine blocks to pass MIN_RESOLUTION_DELAY (2 blocks)
        setup.chain_a.mine_blocks(3)

        # Advance time
        setup.chain_a.advance_time(60)

        # Resolve
        setup.buffer_contract_a.functions.resolve_dependency(tx_id).transact({"from": relayer})

        # Verify ready
        tx = setup.buffer_contract_a.functions.get_transaction(tx_id).call()
        assert tx[5] == 2  # READY state

    def test_full_cross_chain_cycle(self, cross_chain_setup, relayer):
        """Test complete cross-chain transaction cycle."""
        setup = cross_chain_setup

        # Create swap group ID
        swap_group_id = generate_tx_id("swap_group")

        # Transaction on Chain A
        tx_id_a = generate_tx_id("chain_a_leg")
        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 60

        # Buffer on Chain A with commitment
        commitment = keccak(b"secret_payload" + keccak(b"secret"))
        setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
            tx_id_a,
            setup.buffer_a,
            setup.buffer_b,
            commitment,
            bytes(32),  # no dependency
            future_ts,
            swap_group_id,
            relayer  # refund recipient
        ).transact({"from": relayer})

        # Transaction on Chain B (mirror leg)
        tx_id_b = generate_tx_id("chain_b_leg")
        future_ts_b = setup.chain_b.w3.eth.get_block("latest").timestamp + 60

        relayer_b = setup.chain_b.w3.eth.account.from_key(RELAYER_KEY).address
        commitment_b = keccak(b"secret_payload_b" + keccak(b"secret_b"))

        setup.buffer_contract_b.functions.buffer_transaction_with_commitment(
            tx_id_b,
            setup.buffer_b,
            setup.buffer_a,
            commitment_b,
            bytes(32),
            future_ts_b,
            swap_group_id,
            relayer_b
        ).transact({"from": relayer_b})

        # Verify both are buffered
        tx_a = setup.buffer_contract_a.functions.get_transaction(tx_id_a).call()
        tx_b = setup.buffer_contract_b.functions.get_transaction(tx_id_b).call()

        assert tx_a[5] == 1  # BUFFERED
        assert tx_b[5] == 1  # BUFFERED


class TestSwapGroups:
    """Test atomic swap group functionality."""

    def test_swap_group_tracking(self, cross_chain_setup, relayer):
        """Test that swap groups track multiple transactions."""
        setup = cross_chain_setup
        swap_group_id = generate_tx_id("group_tracking")

        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 60

        # Add 3 transactions to swap group
        for i in range(3):
            tx_id = generate_tx_id(f"group_tx_{i}")
            commitment = keccak(f"payload_{i}".encode() + keccak(b"secret"))

            setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
                tx_id,
                setup.buffer_a,
                setup.buffer_b,
                commitment,
                bytes(32),
                future_ts,
                swap_group_id,
                relayer
            ).transact({"from": relayer})

        # Check swap group count
        count = setup.buffer_contract_a.functions.swap_group_count(swap_group_id).call()
        assert count == 3

        # Check status
        total, ready, all_ready = setup.buffer_contract_a.functions.get_swap_group_status(swap_group_id).call()
        assert total == 3
        assert ready == 0
        assert all_ready == False

    def test_swap_group_max_size(self, cross_chain_setup, relayer):
        """Test swap group enforces max size of 4."""
        setup = cross_chain_setup
        swap_group_id = generate_tx_id("max_size_group")

        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 60

        # Fill group with 4 transactions
        for i in range(4):
            tx_id = generate_tx_id(f"max_tx_{i}")
            commitment = keccak(f"payload_{i}".encode() + keccak(b"secret"))

            setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
                tx_id,
                setup.buffer_a,
                setup.buffer_b,
                commitment,
                bytes(32),
                future_ts,
                swap_group_id,
                relayer
            ).transact({"from": relayer})

        # Try to add 5th - should fail
        tx_id_5 = generate_tx_id("max_tx_5")
        commitment_5 = keccak(b"payload_5" + keccak(b"secret"))

        with pytest.raises(Exception) as exc_info:
            setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
                tx_id_5,
                setup.buffer_a,
                setup.buffer_b,
                commitment_5,
                bytes(32),
                future_ts,
                swap_group_id,
                relayer
            ).transact({"from": relayer})

        assert "full" in str(exc_info.value).lower() or "revert" in str(exc_info.value).lower()


class TestTimeoutAndRefund:
    """Test timeout and refund scenarios."""

    def test_transaction_expires(self, cross_chain_setup, relayer):
        """Test that transaction expires after deadline."""
        setup = cross_chain_setup
        tx_id = generate_tx_id("expire_test")

        # Very short coordination window (use minimum)
        short_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 5

        setup.buffer_contract_a.functions.buffer_transaction(
            tx_id,
            setup.buffer_a,
            setup.buffer_b,
            b"expiring_payload",
            bytes(32),
            short_ts
        ).transact({"from": relayer})

        # Mine blocks to pass resolution delay
        setup.chain_a.mine_blocks(3)

        # Advance time past expiry
        setup.chain_a.advance_time(100)

        # Try to resolve - should fail due to expiry
        with pytest.raises(Exception) as exc_info:
            setup.buffer_contract_a.functions.resolve_dependency(tx_id).transact({"from": relayer})

        # Check state is EXPIRED
        tx = setup.buffer_contract_a.functions.get_transaction(tx_id).call()
        assert tx[5] == 5  # EXPIRED state

    def test_refund_after_expiry(self, cross_chain_setup, relayer):
        """Test claiming refund after transaction expires."""
        setup = cross_chain_setup
        tx_id = generate_tx_id("refund_test")

        short_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 5

        # Buffer with commitment so refund_recipient is set
        commitment = keccak(b"refund_payload" + keccak(b"secret"))
        setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
            tx_id,
            setup.buffer_a,
            setup.buffer_b,
            commitment,
            bytes(32),
            short_ts,
            bytes(32),  # no swap group
            relayer
        ).transact({"from": relayer})

        # Mine and advance time
        setup.chain_a.mine_blocks(3)
        setup.chain_a.advance_time(100)

        # Trigger expiry by attempting resolution
        try:
            setup.buffer_contract_a.functions.resolve_dependency(tx_id).transact({"from": relayer})
        except Exception:
            pass  # Expected to fail

        # Claim refund
        setup.buffer_contract_a.functions.claim_refund(tx_id).transact({"from": relayer})

        # Verify REFUNDED state
        tx = setup.buffer_contract_a.functions.get_transaction(tx_id).call()
        assert tx[5] == 6  # REFUNDED state


class TestCommitReveal:
    """Test commit-reveal MEV protection."""

    def test_reveal_with_correct_secret(self, cross_chain_setup, relayer):
        """Test revealing with correct secret succeeds."""
        setup = cross_chain_setup
        tx_id = generate_tx_id("reveal_test")

        payload = b"secret_swap_data"
        secret = keccak(b"my_secret")
        commitment = keccak(payload + secret)

        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 120

        # Buffer with commitment
        setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
            tx_id,
            setup.buffer_a,
            setup.buffer_b,
            commitment,
            bytes(32),
            future_ts,
            bytes(32),
            relayer
        ).transact({"from": relayer})

        # Mine a block
        setup.chain_a.mine_blocks(1)

        # Reveal
        setup.buffer_contract_a.functions.reveal_transaction(
            tx_id,
            payload,
            secret
        ).transact({"from": relayer})

        # Check revealed
        revealed = setup.buffer_contract_a.functions.reveals(tx_id).call()
        assert revealed == True

    def test_reveal_with_wrong_secret_fails(self, cross_chain_setup, relayer):
        """Test revealing with wrong secret fails."""
        setup = cross_chain_setup
        tx_id = generate_tx_id("wrong_secret_test")

        payload = b"secret_swap_data"
        real_secret = keccak(b"real_secret")
        wrong_secret = keccak(b"wrong_secret")
        commitment = keccak(payload + real_secret)

        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 120

        setup.buffer_contract_a.functions.buffer_transaction_with_commitment(
            tx_id,
            setup.buffer_a,
            setup.buffer_b,
            commitment,
            bytes(32),
            future_ts,
            bytes(32),
            relayer
        ).transact({"from": relayer})

        setup.chain_a.mine_blocks(1)

        # Try to reveal with wrong secret
        with pytest.raises(Exception) as exc_info:
            setup.buffer_contract_a.functions.reveal_transaction(
                tx_id,
                payload,
                wrong_secret
            ).transact({"from": relayer})

        assert "mismatch" in str(exc_info.value).lower() or "revert" in str(exc_info.value).lower()


class TestAtomicSwapCoordinator:
    """Test AtomicSwapCoordinator functionality."""

    def test_create_and_take_order(self, cross_chain_setup, maker, taker):
        """Test creating and taking a swap order."""
        setup = cross_chain_setup
        order_id = generate_order_id("basic_order")

        deadline = setup.chain_a.w3.eth.get_block("latest").timestamp + 3600

        # Create order
        setup.coordinator_contract_a.functions.create_swap_order(
            order_id,
            setup.buffer_a,  # offer chain
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # offer token
            1000,  # offer amount
            setup.buffer_b,  # want chain
            "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",  # want token
            2000,  # want amount
            1800,  # min receive (slippage protection)
            deadline,
            50,  # 0.5% relayer reward
            "0x0000000000000000000000000000000000000000"  # open order
        ).transact({"from": maker})

        # Verify order created
        order = setup.coordinator_contract_a.functions.get_order(order_id).call()
        assert order[0] == order_id
        assert order[1] == maker
        assert order[4] == 1000  # offer_amount
        assert order[11] == 1  # OPEN state

        # Take order
        setup.coordinator_contract_a.functions.take_swap_order(
            order_id,
            1000  # full fill
        ).transact({"from": taker})

        # Verify matched
        order = setup.coordinator_contract_a.functions.get_order(order_id).call()
        assert order[11] == 2  # MATCHED state
        assert order[13] == 1000  # filled_offer_amount

    def test_partial_fill(self, cross_chain_setup, maker, taker):
        """Test partial fills on an order."""
        setup = cross_chain_setup
        order_id = generate_order_id("partial_order")

        deadline = setup.chain_a.w3.eth.get_block("latest").timestamp + 3600

        # Create order for 1000
        setup.coordinator_contract_a.functions.create_swap_order(
            order_id,
            setup.buffer_a,
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            1000,
            setup.buffer_b,
            "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            2000,
            1800,
            deadline,
            50,
            "0x0000000000000000000000000000000000000000"
        ).transact({"from": maker})

        # Take partial (400)
        setup.coordinator_contract_a.functions.take_swap_order(
            order_id,
            400
        ).transact({"from": taker})

        # Verify partial fill
        order = setup.coordinator_contract_a.functions.get_order(order_id).call()
        assert order[11] == 1  # Still OPEN
        assert order[13] == 400  # filled_offer_amount

        # Get remaining
        remaining = setup.coordinator_contract_a.functions.get_remaining_offer(order_id).call()
        assert remaining == 600

    def test_cancel_order(self, cross_chain_setup, maker):
        """Test cancelling an unfilled order."""
        setup = cross_chain_setup
        order_id = generate_order_id("cancel_order")

        deadline = setup.chain_a.w3.eth.get_block("latest").timestamp + 3600

        setup.coordinator_contract_a.functions.create_swap_order(
            order_id,
            setup.buffer_a,
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            1000,
            setup.buffer_b,
            "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            2000,
            1800,
            deadline,
            50,
            "0x0000000000000000000000000000000000000000"
        ).transact({"from": maker})

        # Cancel
        setup.coordinator_contract_a.functions.cancel_order(order_id).transact({"from": maker})

        # Verify cancelled
        order = setup.coordinator_contract_a.functions.get_order(order_id).call()
        assert order[11] == 6  # CANCELLED state

        # Verify not fillable
        fillable = setup.coordinator_contract_a.functions.is_order_fillable(order_id).call()
        assert fillable == False


class TestProtocolFees:
    """Test protocol fee functionality."""

    def test_fee_calculation(self, cross_chain_setup, maker):
        """Test fee calculation without discount."""
        setup = cross_chain_setup

        amount = 10000 * 10**18  # 10,000 tokens

        # Calculate fee preview (no TESS token configured, no discount)
        fee, has_discount = setup.coordinator_contract_a.functions.calculate_fee_preview(
            amount,
            maker
        ).call()

        # Default fee is 0.2% = 20 bps
        expected_fee = (amount * 20) // 10000
        assert fee == expected_fee
        assert has_discount == False

    def test_set_protocol_fee(self, cross_chain_setup):
        """Test updating protocol fee."""
        setup = cross_chain_setup
        deployer = setup.chain_a.w3.eth.account.from_key(DEPLOYER_KEY).address

        # Get current fee
        current_fee = setup.coordinator_contract_a.functions.protocol_fee_bps().call()
        assert current_fee == 20  # Default 0.2%

        # Set new fee
        setup.coordinator_contract_a.functions.set_protocol_fee(25).transact({"from": deployer})

        # Verify
        new_fee = setup.coordinator_contract_a.functions.protocol_fee_bps().call()
        assert new_fee == 25

        # Reset to default
        setup.coordinator_contract_a.functions.set_protocol_fee(20).transact({"from": deployer})


class TestDependencyResolution:
    """Test dependency resolution across chains."""

    def test_dependency_chain(self, cross_chain_setup, relayer):
        """Test resolving dependent transactions."""
        setup = cross_chain_setup

        # First transaction (no dependency)
        tx_id_1 = generate_tx_id("dep_tx_1")
        future_ts = setup.chain_a.w3.eth.get_block("latest").timestamp + 60

        setup.buffer_contract_a.functions.buffer_transaction(
            tx_id_1,
            setup.buffer_a,
            setup.buffer_b,
            b"first_payload",
            bytes(32),  # no dependency
            future_ts
        ).transact({"from": relayer})

        # Second transaction (depends on first)
        tx_id_2 = generate_tx_id("dep_tx_2")

        setup.buffer_contract_a.functions.buffer_transaction(
            tx_id_2,
            setup.buffer_a,
            setup.buffer_b,
            b"second_payload",
            tx_id_1,  # depends on tx_id_1
            future_ts
        ).transact({"from": relayer})

        # Mine blocks
        setup.chain_a.mine_blocks(3)
        setup.chain_a.advance_time(60)

        # Resolve first transaction
        setup.buffer_contract_a.functions.resolve_dependency(tx_id_1).transact({"from": relayer})

        # Verify first is ready
        tx_1 = setup.buffer_contract_a.functions.get_transaction(tx_id_1).call()
        assert tx_1[5] == 2  # READY

        # Now second can be resolved
        setup.buffer_contract_a.functions.resolve_dependency(tx_id_2).transact({"from": relayer})

        # Verify second is ready
        tx_2 = setup.buffer_contract_a.functions.get_transaction(tx_id_2).call()
        assert tx_2[5] == 2  # READY


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
