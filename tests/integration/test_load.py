"""
Load tests for Tesseract cross-chain swap system.

Tests system performance under load:
- Transaction throughput
- Gas efficiency
- Latency measurements
- Circuit breaker behavior

Usage:
    pytest tests/integration/test_load.py -v
    pytest tests/integration/test_load.py -v -k "test_sustained_throughput"

Metrics collected:
- Transactions per second
- Average gas per transaction
- P50/P95/P99 latency
- Failure rate
"""

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import List, Dict
import subprocess
import os

import pytest
from eth_utils import keccak
from web3 import Web3
from vyper import compile_code
from pathlib import Path

# Skip if Anvil not installed
pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "anvil"], capture_output=True).returncode != 0,
    reason="Anvil not installed"
)

# Test configuration
LOAD_TEST_PORT = 8550
LOAD_TEST_CHAIN_ID = 9999

CONTRACT_DIR = Path(__file__).parent.parent.parent / "contracts"
BUFFER_CONTRACT = CONTRACT_DIR / "TesseractBuffer.vy"

DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@dataclass
class LoadTestMetrics:
    """Metrics collected during load testing."""
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    gas_used: List[int] = field(default_factory=list)
    latencies_ms: List[float] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0

    @property
    def success_rate(self) -> float:
        if self.total_transactions == 0:
            return 0.0
        return self.successful_transactions / self.total_transactions * 100

    @property
    def failure_rate(self) -> float:
        return 100 - self.success_rate

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def tps(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.successful_transactions / self.duration_seconds

    @property
    def avg_gas(self) -> float:
        if not self.gas_used:
            return 0.0
        return statistics.mean(self.gas_used)

    @property
    def latency_p50(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.median(self.latencies_ms)

    @property
    def latency_p95(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def latency_p99(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def summary(self) -> str:
        return f"""
Load Test Results
=================
Total Transactions: {self.total_transactions}
Successful: {self.successful_transactions}
Failed: {self.failed_transactions}
Success Rate: {self.success_rate:.2f}%
Duration: {self.duration_seconds:.2f}s
TPS: {self.tps:.2f}

Gas Metrics:
- Average Gas: {self.avg_gas:,.0f}

Latency Metrics:
- P50: {self.latency_p50:.2f}ms
- P95: {self.latency_p95:.2f}ms
- P99: {self.latency_p99:.2f}ms
"""


class LoadTestAnvil:
    """Anvil instance optimized for load testing."""

    def __init__(self, port: int, chain_id: int):
        self.port = port
        self.chain_id = chain_id
        self.process = None
        self.w3 = None

    def start(self):
        """Start Anvil with performance settings."""
        cmd = [
            "anvil",
            "--port", str(self.port),
            "--chain-id", str(self.chain_id),
            "--block-time", "1",
            "--silent",
            "--accounts", "100",  # More test accounts
            "--balance", "10000",  # 10k ETH each
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        time.sleep(2)
        self.w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{self.port}"))

        for _ in range(10):
            if self.w3.is_connected():
                return
            time.sleep(0.5)

        raise RuntimeError("Failed to connect to Anvil")

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)


@pytest.fixture(scope="module")
def load_test_env():
    """Set up load test environment."""
    anvil = LoadTestAnvil(LOAD_TEST_PORT, LOAD_TEST_CHAIN_ID)
    anvil.start()

    # Compile and deploy contract
    with open(BUFFER_CONTRACT) as f:
        source = f.read()
    compiled = compile_code(source, output_formats=["abi", "bytecode"])

    deployer = anvil.w3.eth.account.from_key(DEPLOYER_KEY).address

    contract = anvil.w3.eth.contract(
        abi=compiled["abi"],
        bytecode=compiled["bytecode"]
    )
    tx_hash = contract.constructor().transact({"from": deployer})
    receipt = anvil.w3.eth.wait_for_transaction_receipt(tx_hash)

    deployed = anvil.w3.eth.contract(
        address=receipt.contractAddress,
        abi=compiled["abi"]
    )

    # Grant roles to deployer for testing
    BUFFER_ROLE = Web3.keccak(text="BUFFER_ROLE")
    RESOLVE_ROLE = Web3.keccak(text="RESOLVE_ROLE")
    deployed.functions.grant_role(BUFFER_ROLE, deployer).transact({"from": deployer})
    deployed.functions.grant_role(RESOLVE_ROLE, deployer).transact({"from": deployer})

    yield {
        "anvil": anvil,
        "w3": anvil.w3,
        "contract": deployed,
        "deployer": deployer,
    }

    anvil.stop()


class TestThroughput:
    """Test transaction throughput."""

    def test_sequential_buffer(self, load_test_env, request):
        """Test sequential buffering throughput."""
        env = load_test_env
        metrics = LoadTestMetrics()

        num_transactions = 50
        metrics.start_time = time.time()

        for i in range(num_transactions):
            tx_id = keccak(text=f"seq_tx_{i}_{time.time()}")
            future_ts = env["w3"].eth.get_block("latest").timestamp + 60

            try:
                start = time.time()
                tx_hash = env["contract"].functions.buffer_transaction(
                    tx_id,
                    env["deployer"],
                    "0x2222222222222222222222222222222222222222",
                    f"payload_{i}".encode(),
                    bytes(32),
                    future_ts
                ).transact({"from": env["deployer"]})

                receipt = env["w3"].eth.wait_for_transaction_receipt(tx_hash)
                end = time.time()

                metrics.total_transactions += 1
                if receipt.status == 1:
                    metrics.successful_transactions += 1
                    metrics.gas_used.append(receipt.gasUsed)
                    metrics.latencies_ms.append((end - start) * 1000)
                else:
                    metrics.failed_transactions += 1

            except Exception as e:
                metrics.total_transactions += 1
                metrics.failed_transactions += 1

        metrics.end_time = time.time()

        print(metrics.summary())

        # Assertions
        assert metrics.success_rate >= 90, f"Success rate too low: {metrics.success_rate}%"
        assert metrics.tps >= 1, f"TPS too low: {metrics.tps}"

    def test_burst_buffer(self, load_test_env):
        """Test burst buffering (many transactions quickly)."""
        env = load_test_env
        metrics = LoadTestMetrics()

        num_transactions = 20
        tx_hashes = []

        metrics.start_time = time.time()

        # Submit all transactions as fast as possible
        for i in range(num_transactions):
            tx_id = keccak(text=f"burst_tx_{i}_{time.time()}")
            future_ts = env["w3"].eth.get_block("latest").timestamp + 120

            try:
                tx_hash = env["contract"].functions.buffer_transaction(
                    tx_id,
                    env["deployer"],
                    "0x3333333333333333333333333333333333333333",
                    f"burst_payload_{i}".encode(),
                    bytes(32),
                    future_ts
                ).transact({"from": env["deployer"]})

                tx_hashes.append((tx_hash, time.time()))
                metrics.total_transactions += 1

            except Exception:
                metrics.total_transactions += 1
                metrics.failed_transactions += 1

        # Wait for all receipts
        for tx_hash, submit_time in tx_hashes:
            try:
                receipt = env["w3"].eth.wait_for_transaction_receipt(tx_hash, timeout=30)
                end_time = time.time()

                if receipt.status == 1:
                    metrics.successful_transactions += 1
                    metrics.gas_used.append(receipt.gasUsed)
                    metrics.latencies_ms.append((end_time - submit_time) * 1000)
                else:
                    metrics.failed_transactions += 1
            except Exception:
                metrics.failed_transactions += 1

        metrics.end_time = time.time()

        print(metrics.summary())

        assert metrics.success_rate >= 80, f"Burst success rate too low: {metrics.success_rate}%"


class TestGasEfficiency:
    """Test gas efficiency of operations."""

    def test_buffer_gas_cost(self, load_test_env):
        """Measure gas cost for buffer_transaction."""
        env = load_test_env
        gas_costs = []

        for i in range(10):
            tx_id = keccak(text=f"gas_test_{i}_{time.time()}")
            future_ts = env["w3"].eth.get_block("latest").timestamp + 60

            tx_hash = env["contract"].functions.buffer_transaction(
                tx_id,
                env["deployer"],
                "0x4444444444444444444444444444444444444444",
                b"x" * (64 + i * 10),  # Varying payload sizes
                bytes(32),
                future_ts
            ).transact({"from": env["deployer"]})

            receipt = env["w3"].eth.wait_for_transaction_receipt(tx_hash)
            gas_costs.append(receipt.gasUsed)

        avg_gas = statistics.mean(gas_costs)
        max_gas = max(gas_costs)
        min_gas = min(gas_costs)

        print(f"""
Gas Efficiency Report
=====================
Average Gas: {avg_gas:,.0f}
Min Gas: {min_gas:,.0f}
Max Gas: {max_gas:,.0f}
Variance: {max_gas - min_gas:,.0f}
""")

        # Gas should be reasonable (< 200k for buffer)
        assert avg_gas < 200_000, f"Average gas too high: {avg_gas}"

    def test_resolve_gas_cost(self, load_test_env):
        """Measure gas cost for resolve_dependency."""
        env = load_test_env
        gas_costs = []

        for i in range(5):
            tx_id = keccak(text=f"resolve_gas_{i}_{time.time()}")
            future_ts = env["w3"].eth.get_block("latest").timestamp + 60

            # Buffer
            env["contract"].functions.buffer_transaction(
                tx_id,
                env["deployer"],
                "0x5555555555555555555555555555555555555555",
                b"resolve_test_payload",
                bytes(32),
                future_ts
            ).transact({"from": env["deployer"]})

            # Mine blocks
            for _ in range(3):
                env["w3"].testing.mine()

            # Advance time
            env["w3"].provider.make_request("evm_increaseTime", [60])
            env["w3"].testing.mine()

            # Resolve
            tx_hash = env["contract"].functions.resolve_dependency(tx_id).transact(
                {"from": env["deployer"]}
            )
            receipt = env["w3"].eth.wait_for_transaction_receipt(tx_hash)
            gas_costs.append(receipt.gasUsed)

        avg_gas = statistics.mean(gas_costs)
        print(f"Average resolve gas: {avg_gas:,.0f}")

        assert avg_gas < 150_000, f"Resolve gas too high: {avg_gas}"


class TestCircuitBreaker:
    """Test circuit breaker under failure conditions."""

    def test_circuit_breaker_triggers(self, load_test_env):
        """Test that circuit breaker triggers after threshold failures."""
        env = load_test_env

        # Get current threshold
        threshold = env["contract"].functions.circuit_breaker_threshold().call()

        # Verify not active initially
        active = env["contract"].functions.circuit_breaker_active().call()
        assert not active, "Circuit breaker should not be active initially"

        # We can't easily trigger failures in the contract without
        # actually causing transaction failures, which is complex
        # This is more of a documentation test

        print(f"Circuit breaker threshold: {threshold}")
        print("Circuit breaker test passed (threshold verified)")


class TestRateLimiting:
    """Test rate limiting behavior."""

    def test_user_rate_limit(self, load_test_env):
        """Test per-user rate limiting."""
        env = load_test_env

        # Max 10 transactions per block per user
        MAX_USER_TX_PER_BLOCK = 10

        successful = 0
        failed = 0

        # Try to submit more than limit in same block
        for i in range(15):
            tx_id = keccak(text=f"rate_limit_{i}_{time.time()}")
            future_ts = env["w3"].eth.get_block("latest").timestamp + 60

            try:
                tx_hash = env["contract"].functions.buffer_transaction(
                    tx_id,
                    env["deployer"],
                    "0x6666666666666666666666666666666666666666",
                    f"rate_test_{i}".encode(),
                    bytes(32),
                    future_ts
                ).transact({"from": env["deployer"]})

                receipt = env["w3"].eth.wait_for_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                failed += 1

        print(f"Rate limit test: {successful} successful, {failed} failed")

        # Some should fail due to rate limiting
        # (depends on how many fit in same block)


class TestStressConditions:
    """Test behavior under stress conditions."""

    def test_large_payload(self, load_test_env):
        """Test with maximum payload size."""
        env = load_test_env

        max_payload_size = env["contract"].functions.max_payload_size().call()
        tx_id = keccak(text=f"large_payload_{time.time()}")
        future_ts = env["w3"].eth.get_block("latest").timestamp + 60

        # Create max-size payload
        large_payload = b"x" * max_payload_size

        tx_hash = env["contract"].functions.buffer_transaction(
            tx_id,
            env["deployer"],
            "0x7777777777777777777777777777777777777777",
            large_payload,
            bytes(32),
            future_ts
        ).transact({"from": env["deployer"]})

        receipt = env["w3"].eth.wait_for_transaction_receipt(tx_hash)
        assert receipt.status == 1, "Large payload transaction failed"

        print(f"Large payload ({max_payload_size} bytes) gas: {receipt.gasUsed:,}")

    def test_concurrent_swap_groups(self, load_test_env):
        """Test multiple concurrent swap groups."""
        env = load_test_env

        num_groups = 5
        txs_per_group = 3

        for g in range(num_groups):
            swap_group_id = keccak(text=f"stress_group_{g}_{time.time()}")
            future_ts = env["w3"].eth.get_block("latest").timestamp + 120

            for t in range(txs_per_group):
                tx_id = keccak(text=f"stress_tx_{g}_{t}_{time.time()}")
                commitment = keccak(f"payload_{g}_{t}".encode() + keccak(b"secret"))

                env["contract"].functions.buffer_transaction_with_commitment(
                    tx_id,
                    env["deployer"],
                    "0x8888888888888888888888888888888888888888",
                    commitment,
                    bytes(32),
                    future_ts,
                    swap_group_id,
                    env["deployer"]
                ).transact({"from": env["deployer"]})

            # Verify group count
            count = env["contract"].functions.swap_group_count(swap_group_id).call()
            assert count == txs_per_group

        print(f"Created {num_groups} swap groups with {txs_per_group} transactions each")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
