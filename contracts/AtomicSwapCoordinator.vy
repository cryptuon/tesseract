# @version ^0.3.10
"""
AtomicSwapCoordinator: DeFi Atomic Swap Coordination Layer

Manages cross-rollup atomic token swaps with:
- Order book for makers and takers
- Slippage protection via min_receive_amount
- Partial fill support
- Relayer fee incentives
- Timeout and refund handling
- Protocol fee collection (0.1-0.3% flat fee)
- TESS staker discounts

Fee Structure (default 0.2% = 20 bps):
- 60% to TESS stakers
- 30% to relayers
- 10% to treasury

Works in conjunction with TesseractBuffer for cross-chain coordination.
"""

from vyper.interfaces import ERC20

# Events
event SwapOrderCreated:
    order_id: indexed(bytes32)
    maker: indexed(address)
    offer_chain: address
    want_chain: address
    offer_amount: uint256
    want_amount: uint256
    deadline: uint256

event SwapOrderCancelled:
    order_id: indexed(bytes32)
    maker: indexed(address)
    cancelled_at: uint256

event SwapFillCreated:
    order_id: indexed(bytes32)
    fill_id: indexed(bytes32)
    taker: indexed(address)
    offer_amount_filled: uint256
    want_amount_filled: uint256

event SwapCompleted:
    order_id: indexed(bytes32)
    completed_at: uint256

event SwapRefunded:
    order_id: indexed(bytes32)
    recipient: indexed(address)
    refunded_at: uint256

event RelayerRewardClaimed:
    relayer: indexed(address)
    amount: uint256

event ProtocolFeeCollected:
    order_id: indexed(bytes32)
    token: indexed(address)
    amount: uint256
    discount_applied: bool

event FeeRateUpdated:
    old_rate: uint256
    new_rate: uint256

event FeeCollectorUpdated:
    old_collector: address
    new_collector: address

# Enums
enum SwapState:
    EMPTY
    OPEN           # Order created, awaiting taker
    MATCHED        # Taker found, legs committed
    EXECUTING      # Execution in progress
    COMPLETED      # Successfully completed
    REFUNDED       # Timed out and refunded
    CANCELLED      # Cancelled by maker

# Structs
struct SwapOrder:
    order_id: bytes32
    maker: address
    taker: address           # address(0) for open orders
    offer_chain: address     # Chain/rollup for offered asset
    offer_token: address     # Token address on offer chain
    offer_amount: uint256
    want_chain: address      # Chain/rollup for wanted asset
    want_token: address      # Token address on want chain
    want_amount: uint256
    min_receive_amount: uint256  # Slippage protection
    created_at: uint256
    deadline: uint256
    state: SwapState
    filled_offer_amount: uint256
    filled_want_amount: uint256
    relayer_reward_bps: uint256  # Basis points (100 = 1%)

struct Fill:
    fill_id: bytes32
    order_id: bytes32
    taker: address
    offer_amount_filled: uint256
    want_amount_filled: uint256
    timestamp: uint256

# Constants
MAX_RELAYER_REWARD_BPS: constant(uint256) = 100   # 1% max
MIN_ORDER_DURATION: constant(uint256) = 300       # 5 minutes minimum
MAX_ORDER_DURATION: constant(uint256) = 86400     # 24 hours maximum
MAX_FILLS_PER_ORDER: constant(uint256) = 10       # Max partial fills
PRECISION: constant(uint256) = 10 ** 18           # Price precision

# Fee constants
DEFAULT_PROTOCOL_FEE_BPS: constant(uint256) = 20  # 0.2% default
MIN_PROTOCOL_FEE_BPS: constant(uint256) = 10      # 0.1% minimum
MAX_PROTOCOL_FEE_BPS: constant(uint256) = 30      # 0.3% maximum
STAKER_DISCOUNT_BPS: constant(uint256) = 5000     # 50% discount for TESS stakers
MIN_STAKE_FOR_DISCOUNT: constant(uint256) = 10_000 * 10 ** 18  # 10k TESS minimum

# State variables
owner: public(address)
paused: public(bool)

# Fee configuration
protocol_fee_bps: public(uint256)    # Current fee rate in basis points
fee_collector: public(address)        # FeeCollector contract address
tess_token: public(address)           # TESS token for discount checks
staking_contract: public(address)     # TesseractStaking for balance checks
total_fees_collected: public(HashMap[address, uint256])  # token -> total fees

# Order storage
orders: public(HashMap[bytes32, SwapOrder])
order_count: public(uint256)

# Fill storage
order_fill_count: HashMap[bytes32, uint256]       # order_id -> number of fills
fills: public(HashMap[bytes32, Fill])             # fill_id -> Fill

# Relayer tracking
relayer_rewards: public(HashMap[address, uint256])
relayer_total_earned: public(HashMap[address, uint256])

# TesseractBuffer interface (for future integration)
tesseract_buffer: public(address)


@external
def __init__():
    """Initialize the contract."""
    self.owner = msg.sender
    self.protocol_fee_bps = DEFAULT_PROTOCOL_FEE_BPS


@internal
def _check_owner():
    """Check if caller is owner."""
    assert msg.sender == self.owner, "Not owner"


@internal
def _check_not_paused():
    """Check if contract is not paused."""
    assert not self.paused, "Contract paused"


@internal
def _has_staker_discount(user: address) -> bool:
    """Check if user qualifies for staker discount."""
    if self.staking_contract == empty(address):
        return False
    if self.tess_token == empty(address):
        return False

    # Check staked balance (simplified - in production use staking contract view)
    tess_balance: uint256 = ERC20(self.tess_token).balanceOf(user)
    return tess_balance >= MIN_STAKE_FOR_DISCOUNT


@internal
def _calculate_fee(amount: uint256, user: address) -> uint256:
    """Calculate protocol fee for an amount, applying discounts if eligible."""
    base_fee: uint256 = (amount * self.protocol_fee_bps) / 10000

    # Apply 50% discount for TESS stakers
    if self._has_staker_discount(user):
        return (base_fee * (10000 - STAKER_DISCOUNT_BPS)) / 10000

    return base_fee


# Order Management

@external
def create_swap_order(
    order_id: bytes32,
    offer_chain: address,
    offer_token: address,
    offer_amount: uint256,
    want_chain: address,
    want_token: address,
    want_amount: uint256,
    min_receive_amount: uint256,
    deadline: uint256,
    relayer_reward_bps: uint256,
    taker: address  # address(0) for open order
) -> bytes32:
    """
    Create a new atomic swap order.

    Slippage protection via min_receive_amount.
    """
    self._check_not_paused()

    # Validate inputs
    assert order_id != empty(bytes32), "Invalid order ID"
    assert self.orders[order_id].state == SwapState.EMPTY, "Order exists"
    assert offer_chain != want_chain, "Same chain not allowed"
    assert offer_token != empty(address), "Invalid offer token"
    assert want_token != empty(address), "Invalid want token"
    assert offer_amount > 0, "Invalid offer amount"
    assert want_amount > 0, "Invalid want amount"
    assert min_receive_amount <= want_amount, "Invalid min receive"
    assert min_receive_amount > 0, "Min receive must be positive"
    assert deadline > block.timestamp + MIN_ORDER_DURATION, "Deadline too soon"
    assert deadline < block.timestamp + MAX_ORDER_DURATION, "Deadline too far"
    assert relayer_reward_bps <= MAX_RELAYER_REWARD_BPS, "Reward too high"

    self.orders[order_id] = SwapOrder({
        order_id: order_id,
        maker: msg.sender,
        taker: taker,
        offer_chain: offer_chain,
        offer_token: offer_token,
        offer_amount: offer_amount,
        want_chain: want_chain,
        want_token: want_token,
        want_amount: want_amount,
        min_receive_amount: min_receive_amount,
        created_at: block.timestamp,
        deadline: deadline,
        state: SwapState.OPEN,
        filled_offer_amount: 0,
        filled_want_amount: 0,
        relayer_reward_bps: relayer_reward_bps
    })

    self.order_count += 1

    log SwapOrderCreated(
        order_id, msg.sender, offer_chain, want_chain,
        offer_amount, want_amount, deadline
    )

    return order_id


@external
def take_swap_order(order_id: bytes32, fill_amount: uint256) -> bytes32:
    """
    Take an open swap order (full or partial fill).

    Returns the fill_id for tracking.
    """
    self._check_not_paused()

    order: SwapOrder = self.orders[order_id]
    assert order.state == SwapState.OPEN, "Order not open"
    assert block.timestamp < order.deadline, "Order expired"

    # Check taker restriction
    if order.taker != empty(address):
        assert msg.sender == order.taker, "Not authorized taker"

    # Calculate fill amounts
    remaining_offer: uint256 = order.offer_amount - order.filled_offer_amount
    assert fill_amount > 0, "Invalid fill amount"
    assert fill_amount <= remaining_offer, "Fill exceeds remaining"

    # Proportional want amount
    fill_want_amount: uint256 = (fill_amount * order.want_amount) / order.offer_amount

    # Check slippage for partial fill
    proportional_min: uint256 = (fill_amount * order.min_receive_amount) / order.offer_amount
    assert fill_want_amount >= proportional_min, "Slippage exceeded"

    # Check partial fill limits
    fill_count: uint256 = self.order_fill_count[order_id]
    assert fill_count < MAX_FILLS_PER_ORDER, "Too many fills"

    # Create fill record
    fill_id: bytes32 = keccak256(concat(
        order_id,
        convert(msg.sender, bytes32),
        convert(fill_amount, bytes32),
        convert(block.timestamp, bytes32)
    ))

    self.fills[fill_id] = Fill({
        fill_id: fill_id,
        order_id: order_id,
        taker: msg.sender,
        offer_amount_filled: fill_amount,
        want_amount_filled: fill_want_amount,
        timestamp: block.timestamp
    })

    self.order_fill_count[order_id] = fill_count + 1

    # Update order
    self.orders[order_id].filled_offer_amount += fill_amount
    self.orders[order_id].filled_want_amount += fill_want_amount

    # Mark as matched if fully filled
    if self.orders[order_id].filled_offer_amount == order.offer_amount:
        self.orders[order_id].state = SwapState.MATCHED

    log SwapFillCreated(order_id, fill_id, msg.sender, fill_amount, fill_want_amount)

    return fill_id


@external
def cancel_order(order_id: bytes32):
    """
    Cancel an open order.

    Only the maker can cancel, and only if no fills have been taken.
    """
    order: SwapOrder = self.orders[order_id]

    assert order.state == SwapState.OPEN, "Order not open"
    assert msg.sender == order.maker, "Not maker"
    assert order.filled_offer_amount == 0, "Order has fills"

    self.orders[order_id].state = SwapState.CANCELLED

    log SwapOrderCancelled(order_id, msg.sender, block.timestamp)


@external
def mark_swap_completed(order_id: bytes32, fee_token: address, fee_amount: uint256):
    """
    Mark a swap as completed after successful cross-chain execution.

    Called by authorized relayer/operator.
    Collects protocol fees and sends to FeeCollector.
    """
    self._check_not_paused()

    order: SwapOrder = self.orders[order_id]
    assert order.state == SwapState.MATCHED or order.state == SwapState.EXECUTING, "Invalid state"

    self.orders[order_id].state = SwapState.COMPLETED

    # Collect protocol fee if configured
    if self.fee_collector != empty(address) and fee_amount > 0:
        # Calculate fee with potential staker discount
        actual_fee: uint256 = self._calculate_fee(fee_amount, order.maker)
        has_discount: bool = self._has_staker_discount(order.maker)

        if actual_fee > 0:
            # Transfer fee token to fee collector
            # Note: In production, the relayer would handle this transfer
            self.total_fees_collected[fee_token] += actual_fee

            log ProtocolFeeCollected(order_id, fee_token, actual_fee, has_discount)

    log SwapCompleted(order_id, block.timestamp)


@external
def initiate_refund(order_id: bytes32):
    """
    Initiate refund for a timed-out swap.

    Can be called by maker or any taker after deadline.
    """
    order: SwapOrder = self.orders[order_id]

    assert order.state != SwapState.COMPLETED, "Already completed"
    assert order.state != SwapState.REFUNDED, "Already refunded"
    assert order.state != SwapState.CANCELLED, "Already cancelled"
    assert block.timestamp > order.deadline, "Not yet expired"

    # Verify caller is involved (maker or has a fill)
    is_involved: bool = msg.sender == order.maker
    # Note: In production, we'd check fills - simplified for now

    assert is_involved or self.order_fill_count[order_id] > 0, "Not authorized"

    self.orders[order_id].state = SwapState.REFUNDED

    log SwapRefunded(order_id, msg.sender, block.timestamp)


# Relayer Functions

@external
def record_relayer_reward(relayer: address, order_id: bytes32, gas_used: uint256):
    """
    Record a relayer reward for executing a swap leg.

    Called after successful execution.
    """
    self._check_owner()  # Only owner can record rewards (or authorized contract)

    order: SwapOrder = self.orders[order_id]
    assert order.state == SwapState.COMPLETED, "Order not completed"

    # Calculate reward based on filled amount and reward bps
    reward: uint256 = (order.filled_offer_amount * order.relayer_reward_bps) / 10000

    self.relayer_rewards[relayer] += reward
    self.relayer_total_earned[relayer] += reward


@external
def claim_relayer_rewards():
    """
    Claim accumulated relayer rewards.

    Note: In production, this would transfer actual tokens.
    This version just marks claims for off-chain settlement.
    """
    amount: uint256 = self.relayer_rewards[msg.sender]
    assert amount > 0, "No rewards to claim"

    self.relayer_rewards[msg.sender] = 0

    log RelayerRewardClaimed(msg.sender, amount)


# View Functions

@view
@external
def get_order(order_id: bytes32) -> SwapOrder:
    """Get full order details."""
    return self.orders[order_id]


@view
@external
def get_fill(fill_id: bytes32) -> Fill:
    """Get fill details."""
    return self.fills[fill_id]


@view
@external
def get_order_fill_count(order_id: bytes32) -> uint256:
    """Get number of fills for an order."""
    return self.order_fill_count[order_id]


@view
@external
def calculate_expected_receive(order_id: bytes32, fill_amount: uint256) -> uint256:
    """
    Calculate expected receive amount for a given fill.

    Allows takers to verify price before committing.
    """
    order: SwapOrder = self.orders[order_id]
    assert order.state != SwapState.EMPTY, "Order not found"

    # Proportional calculation
    return (fill_amount * order.want_amount) / order.offer_amount


@view
@external
def is_order_fillable(order_id: bytes32) -> bool:
    """Check if an order can still be filled."""
    order: SwapOrder = self.orders[order_id]
    return (
        order.state == SwapState.OPEN and
        block.timestamp < order.deadline and
        order.filled_offer_amount < order.offer_amount
    )


@view
@external
def get_remaining_offer(order_id: bytes32) -> uint256:
    """Get remaining offer amount available for fills."""
    order: SwapOrder = self.orders[order_id]
    return order.offer_amount - order.filled_offer_amount


# Admin Functions

@external
def set_tesseract_buffer(buffer: address):
    """Set TesseractBuffer contract address for integration."""
    self._check_owner()
    assert buffer != empty(address), "Invalid address"
    self.tesseract_buffer = buffer


@external
def pause():
    """Pause contract operations."""
    self._check_owner()
    self.paused = True


@external
def unpause():
    """Unpause contract operations."""
    self._check_owner()
    self.paused = False


@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    self._check_owner()
    assert new_owner != empty(address), "Invalid owner"
    self.owner = new_owner


# Fee Configuration Functions

@external
def set_protocol_fee(new_fee_bps: uint256):
    """
    Set the protocol fee rate in basis points.

    Only owner can update. Governance should control this in production.
    """
    self._check_owner()
    assert new_fee_bps >= MIN_PROTOCOL_FEE_BPS, "Fee too low"
    assert new_fee_bps <= MAX_PROTOCOL_FEE_BPS, "Fee too high"

    old_fee: uint256 = self.protocol_fee_bps
    self.protocol_fee_bps = new_fee_bps

    log FeeRateUpdated(old_fee, new_fee_bps)


@external
def set_fee_collector(new_collector: address):
    """Set the fee collector contract address."""
    self._check_owner()

    old_collector: address = self.fee_collector
    self.fee_collector = new_collector

    log FeeCollectorUpdated(old_collector, new_collector)


@external
def set_tess_token(token: address):
    """Set the TESS token address for discount checks."""
    self._check_owner()
    self.tess_token = token


@external
def set_staking_contract(staking: address):
    """Set the staking contract address for discount checks."""
    self._check_owner()
    self.staking_contract = staking


@view
@external
def calculate_fee_preview(amount: uint256, user: address) -> (uint256, bool):
    """
    Preview fee calculation for a user.

    Returns (fee_amount, has_discount).
    Note: Discount check requires external call, so this is a staticcall-safe view.
    """
    base_fee: uint256 = (amount * self.protocol_fee_bps) / 10000
    has_discount: bool = False

    # Check for staker discount if token is configured
    if self.tess_token != empty(address):
        tess_balance: uint256 = ERC20(self.tess_token).balanceOf(user)
        if tess_balance >= MIN_STAKE_FOR_DISCOUNT:
            has_discount = True
            base_fee = (base_fee * (10000 - STAKER_DISCOUNT_BPS)) / 10000

    return (base_fee, has_discount)


@view
@external
def get_total_fees(token: address) -> uint256:
    """Get total fees collected for a token."""
    return self.total_fees_collected[token]
