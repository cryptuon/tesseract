# @version ^0.3.10
"""
Tesseract: Cross-Rollup Atomic Transaction Execution System
A secure system for coordinating atomic transactions across multiple rollups
"""

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
    payload: bytes[1024]  # Fixed: lowercase bytes
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
MAX_PAYLOAD_SIZE: constant(uint256) = 1024  # Reduced for testing
DEFAULT_COORDINATION_WINDOW: constant(uint256) = 30

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

# Configuration
coordination_window: public(uint256)

@external
def __init__():
    """Initialize the contract with default settings."""
    self.owner = msg.sender
    self.emergency_admin = msg.sender
    self.coordination_window = DEFAULT_COORDINATION_WINDOW

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
    payload: bytes[1024],
    dependency_tx_id: bytes32,
    timestamp: uint256
):
    """Buffer a new cross-rollup transaction."""
    self._check_not_paused()
    self._check_role(BUFFER_ROLE, msg.sender)

    # Validate inputs
    assert tx_id != empty(bytes32), "Invalid transaction ID"
    assert origin_rollup != empty(address), "Invalid origin rollup"
    assert target_rollup != empty(address), "Invalid target rollup"
    assert origin_rollup != target_rollup, "Origin and target cannot be same"
    assert len(payload) > 0, "Empty payload not allowed"
    assert timestamp >= block.timestamp, "Timestamp cannot be in the past"

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
    self._check_role(RESOLVE_ROLE, msg.sender)

    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]

    # Validate transaction exists and is in correct state
    assert buffered_tx.state == TransactionState.BUFFERED, "Transaction not in buffered state"

    # Check if transaction has expired
    assert block.timestamp <= buffered_tx.expiry, "Transaction expired"

    # Check dependency resolution
    dependency_resolved: bool = True
    if buffered_tx.dependency_tx_id != empty(bytes32):
        dependency_tx: BufferedTransaction = self.buffered_transactions[buffered_tx.dependency_tx_id]
        dependency_resolved = (dependency_tx.state == TransactionState.READY) or (dependency_tx.state == TransactionState.EXECUTED)

    # Check timing constraints
    timing_valid: bool = block.timestamp >= buffered_tx.timestamp

    if dependency_resolved and timing_valid:
        self.buffered_transactions[tx_id].state = TransactionState.READY
        log TransactionReady(tx_id, block.timestamp)
    else:
        reason: String[256] = "Dependencies not satisfied"
        log TransactionFailed(tx_id, reason, block.timestamp)
        raise reason

@view
@external
def is_transaction_ready(tx_id: bytes32) -> bool:
    """Check if a buffered transaction is ready for execution."""
    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
    return (buffered_tx.state == TransactionState.READY) and (block.timestamp >= buffered_tx.timestamp)

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

# Emergency Functions
@external
def emergency_pause():
    """Pause all contract operations."""
    assert (msg.sender == self.emergency_admin) or (msg.sender == self.owner), "Not authorized"
    self.paused = True
    log EmergencyPause(msg.sender, block.timestamp)

@external
def emergency_unpause():
    """Unpause contract operations."""
    self._check_owner()
    self.paused = False
    log EmergencyUnpause(msg.sender, block.timestamp)

# Configuration Functions
@external
def set_coordination_window(window: uint256):
    """Set the coordination window duration."""
    self._check_owner()
    assert window >= 5, "Window too short"
    assert window <= 300, "Window too long"
    self.coordination_window = window

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