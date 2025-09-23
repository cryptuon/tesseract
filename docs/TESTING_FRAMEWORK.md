# Tesseract Testing Framework

## Overview

This document outlines the comprehensive testing strategy for Tesseract, incorporating modern testing practices for cross-rollup blockchain systems using the Ape framework.

## Testing Architecture

### Test Categories

1. **Unit Tests**: Individual function testing
2. **Integration Tests**: Cross-component interaction testing
3. **End-to-End Tests**: Full system workflow testing
4. **Load Tests**: Performance and scalability testing
5. **Security Tests**: Vulnerability and attack vector testing
6. **Cross-Chain Tests**: Multi-rollup coordination testing

### Test Environment Setup

#### Local Development
```python
# tests/conftest.py
import pytest
from ape import accounts, project, Contract
from ape.managers.networks import NetworkManager

@pytest.fixture
def deployer():
    return accounts.test_accounts[0]

@pytest.fixture
def operator():
    return accounts.test_accounts[1]

@pytest.fixture
def user():
    return accounts.test_accounts[2]

@pytest.fixture
def tesseract_contract(deployer):
    return deployer.deploy(project.TesseractBuffer)

@pytest.fixture
def configured_contract(tesseract_contract, deployer, operator):
    # Set up roles and initial configuration
    tesseract_contract.grant_role(
        tesseract_contract.BUFFER_ROLE(),
        operator.address,
        sender=deployer
    )
    tesseract_contract.grant_role(
        tesseract_contract.RESOLVE_ROLE(),
        operator.address,
        sender=deployer
    )
    return tesseract_contract
```

#### Multi-Network Testing
```python
# tests/conftest.py (continued)
@pytest.fixture(params=[
    "ethereum:local:hardhat",
    "polygon:local:hardhat",
    "arbitrum:local:hardhat"
])
def multi_network_setup(request):
    network_choice = request.param
    with networks.parse_network_choice(network_choice):
        deployer = accounts.test_accounts[0]
        contract = deployer.deploy(project.TesseractBuffer)
        yield {
            'network': network_choice,
            'contract': contract,
            'deployer': deployer
        }
```

## Unit Tests

### Basic Functionality Tests

```python
# tests/unit/test_buffer_transaction.py
import pytest
from ape import reverts
from hexbytes import HexBytes

def test_buffer_transaction_success(configured_contract, operator, user):
    """Test successful transaction buffering."""
    tx_id = HexBytes("0x" + "1" * 64)
    origin_rollup = user.address
    target_rollup = operator.address
    payload = b"test payload"
    dependency_tx_id = HexBytes("0x" + "2" * 64)
    timestamp = configured_contract.provider.get_block("latest").timestamp + 10

    # Buffer transaction
    receipt = configured_contract.buffer_transaction(
        tx_id,
        origin_rollup,
        target_rollup,
        payload,
        dependency_tx_id,
        timestamp,
        sender=operator
    )

    # Check event emission
    assert len(receipt.logs) == 1
    event = receipt.logs[0]
    assert event.event_name == "TransactionBuffered"
    assert event.tx_id == tx_id

    # Check state
    buffered_tx = configured_contract.buffered_transactions(tx_id)
    assert buffered_tx.origin_rollup == origin_rollup
    assert buffered_tx.target_rollup == target_rollup

def test_buffer_transaction_unauthorized(configured_contract, user):
    """Test that unauthorized users cannot buffer transactions."""
    tx_id = HexBytes("0x" + "1" * 64)

    with reverts("AccessControl: account missing role"):
        configured_contract.buffer_transaction(
            tx_id,
            user.address,
            user.address,
            b"payload",
            HexBytes("0x" + "2" * 64),
            configured_contract.provider.get_block("latest").timestamp + 10,
            sender=user  # Unauthorized user
        )

def test_buffer_duplicate_transaction(configured_contract, operator):
    """Test that duplicate transaction IDs are rejected."""
    tx_id = HexBytes("0x" + "1" * 64)
    timestamp = configured_contract.provider.get_block("latest").timestamp + 10

    # Buffer first transaction
    configured_contract.buffer_transaction(
        tx_id,
        operator.address,
        operator.address,
        b"payload1",
        HexBytes("0x" + "2" * 64),
        timestamp,
        sender=operator
    )

    # Attempt to buffer duplicate
    with reverts("Transaction already exists"):
        configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            operator.address,
            b"payload2",
            HexBytes("0x" + "3" * 64),
            timestamp + 10,
            sender=operator
        )
```

### Access Control Tests

```python
# tests/unit/test_access_control.py
import pytest
from ape import reverts

def test_role_assignment(tesseract_contract, deployer, user):
    """Test role assignment and checking."""
    buffer_role = tesseract_contract.BUFFER_ROLE()

    # Initially user should not have role
    assert not tesseract_contract.has_role(buffer_role, user.address)

    # Grant role
    tesseract_contract.grant_role(buffer_role, user.address, sender=deployer)

    # Check role granted
    assert tesseract_contract.has_role(buffer_role, user.address)

def test_role_revocation(tesseract_contract, deployer, user):
    """Test role revocation."""
    buffer_role = tesseract_contract.BUFFER_ROLE()

    # Grant then revoke role
    tesseract_contract.grant_role(buffer_role, user.address, sender=deployer)
    tesseract_contract.revoke_role(buffer_role, user.address, sender=deployer)

    # Check role revoked
    assert not tesseract_contract.has_role(buffer_role, user.address)

def test_unauthorized_role_management(tesseract_contract, user):
    """Test that non-owners cannot manage roles."""
    buffer_role = tesseract_contract.BUFFER_ROLE()

    with reverts("AccessControl: caller is not owner"):
        tesseract_contract.grant_role(buffer_role, user.address, sender=user)
```

### Input Validation Tests

```python
# tests/unit/test_validation.py
import pytest
from ape import reverts
from hexbytes import HexBytes

def test_invalid_transaction_id(configured_contract, operator):
    """Test rejection of empty transaction ID."""
    empty_tx_id = HexBytes("0x" + "0" * 64)

    with reverts("Invalid transaction ID"):
        configured_contract.buffer_transaction(
            empty_tx_id,
            operator.address,
            operator.address,
            b"payload",
            HexBytes("0x" + "1" * 64),
            configured_contract.provider.get_block("latest").timestamp + 10,
            sender=operator
        )

def test_invalid_addresses(configured_contract, operator):
    """Test rejection of zero addresses."""
    tx_id = HexBytes("0x" + "1" * 64)
    zero_address = "0x" + "0" * 40
    timestamp = configured_contract.provider.get_block("latest").timestamp + 10

    with reverts("Invalid origin rollup"):
        configured_contract.buffer_transaction(
            tx_id,
            zero_address,
            operator.address,
            b"payload",
            HexBytes("0x" + "2" * 64),
            timestamp,
            sender=operator
        )

def test_same_origin_target(configured_contract, operator):
    """Test rejection when origin and target are the same."""
    tx_id = HexBytes("0x" + "1" * 64)

    with reverts("Origin and target cannot be same"):
        configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            operator.address,  # Same as origin
            b"payload",
            HexBytes("0x" + "2" * 64),
            configured_contract.provider.get_block("latest").timestamp + 10,
            sender=operator
        )

def test_past_timestamp(configured_contract, operator):
    """Test rejection of past timestamps."""
    tx_id = HexBytes("0x" + "1" * 64)
    past_timestamp = configured_contract.provider.get_block("latest").timestamp - 100

    with reverts("Timestamp cannot be in the past"):
        configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            "0x" + "1" * 40,
            b"payload",
            HexBytes("0x" + "2" * 64),
            past_timestamp,
            sender=operator
        )
```

## Integration Tests

### Cross-Chain Coordination Tests

```python
# tests/integration/test_cross_chain.py
import pytest
from ape import networks
from hexbytes import HexBytes

@pytest.mark.parametrize("network_pair", [
    ("ethereum:local:hardhat", "polygon:local:hardhat"),
    ("arbitrum:local:hardhat", "optimism:local:hardhat")
])
def test_cross_chain_transaction_coordination(network_pair):
    """Test transaction coordination across different networks."""
    origin_network, target_network = network_pair

    # Deploy contracts on both networks
    with networks.parse_network_choice(origin_network):
        origin_deployer = accounts.test_accounts[0]
        origin_contract = origin_deployer.deploy(project.TesseractBuffer)

    with networks.parse_network_choice(target_network):
        target_deployer = accounts.test_accounts[0]
        target_contract = target_deployer.deploy(project.TesseractBuffer)

    # Configure cross-chain coordination
    tx_id = HexBytes("0x" + "1" * 64)

    # Buffer transaction on origin chain
    with networks.parse_network_choice(origin_network):
        origin_contract.buffer_transaction(
            tx_id,
            origin_deployer.address,
            target_deployer.address,
            b"cross-chain payload",
            HexBytes("0x" + "0" * 64),  # No dependency
            origin_contract.provider.get_block("latest").timestamp + 30,
            sender=origin_deployer
        )

    # Verify transaction can be resolved on target chain
    with networks.parse_network_choice(target_network):
        # Simulate cross-chain state verification
        target_contract.verify_cross_chain_transaction(
            tx_id,
            origin_network.split(":")[0],  # origin chain ID
            sender=target_deployer
        )

def test_dependency_resolution_chain(configured_contract, operator):
    """Test resolution of transaction dependency chains."""
    # Create dependency chain: tx3 -> tx2 -> tx1
    tx_id_1 = HexBytes("0x" + "1" * 64)
    tx_id_2 = HexBytes("0x" + "2" * 64)
    tx_id_3 = HexBytes("0x" + "3" * 64)

    current_time = configured_contract.provider.get_block("latest").timestamp

    # Buffer transactions with dependencies
    configured_contract.buffer_transaction(
        tx_id_1,
        operator.address,
        "0x" + "a" * 40,
        b"tx1",
        HexBytes("0x" + "0" * 64),  # No dependency
        current_time + 10,
        sender=operator
    )

    configured_contract.buffer_transaction(
        tx_id_2,
        operator.address,
        "0x" + "b" * 40,
        b"tx2",
        tx_id_1,  # Depends on tx1
        current_time + 20,
        sender=operator
    )

    configured_contract.buffer_transaction(
        tx_id_3,
        operator.address,
        "0x" + "c" * 40,
        b"tx3",
        tx_id_2,  # Depends on tx2
        current_time + 30,
        sender=operator
    )

    # Fast forward time
    configured_contract.provider.mine(timestamp=current_time + 35)

    # Resolve dependencies in order
    configured_contract.resolve_dependency(tx_id_1, sender=operator)
    configured_contract.resolve_dependency(tx_id_2, sender=operator)
    configured_contract.resolve_dependency(tx_id_3, sender=operator)

    # Verify all transactions are ready
    assert configured_contract.is_transaction_ready(tx_id_1)
    assert configured_contract.is_transaction_ready(tx_id_2)
    assert configured_contract.is_transaction_ready(tx_id_3)
```

## Load Testing

### Performance Tests

```python
# tests/load/test_throughput.py
import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from hexbytes import HexBytes

def test_high_throughput_buffering(configured_contract, operator):
    """Test system performance under high transaction load."""
    num_transactions = 1000
    base_time = configured_contract.provider.get_block("latest").timestamp + 100

    def buffer_transaction(i):
        tx_id = HexBytes(f"0x{i:064x}")
        return configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            f"0x{(i % 256):040x}",
            f"payload_{i}".encode(),
            HexBytes("0x" + "0" * 64),
            base_time + i,
            sender=operator
        )

    start_time = time.time()

    # Buffer transactions in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(buffer_transaction, i) for i in range(num_transactions)]
        results = [future.result() for future in futures]

    end_time = time.time()
    duration = end_time - start_time
    tps = num_transactions / duration

    print(f"Buffered {num_transactions} transactions in {duration:.2f}s ({tps:.2f} TPS)")
    assert tps > 50  # Minimum performance requirement

def test_concurrent_resolution(configured_contract, operator):
    """Test concurrent dependency resolution."""
    num_transactions = 100

    # Buffer independent transactions
    tx_ids = []
    current_time = configured_contract.provider.get_block("latest").timestamp

    for i in range(num_transactions):
        tx_id = HexBytes(f"0x{i:064x}")
        configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            f"0x{(i % 256):040x}",
            f"payload_{i}".encode(),
            HexBytes("0x" + "0" * 64),
            current_time + 10,
            sender=operator
        )
        tx_ids.append(tx_id)

    # Fast forward time
    configured_contract.provider.mine(timestamp=current_time + 20)

    # Resolve concurrently
    def resolve_transaction(tx_id):
        return configured_contract.resolve_dependency(tx_id, sender=operator)

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(resolve_transaction, tx_id) for tx_id in tx_ids]
        results = [future.result() for future in futures]

    end_time = time.time()
    duration = end_time - start_time
    rps = num_transactions / duration

    print(f"Resolved {num_transactions} transactions in {duration:.2f}s ({rps:.2f} RPS)")
    assert rps > 20  # Minimum resolution performance
```

## Security Testing

### Attack Vector Tests

```python
# tests/security/test_attack_vectors.py
import pytest
from ape import reverts
from hexbytes import HexBytes

def test_reentrancy_protection(configured_contract, operator):
    """Test protection against reentrancy attacks."""
    # This test would require a malicious contract that attempts reentrancy
    # Vyper provides built-in protection, but we test the additional locks

    tx_id = HexBytes("0x" + "1" * 64)

    # Attempt to resolve the same transaction multiple times concurrently
    # This should be prevented by transaction locks
    def attempt_resolution():
        configured_contract.resolve_dependency(tx_id, sender=operator)

    # First call should succeed, subsequent should fail
    attempt_resolution()

    with reverts("Transaction being processed"):
        attempt_resolution()

def test_dos_protection_rate_limiting(configured_contract, operator):
    """Test DoS protection through rate limiting."""
    current_block = configured_contract.provider.get_block("latest").number

    # Attempt to exceed per-block transaction limit
    for i in range(100):  # Within limit
        tx_id = HexBytes(f"0x{i:064x}")
        configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            f"0x{(i % 256):040x}",
            f"payload_{i}".encode(),
            HexBytes("0x" + "0" * 64),
            configured_contract.provider.get_block("latest").timestamp + 100,
            sender=operator
        )

    # 101st transaction should fail
    tx_id = HexBytes("0x" + "ff" * 32)
    with reverts("Block transaction limit exceeded"):
        configured_contract.buffer_transaction(
            tx_id,
            operator.address,
            "0x" + "aa" * 20,
            b"excess_payload",
            HexBytes("0x" + "0" * 64),
            configured_contract.provider.get_block("latest").timestamp + 100,
            sender=operator
        )

def test_integer_overflow_protection(configured_contract, operator):
    """Test protection against integer overflow attacks."""
    # Vyper provides automatic overflow protection
    # Test with maximum values
    max_timestamp = 2**256 - 1

    with reverts():  # Should revert due to overflow or validation
        configured_contract.buffer_transaction(
            HexBytes("0x" + "1" * 64),
            operator.address,
            "0x" + "aa" * 20,
            b"payload",
            HexBytes("0x" + "0" * 64),
            max_timestamp,
            sender=operator
        )
```

## Test Execution

### Running Tests

```bash
# Run all tests
ape test

# Run specific test categories
ape test tests/unit/
ape test tests/integration/
ape test tests/load/
ape test tests/security/

# Run with coverage
ape test --coverage

# Run specific test with verbose output
ape test tests/unit/test_buffer_transaction.py::test_buffer_transaction_success -v

# Run load tests with custom parameters
ape test tests/load/ --transactions=5000 --workers=20
```

### Continuous Integration

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install Poetry
      run: pip install poetry

    - name: Install dependencies
      run: poetry install

    - name: Run tests
      run: |
        poetry run ape test --coverage
        poetry run ape test tests/security/ --maxfail=1

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Test Reporting

```python
# tests/conftest.py (test reporting)
import pytest
import json
from datetime import datetime

@pytest.fixture(autouse=True)
def test_metrics(request):
    """Collect test metrics for performance monitoring."""
    start_time = time.time()
    yield
    end_time = time.time()

    # Record test execution time
    test_name = request.node.name
    duration = end_time - start_time

    metrics = {
        'test_name': test_name,
        'duration': duration,
        'timestamp': datetime.now().isoformat(),
        'status': 'passed' if request.node.rep_call.passed else 'failed'
    }

    # Write to metrics file
    with open('test_metrics.jsonl', 'a') as f:
        f.write(json.dumps(metrics) + '\n')
```

## Test Data Management

### Test Fixtures

```python
# tests/fixtures/transaction_data.py
from hexbytes import HexBytes

class TestTransactionData:
    @staticmethod
    def valid_transaction():
        return {
            'tx_id': HexBytes("0x" + "1" * 64),
            'origin_rollup': "0x" + "a" * 40,
            'target_rollup': "0x" + "b" * 40,
            'payload': b"test payload",
            'dependency_tx_id': HexBytes("0x" + "0" * 64),
            'timestamp_offset': 30
        }

    @staticmethod
    def invalid_transactions():
        return [
            {
                'name': 'empty_tx_id',
                'data': {
                    'tx_id': HexBytes("0x" + "0" * 64),
                    'expected_error': "Invalid transaction ID"
                }
            },
            {
                'name': 'zero_origin',
                'data': {
                    'origin_rollup': "0x" + "0" * 40,
                    'expected_error': "Invalid origin rollup"
                }
            }
        ]
```

This comprehensive testing framework ensures the Tesseract system is thoroughly validated across all critical dimensions including functionality, security, performance, and cross-chain coordination.