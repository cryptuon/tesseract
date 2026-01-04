# @version ^0.3.10
"""
Tesseract: Cross-Rollup Atomic Transaction Execution System
A secure system for coordinating atomic transactions across multiple rollups

Features:
- Cross-rollup transaction buffering with dependency resolution
- MEV protection via commit-reveal pattern
- Flash loan protection via block delay
- Atomic swap groups for multi-leg coordination
- Refund mechanism for expired transactions
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

event TransactionRevealed:
    tx_id: indexed(bytes32)
    revealed_at: uint256

event TransactionRefunded:
    tx_id: indexed(bytes32)
    recipient: indexed(address)
    refunded_at: uint256

event SwapGroupCreated:
    group_id: indexed(bytes32)
    creator: indexed(address)
    created_at: uint256

event SwapGroupCompleted:
    group_id: indexed(bytes32)
    completed_at: uint256

# Enums
enum TransactionState:
    EMPTY
    BUFFERED
    READY
    EXECUTED
    FAILED
    EXPIRED
    REFUNDED

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
    # DeFi security fields
    commitment_hash: bytes32      # For commit-reveal MEV protection
    reveal_deadline: uint256      # When reveal must happen
    creator: address              # Original transaction creator
    refund_recipient: address     # Where to send refunds
    swap_group_id: bytes32        # Links related swap legs
    creation_block: uint256       # For flash loan protection

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

# DeFi security constants
MIN_RESOLUTION_DELAY: constant(uint256) = 2       # Blocks between buffer and resolve (flash loan protection)
MIN_REVEAL_WINDOW: constant(uint256) = 12         # Minimum blocks for reveal (~2.5 min at 12s)
MAX_REVEAL_WINDOW: constant(uint256) = 100        # Maximum blocks for reveal (~20 min)
MAX_SWAP_GROUP_SIZE: constant(uint256) = 4        # Max legs in an atomic swap

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

# DeFi security state
swap_group_txs: HashMap[bytes32, bytes32[4]]      # group_id -> tx_ids (fixed size array)
swap_group_count: public(HashMap[bytes32, uint256])  # group_id -> number of txs in group
swap_group_ready: HashMap[bytes32, uint256]       # group_id -> number of ready txs
reveals: public(HashMap[bytes32, bool])            # tx_id -> has been revealed

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
        confirmations: 0,
        commitment_hash: empty(bytes32),
        reveal_deadline: 0,
        creator: msg.sender,
        refund_recipient: msg.sender,
        swap_group_id: empty(bytes32),
        creation_block: block.number
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

    # Flash loan protection: must wait minimum blocks after creation
    assert block.number >= buffered_tx.creation_block + MIN_RESOLUTION_DELAY, "Resolution too soon - flash loan protection"

    # If commitment was used, must be revealed first
    if buffered_tx.commitment_hash != empty(bytes32):
        assert self.reveals[tx_id], "Transaction not revealed"

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

        # Update swap group ready count
        if buffered_tx.swap_group_id != empty(bytes32):
            self.swap_group_ready[buffered_tx.swap_group_id] += 1
            # Check if all transactions in swap group are ready
            if self.swap_group_ready[buffered_tx.swap_group_id] == self.swap_group_count[buffered_tx.swap_group_id]:
                log SwapGroupCompleted(buffered_tx.swap_group_id, block.timestamp)

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


# DeFi Security Functions

@external
def buffer_transaction_with_commitment(
    tx_id: bytes32,
    origin_rollup: address,
    target_rollup: address,
    commitment_hash: bytes32,
    dependency_tx_id: bytes32,
    timestamp: uint256,
    swap_group_id: bytes32,
    refund_recipient: address
):
    """
    Buffer a transaction with MEV protection via commit-reveal pattern.

    The actual payload is hidden until reveal_transaction is called.
    This prevents frontrunning by MEV bots.
    """
    self._check_not_paused()
    self._check_circuit_breaker()
    self._check_role(BUFFER_ROLE, msg.sender)
    self._check_rate_limits()

    # Validate inputs
    assert tx_id != empty(bytes32), "Invalid transaction ID"
    assert origin_rollup != empty(address), "Invalid origin rollup"
    assert target_rollup != empty(address), "Invalid target rollup"
    assert origin_rollup != target_rollup, "Origin and target cannot be same"
    assert commitment_hash != empty(bytes32), "Invalid commitment hash"
    assert refund_recipient != empty(address), "Invalid refund recipient"
    assert timestamp >= block.timestamp, "Timestamp cannot be in the past"
    assert timestamp <= block.timestamp + MAX_FUTURE_TIMESTAMP, "Timestamp too far in future"

    # Check transaction doesn't already exist
    assert self.buffered_transactions[tx_id].state == TransactionState.EMPTY, "Transaction already exists"

    # Validate and track swap group
    if swap_group_id != empty(bytes32):
        current_count: uint256 = self.swap_group_count[swap_group_id]
        assert current_count < MAX_SWAP_GROUP_SIZE, "Swap group full"
        self.swap_group_txs[swap_group_id][current_count] = tx_id
        self.swap_group_count[swap_group_id] = current_count + 1

        # Log swap group creation on first transaction
        if current_count == 0:
            log SwapGroupCreated(swap_group_id, msg.sender, block.timestamp)

    # Calculate reveal deadline and expiry
    reveal_deadline: uint256 = block.number + MIN_REVEAL_WINDOW
    expiry: uint256 = timestamp + self.coordination_window

    # Store transaction with empty payload (will be revealed later)
    self.buffered_transactions[tx_id] = BufferedTransaction({
        origin_rollup: origin_rollup,
        target_rollup: target_rollup,
        payload: b"",
        dependency_tx_id: dependency_tx_id,
        timestamp: timestamp,
        state: TransactionState.BUFFERED,
        expiry: expiry,
        confirmations: 0,
        commitment_hash: commitment_hash,
        reveal_deadline: reveal_deadline,
        creator: msg.sender,
        refund_recipient: refund_recipient,
        swap_group_id: swap_group_id,
        creation_block: block.number
    })

    self.transaction_count += 1

    log TransactionBuffered(tx_id, origin_rollup, target_rollup, dependency_tx_id, timestamp)


@external
def reveal_transaction(tx_id: bytes32, payload: Bytes[2048], secret: bytes32):
    """
    Reveal the actual payload for a committed transaction.

    The payload + secret must hash to the original commitment_hash.
    This is the second phase of commit-reveal MEV protection.
    """
    self._check_not_paused()
    self._check_role(BUFFER_ROLE, msg.sender)

    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]

    # Validate state
    assert buffered_tx.state == TransactionState.BUFFERED, "Transaction not buffered"
    assert not self.reveals[tx_id], "Already revealed"
    assert buffered_tx.commitment_hash != empty(bytes32), "No commitment to reveal"

    # Check reveal window
    assert block.number >= buffered_tx.creation_block + 1, "Too early to reveal"
    assert block.number <= buffered_tx.reveal_deadline, "Reveal deadline passed"

    # Verify commitment (payload + secret hashes to stored commitment)
    computed_hash: bytes32 = keccak256(concat(payload, secret))
    assert computed_hash == buffered_tx.commitment_hash, "Invalid reveal - hash mismatch"

    # Validate payload
    assert len(payload) > 0, "Empty payload not allowed"
    assert len(payload) <= self.max_payload_size, "Payload too large"

    # Store revealed payload
    self.buffered_transactions[tx_id].payload = payload
    self.reveals[tx_id] = True

    log TransactionRevealed(tx_id, block.timestamp)


@external
def add_to_swap_group(tx_id: bytes32, swap_group_id: bytes32):
    """
    Add an existing buffered transaction to a swap group.

    This allows linking related transactions for atomic coordination.
    """
    self._check_role(BUFFER_ROLE, msg.sender)

    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]

    # Validate transaction exists and is in correct state
    assert buffered_tx.state == TransactionState.BUFFERED, "Transaction not buffered"
    assert buffered_tx.swap_group_id == empty(bytes32), "Already in a swap group"
    assert swap_group_id != empty(bytes32), "Invalid swap group ID"

    # Check swap group has room
    current_count: uint256 = self.swap_group_count[swap_group_id]
    assert current_count < MAX_SWAP_GROUP_SIZE, "Swap group full"

    # Add to swap group
    self.swap_group_txs[swap_group_id][current_count] = tx_id
    self.swap_group_count[swap_group_id] = current_count + 1
    self.buffered_transactions[tx_id].swap_group_id = swap_group_id

    # Log swap group creation on first transaction
    if current_count == 0:
        log SwapGroupCreated(swap_group_id, msg.sender, block.timestamp)


@external
def claim_refund(tx_id: bytes32):
    """
    Claim a refund for an expired or failed transaction.

    Only the designated refund_recipient can claim.
    Marks transaction as REFUNDED to prevent double claims.
    """
    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]

    # Must be expired or failed
    assert buffered_tx.state == TransactionState.EXPIRED or buffered_tx.state == TransactionState.FAILED, "Not refundable"

    # Only refund recipient can claim
    assert msg.sender == buffered_tx.refund_recipient, "Not refund recipient"

    # Mark as refunded (prevents double claims)
    self.buffered_transactions[tx_id].state = TransactionState.REFUNDED

    log TransactionRefunded(tx_id, msg.sender, block.timestamp)


@external
def expire_swap_group(swap_group_id: bytes32):
    """
    Expire all transactions in a swap group if any has timed out.

    This enables atomic refunds for failed multi-leg swaps.
    """
    self._check_role(RESOLVE_ROLE, msg.sender)

    assert swap_group_id != empty(bytes32), "Invalid swap group ID"
    group_size: uint256 = self.swap_group_count[swap_group_id]
    assert group_size > 0, "Swap group not found"

    # Check if any transaction in group has expired
    any_expired: bool = False
    for i in range(MAX_SWAP_GROUP_SIZE):
        if i >= group_size:
            break
        tx_id: bytes32 = self.swap_group_txs[swap_group_id][i]
        buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
        if block.timestamp > buffered_tx.expiry:
            any_expired = True
            break

    assert any_expired, "No expired transactions in group"

    # Expire all non-executed transactions in the group
    for i in range(MAX_SWAP_GROUP_SIZE):
        if i >= group_size:
            break
        tx_id: bytes32 = self.swap_group_txs[swap_group_id][i]
        buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
        if buffered_tx.state == TransactionState.BUFFERED or buffered_tx.state == TransactionState.READY:
            self.buffered_transactions[tx_id].state = TransactionState.EXPIRED
            self._record_failure(tx_id, "Swap group timeout")


@view
@external
def get_swap_group_status(swap_group_id: bytes32) -> (uint256, uint256, bool):
    """
    Get the status of a swap group.

    Returns: (total_count, ready_count, all_ready)
    """
    total: uint256 = self.swap_group_count[swap_group_id]
    ready: uint256 = self.swap_group_ready[swap_group_id]
    all_ready: bool = (total > 0) and (ready == total)
    return (total, ready, all_ready)


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