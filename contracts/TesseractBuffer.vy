# @version ^0.3.10
"""
Tesseract: Cross-Rollup Atomic Transaction Execution System
A secure system for coordinating atomic transactions across multiple rollups
"""

from vyper.interfaces import ERC20

# Events
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    dependency_tx_id: bytes32
    timestamp: uint256

event TransactionReady:
    tx_id: indexed(bytes32)
    resolved_at: uint256

event TransactionFailed:
    tx_id: indexed(bytes32)
    reason: String[256]
    failed_at: uint256

event EmergencyPause:
    caller: indexed(address)
    paused_at: uint256

event EmergencyUnpause:
    caller: indexed(address)
    unpaused_at: uint256

event RoleGranted:
    role: indexed(bytes32)
    account: indexed(address)
    sender: indexed(address)

event RoleRevoked:
    role: indexed(bytes32)
    account: indexed(address)
    sender: indexed(address)

# Enums
enum TransactionState:
    EMPTY
    BUFFERED
    READY
    EXECUTED
    FAILED
    EXPIRED

# Structs
struct BufferedTransaction:
    origin_rollup: address
    target_rollup: address
    payload: Bytes[2048]
    dependency_tx_id: bytes32
    timestamp: uint256
    state: TransactionState
    expiry: uint256
    confirmations: uint256

# Constants
BUFFER_ROLE: constant(bytes32) = keccak256("BUFFER_ROLE")
RESOLVE_ROLE: constant(bytes32) = keccak256("RESOLVE_ROLE")
ADMIN_ROLE: constant(bytes32) = keccak256("ADMIN_ROLE")

MAX_TRANSACTIONS_PER_BLOCK: constant(uint256) = 100
MAX_USER_TRANSACTIONS_PER_BLOCK: constant(uint256) = 10
MAX_PAYLOAD_SIZE: constant(uint256) = 2048
MAX_FUTURE_TIMESTAMP: constant(uint256) = 86400  # 24 hours
DEFAULT_COORDINATION_WINDOW: constant(uint256) = 30  # 30 seconds
RESET_COOLDOWN: constant(uint256) = 3600  # 1 hour

# State variables
owner: public(address)
emergency_admin: public(address)
paused: public(bool)

# Role-based access control
roles: HashMap[bytes32, HashMap[address, bool]]

# Transaction storage
buffered_transactions: public(HashMap[bytes32, BufferedTransaction])
transaction_count: public(uint256)

# Rate limiting
transactions_per_block: HashMap[uint256, uint256]
user_transactions_per_block: HashMap[address, HashMap[uint256, uint256]]

# Circuit breaker
failed_transactions: uint256
circuit_breaker_threshold: public(uint256)
circuit_breaker_active: public(bool)
last_reset_time: uint256

# Transaction processing locks
transaction_lock: HashMap[bytes32, bool]

# Configuration
coordination_window: public(uint256)
max_payload_size: public(uint256)

@external
def __init__():
    """Initialize the contract with default settings."""
    self.owner = msg.sender
    self.emergency_admin = msg.sender
    self.coordination_window = DEFAULT_COORDINATION_WINDOW
    self.max_payload_size = MAX_PAYLOAD_SIZE
    self.circuit_breaker_threshold = 50
    self.last_reset_time = block.timestamp

    # Grant admin role to deployer
    self.roles[ADMIN_ROLE][msg.sender] = True
    log RoleGranted(ADMIN_ROLE, msg.sender, msg.sender)

# Access Control Functions
@internal
def _check_role(role: bytes32, account: address):
    """Check if account has the specified role."""
    assert self.roles[role][account], "AccessControl: account missing role"

@internal
def _check_owner():
    """Check if caller is the contract owner."""
    assert msg.sender == self.owner, "AccessControl: caller is not owner"

@internal
def _check_not_paused():
    """Check if contract is not paused."""
    assert not self.paused, "Contract is paused"

@internal
def _check_circuit_breaker():
    """Check if circuit breaker is not active."""
    assert not self.circuit_breaker_active, "Circuit breaker active"

@internal
def _check_rate_limits():
    """Check if rate limits are not exceeded."""
    current_block: uint256 = block.number

    # Global rate limit
    assert self.transactions_per_block[current_block] < MAX_TRANSACTIONS_PER_BLOCK, "Block transaction limit exceeded"

    # Per-user rate limit
    assert self.user_transactions_per_block[msg.sender][current_block] < MAX_USER_TRANSACTIONS_PER_BLOCK, "User transaction limit exceeded"

    # Update counters
    self.transactions_per_block[current_block] += 1
    self.user_transactions_per_block[msg.sender][current_block] += 1

@internal
def _record_failure(tx_id: bytes32, reason: String[256]):
    """Record a transaction failure and check circuit breaker."""
    self.failed_transactions += 1
    log TransactionFailed(tx_id, reason, block.timestamp)

    if self.failed_transactions >= self.circuit_breaker_threshold:
        self.circuit_breaker_active = True

@external
def grant_role(role: bytes32, account: address):
    """Grant a role to an account."""
    self._check_owner()
    self.roles[role][account] = True
    log RoleGranted(role, account, msg.sender)

@external
def revoke_role(role: bytes32, account: address):
    """Revoke a role from an account."""
    self._check_owner()
    self.roles[role][account] = False
    log RoleRevoked(role, account, msg.sender)

@view
@external
def has_role(role: bytes32, account: address) -> bool:
    """Check if an account has a specific role."""
    return self.roles[role][account]

# Main Transaction Functions
@external
def buffer_transaction(
    tx_id: bytes32,
    origin_rollup: address,
    target_rollup: address,
    payload: Bytes[2048],
    dependency_tx_id: bytes32,
    timestamp: uint256
):
    """Buffer a new cross-rollup transaction."""
    self._check_not_paused()
    self._check_circuit_breaker()
    self._check_role(BUFFER_ROLE, msg.sender)
    self._check_rate_limits()

    # Validate inputs
    assert tx_id != empty(bytes32), "Invalid transaction ID"
    assert origin_rollup != empty(address), "Invalid origin rollup"
    assert target_rollup != empty(address), "Invalid target rollup"
    assert origin_rollup != target_rollup, "Origin and target cannot be same"
    assert len(payload) > 0, "Empty payload not allowed"
    assert len(payload) <= self.max_payload_size, "Payload too large"
    assert timestamp >= block.timestamp, "Timestamp cannot be in the past"
    assert timestamp <= block.timestamp + MAX_FUTURE_TIMESTAMP, "Timestamp too far in future"

    # Check transaction doesn't already exist
    assert self.buffered_transactions[tx_id].state == TransactionState.EMPTY, "Transaction already exists"

    # Calculate expiry time
    expiry: uint256 = timestamp + self.coordination_window

    # Store transaction
    self.buffered_transactions[tx_id] = BufferedTransaction({
        origin_rollup: origin_rollup,
        target_rollup: target_rollup,
        payload: payload,
        dependency_tx_id: dependency_tx_id,
        timestamp: timestamp,
        state: TransactionState.BUFFERED,
        expiry: expiry,
        confirmations: 0
    })

    self.transaction_count += 1

    log TransactionBuffered(tx_id, origin_rollup, target_rollup, dependency_tx_id, timestamp)

@external
def resolve_dependency(tx_id: bytes32):
    """Resolve dependencies for a buffered transaction."""
    self._check_not_paused()
    self._check_circuit_breaker()
    self._check_role(RESOLVE_ROLE, msg.sender)

    # Check not already processing
    assert not self.transaction_lock[tx_id], "Transaction being processed"

    # Set processing lock
    self.transaction_lock[tx_id] = True

    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]

    # Validate transaction exists and is in correct state
    if buffered_tx.state == TransactionState.EMPTY:
        self.transaction_lock[tx_id] = False
        self._record_failure(tx_id, "Transaction does not exist")
        raise "Transaction does not exist"

    if buffered_tx.state != TransactionState.BUFFERED:
        self.transaction_lock[tx_id] = False
        self._record_failure(tx_id, "Transaction not in buffered state")
        raise "Transaction not in buffered state"

    # Check if transaction has expired
    if block.timestamp > buffered_tx.expiry:
        self.buffered_transactions[tx_id].state = TransactionState.EXPIRED
        self.transaction_lock[tx_id] = False
        self._record_failure(tx_id, "Transaction expired")
        raise "Transaction expired"

    # Check dependency resolution
    dependency_resolved: bool = True
    if buffered_tx.dependency_tx_id != empty(bytes32):
        dependency_tx: BufferedTransaction = self.buffered_transactions[buffered_tx.dependency_tx_id]
        dependency_resolved = dependency_tx.state == TransactionState.READY or dependency_tx.state == TransactionState.EXECUTED

    # Check timing constraints
    timing_valid: bool = block.timestamp >= buffered_tx.timestamp

    if dependency_resolved and timing_valid:
        self.buffered_transactions[tx_id].state = TransactionState.READY
        self.transaction_lock[tx_id] = False
        log TransactionReady(tx_id, block.timestamp)
    else:
        self.transaction_lock[tx_id] = False
        reason: String[256] = "Dependencies not satisfied or timing invalid"
        self._record_failure(tx_id, reason)
        raise reason

@view
@external
def is_transaction_ready(tx_id: bytes32) -> bool:
    """Check if a buffered transaction is ready for execution."""
    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
    return buffered_tx.state == TransactionState.READY and block.timestamp >= buffered_tx.timestamp

@view
@external
def get_transaction(tx_id: bytes32) -> BufferedTransaction:
    """Get full transaction details."""
    return self.buffered_transactions[tx_id]

@view
@external
def get_transaction_state(tx_id: bytes32) -> TransactionState:
    """Get transaction state."""
    return self.buffered_transactions[tx_id].state

@external
def mark_transaction_executed(tx_id: bytes32):
    """Mark a transaction as executed."""
    self._check_role(RESOLVE_ROLE, msg.sender)

    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
    assert buffered_tx.state == TransactionState.READY, "Transaction not ready"

    self.buffered_transactions[tx_id].state = TransactionState.EXECUTED

# Emergency Functions
@external
def emergency_pause():
    """Pause all contract operations."""
    assert msg.sender == self.emergency_admin or msg.sender == self.owner, "Not authorized"
    self.paused = True
    log EmergencyPause(msg.sender, block.timestamp)

@external
def emergency_unpause():
    """Unpause contract operations."""
    self._check_owner()
    self.paused = False
    log EmergencyUnpause(msg.sender, block.timestamp)

@external
def reset_circuit_breaker():
    """Reset the circuit breaker after cooldown period."""
    self._check_owner()
    assert block.timestamp >= self.last_reset_time + RESET_COOLDOWN, "Cooldown not elapsed"

    self.circuit_breaker_active = False
    self.failed_transactions = 0
    self.last_reset_time = block.timestamp

# Configuration Functions
@external
def set_coordination_window(window: uint256):
    """Set the coordination window duration."""
    self._check_owner()
    assert window >= 5, "Window too short"
    assert window <= 300, "Window too long"
    self.coordination_window = window

@external
def set_max_payload_size(size: uint256):
    """Set maximum payload size."""
    self._check_owner()
    assert size >= 32, "Size too small"
    assert size <= MAX_PAYLOAD_SIZE, "Size too large"
    self.max_payload_size = size

@external
def set_circuit_breaker_threshold(threshold: uint256):
    """Set circuit breaker threshold."""
    self._check_owner()
    assert threshold >= 10, "Threshold too low"
    self.circuit_breaker_threshold = threshold

@external
def set_emergency_admin(admin: address):
    """Set emergency admin address."""
    self._check_owner()
    assert admin != empty(address), "Invalid admin address"
    self.emergency_admin = admin

@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    self._check_owner()
    assert new_owner != empty(address), "Invalid owner address"
    self.owner = new_owner