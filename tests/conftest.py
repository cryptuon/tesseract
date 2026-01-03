"""
Shared pytest fixtures for Tesseract contract testing.

Provides deployed contract instances, account fixtures, and test utilities
for comprehensive testing of TesseractBuffer.vy.
"""

import pytest
from pathlib import Path
from web3 import Web3
from eth_tester import EthereumTester, PyEVMBackend
from vyper import compile_code
import os

# Constants matching TesseractBuffer.vy
BUFFER_ROLE = Web3.keccak(text="BUFFER_ROLE")
RESOLVE_ROLE = Web3.keccak(text="RESOLVE_ROLE")
ADMIN_ROLE = Web3.keccak(text="ADMIN_ROLE")

CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "TesseractBuffer.vy"


@pytest.fixture(scope="session")
def contract_source():
    """Load contract source code once per test session"""
    with open(CONTRACT_PATH, 'r') as f:
        return f.read()


@pytest.fixture(scope="session")
def compiled_contract(contract_source):
    """Compile contract once per test session"""
    return compile_code(
        contract_source,
        output_formats=['bytecode', 'abi']
    )


@pytest.fixture(scope="session")
def contract_abi(compiled_contract):
    """Extract ABI from compiled contract"""
    return compiled_contract['abi']


@pytest.fixture(scope="session")
def contract_bytecode(compiled_contract):
    """Extract bytecode from compiled contract"""
    return compiled_contract['bytecode']


@pytest.fixture
def eth_tester():
    """Create a fresh EthereumTester for each test"""
    return EthereumTester(backend=PyEVMBackend())


@pytest.fixture
def w3(eth_tester):
    """Create Web3 instance connected to EthereumTester"""
    from web3.providers.eth_tester import EthereumTesterProvider
    return Web3(EthereumTesterProvider(eth_tester))


@pytest.fixture
def accounts(w3):
    """Get test accounts from Web3"""
    return w3.eth.accounts


@pytest.fixture
def owner(accounts):
    """Owner account (deployer)"""
    return accounts[0]


@pytest.fixture
def operator(accounts):
    """Operator account with BUFFER_ROLE and RESOLVE_ROLE"""
    return accounts[1]


@pytest.fixture
def resolver(accounts):
    """Resolver account with RESOLVE_ROLE only"""
    return accounts[2]


@pytest.fixture
def unauthorized_user(accounts):
    """Unauthorized user account (no roles)"""
    return accounts[3]


@pytest.fixture
def emergency_admin(accounts):
    """Emergency admin account"""
    return accounts[4]


@pytest.fixture
def contract(w3, contract_abi, contract_bytecode, owner):
    """Deploy a fresh contract instance for each test"""
    Contract = w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)
    tx_hash = Contract.constructor().transact({'from': owner})
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return w3.eth.contract(
        address=tx_receipt.contractAddress,
        abi=contract_abi
    )


@pytest.fixture
def contract_with_operator(contract, owner, operator):
    """Contract with an authorized operator (has BUFFER_ROLE and RESOLVE_ROLE)"""
    contract.functions.grant_role(BUFFER_ROLE, operator).transact({'from': owner})
    contract.functions.grant_role(RESOLVE_ROLE, operator).transact({'from': owner})
    return contract


@pytest.fixture
def contract_with_resolver(contract, owner, resolver):
    """Contract with a resolver (has RESOLVE_ROLE only)"""
    contract.functions.grant_role(RESOLVE_ROLE, resolver).transact({'from': owner})
    return contract


_tx_counter = 0


def generate_tx_id(index: int = None) -> bytes:
    """Generate a unique transaction ID"""
    global _tx_counter
    if index is None:
        _tx_counter += 1
        index = _tx_counter
    return Web3.keccak(text=f"test_transaction_{index}_{os.urandom(4).hex()}")


def generate_payload(size: int = 64) -> bytes:
    """Generate test payload of specified size"""
    return os.urandom(size)


@pytest.fixture
def tx_id():
    """Generate a unique transaction ID for each test"""
    return generate_tx_id()


@pytest.fixture
def tx_ids():
    """Generate multiple transaction IDs"""
    return [generate_tx_id(i) for i in range(10)]


@pytest.fixture
def payload():
    """Generate a test payload"""
    return generate_payload(64)


@pytest.fixture
def origin_rollup(accounts):
    """Origin rollup address"""
    return accounts[5]


@pytest.fixture
def target_rollup(accounts):
    """Target rollup address (different from origin)"""
    return accounts[6]


@pytest.fixture
def current_timestamp(w3):
    """Get current block timestamp"""
    return w3.eth.get_block('latest').timestamp


@pytest.fixture
def future_timestamp(w3):
    """Get a timestamp in the future (recalculated at use time)"""
    # Get fresh timestamp and add buffer
    return w3.eth.get_block('latest').timestamp + 60


@pytest.fixture
def past_timestamp(w3):
    """Get a timestamp in the past"""
    return w3.eth.get_block('latest').timestamp - 10


@pytest.fixture
def far_future_timestamp(w3):
    """Get a timestamp more than 24 hours in the future (invalid)"""
    return w3.eth.get_block('latest').timestamp + 100000  # ~27 hours


class ContractHelper:
    """Helper class for common contract operations in tests"""

    def __init__(self, contract, w3, owner):
        self.contract = contract
        self.w3 = w3
        self.owner = owner

    def buffer_transaction(
        self,
        tx_id: bytes,
        origin: str,
        target: str,
        payload: bytes,
        dependency_id: bytes = None,
        timestamp: int = None,
        sender: str = None
    ):
        """Buffer a transaction with defaults"""
        if dependency_id is None:
            dependency_id = b'\x00' * 32
        if timestamp is None:
            timestamp = self.w3.eth.get_block('latest').timestamp + 5
        if sender is None:
            sender = self.owner

        return self.contract.functions.buffer_transaction(
            tx_id, origin, target, payload, dependency_id, timestamp
        ).transact({'from': sender})

    def grant_operator_roles(self, account: str):
        """Grant both BUFFER_ROLE and RESOLVE_ROLE to account"""
        self.contract.functions.grant_role(BUFFER_ROLE, account).transact({'from': self.owner})
        self.contract.functions.grant_role(RESOLVE_ROLE, account).transact({'from': self.owner})

    def mine_blocks(self, count: int):
        """Mine additional blocks (advances time by ~15 seconds per block in eth_tester)"""
        for _ in range(count):
            self.w3.testing.mine()

    def set_timestamp(self, timestamp: int):
        """Set the next block timestamp"""
        self.w3.testing.timeTravel(timestamp)

    def get_transaction_state(self, tx_id: bytes) -> int:
        """Get transaction state (returns enum value)"""
        return self.contract.functions.get_transaction_state(tx_id).call()


@pytest.fixture
def helper(contract, w3, owner):
    """Contract helper instance"""
    return ContractHelper(contract, w3, owner)


@pytest.fixture
def helper_with_operator(contract_with_operator, w3, owner):
    """Contract helper with operator already set up"""
    return ContractHelper(contract_with_operator, w3, owner)


# Transaction state enum values (matching Vyper enum)
class TransactionState:
    EMPTY = 0
    BUFFERED = 1
    READY = 2
    EXECUTED = 3
    FAILED = 4
    EXPIRED = 5


@pytest.fixture
def tx_state():
    """Transaction state enum"""
    return TransactionState


# Role constants as fixtures
@pytest.fixture
def buffer_role():
    return BUFFER_ROLE


@pytest.fixture
def resolve_role():
    return RESOLVE_ROLE


@pytest.fixture
def admin_role():
    return ADMIN_ROLE
