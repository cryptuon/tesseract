# @version ^0.3.10
"""
Tesseract: Simple Cross-Rollup Transaction Buffer
A minimal implementation for testing and development
"""

# Events
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    timestamp: uint256

event TransactionReady:
    tx_id: indexed(bytes32)

event TransactionFailed:
    tx_id: indexed(bytes32)
    reason: String[100]

# Transaction states
enum State:
    EMPTY
    BUFFERED
    READY
    EXECUTED

# Transaction structure
struct Transaction:
    origin_rollup: address
    target_rollup: address
    payload: Bytes[512]
    dependency_tx_id: bytes32
    timestamp: uint256
    state: State

# Storage
owner: public(address)
authorized_operators: public(HashMap[address, bool])
transactions: public(HashMap[bytes32, Transaction])
transaction_count: public(uint256)

# Configuration
coordination_window: public(uint256)

@external
def __init__():
    """Initialize the contract"""
    self.owner = msg.sender
    self.coordination_window = 30  # 30 seconds
    self.authorized_operators[msg.sender] = True

@external
def add_operator(operator: address):
    """Add an authorized operator"""
    assert msg.sender == self.owner, "Only owner can add operators"
    self.authorized_operators[operator] = True

@external
def remove_operator(operator: address):
    """Remove an authorized operator"""
    assert msg.sender == self.owner, "Only owner can remove operators"
    self.authorized_operators[operator] = False

@external
def buffer_transaction(
    tx_id: bytes32,
    origin_rollup: address,
    target_rollup: address,
    payload: Bytes[512],
    dependency_tx_id: bytes32,
    timestamp: uint256
):
    """Buffer a new transaction"""
    # Access control
    assert self.authorized_operators[msg.sender], "Not authorized"

    # Validation
    assert tx_id != empty(bytes32), "Invalid transaction ID"
    assert origin_rollup != empty(address), "Invalid origin rollup"
    assert target_rollup != empty(address), "Invalid target rollup"
    assert origin_rollup != target_rollup, "Origin and target must be different"
    assert timestamp >= block.timestamp, "Timestamp cannot be in the past"
    assert self.transactions[tx_id].state == State.EMPTY, "Transaction already exists"

    # Store transaction
    self.transactions[tx_id] = Transaction({
        origin_rollup: origin_rollup,
        target_rollup: target_rollup,
        payload: payload,
        dependency_tx_id: dependency_tx_id,
        timestamp: timestamp,
        state: State.BUFFERED
    })

    self.transaction_count += 1

    log TransactionBuffered(tx_id, origin_rollup, target_rollup, timestamp)

@external
def resolve_dependency(tx_id: bytes32):
    """Resolve dependencies for a transaction"""
    assert self.authorized_operators[msg.sender], "Not authorized"

    transaction: Transaction = self.transactions[tx_id]  # Fixed: renamed from tx
    assert transaction.state == State.BUFFERED, "Transaction not in buffered state"

    # Check if expired
    if block.timestamp > transaction.timestamp + self.coordination_window:
        log TransactionFailed(tx_id, "Transaction expired")
        return

    # Check dependency
    dependency_ready: bool = True
    if transaction.dependency_tx_id != empty(bytes32):
        dep_transaction: Transaction = self.transactions[transaction.dependency_tx_id]
        dependency_ready = dep_transaction.state == State.READY or dep_transaction.state == State.EXECUTED

    # Check timing
    timing_ok: bool = block.timestamp >= transaction.timestamp

    if dependency_ready and timing_ok:
        self.transactions[tx_id].state = State.READY
        log TransactionReady(tx_id)
    else:
        log TransactionFailed(tx_id, "Dependencies not satisfied")

@view
@external
def is_transaction_ready(tx_id: bytes32) -> bool:
    """Check if a transaction is ready"""
    transaction: Transaction = self.transactions[tx_id]  # Fixed: renamed from tx
    return transaction.state == State.READY and block.timestamp >= transaction.timestamp

@view
@external
def get_transaction_state(tx_id: bytes32) -> State:
    """Get transaction state"""
    return self.transactions[tx_id].state

@view
@external
def get_transaction_details(tx_id: bytes32) -> (address, address, bytes32, uint256, State):
    """Get transaction details as tuple"""
    transaction: Transaction = self.transactions[tx_id]  # Fixed: renamed from tx
    return (transaction.origin_rollup, transaction.target_rollup, transaction.dependency_tx_id, transaction.timestamp, transaction.state)

@external
def mark_executed(tx_id: bytes32):
    """Mark a transaction as executed"""
    assert self.authorized_operators[msg.sender], "Not authorized"

    transaction: Transaction = self.transactions[tx_id]  # Fixed: renamed from tx
    assert transaction.state == State.READY, "Transaction not ready"

    self.transactions[tx_id].state = State.EXECUTED

@external
def set_coordination_window(window: uint256):
    """Set coordination window"""
    assert msg.sender == self.owner, "Only owner can set window"
    assert window >= 5 and window <= 300, "Window must be between 5 and 300 seconds"
    self.coordination_window = window