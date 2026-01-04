# @version ^0.3.10
"""
TesseractStaking: Stake TESS to earn protocol fees

Features:
- Stake TESS tokens to receive stTESS (staked TESS)
- Earn share of protocol fees (60% of all swap fees)
- Time-weighted rewards distribution
- Cooldown period for unstaking (7 days)
- Emergency withdrawal with penalty

Fee Distribution:
- 60% to stakers (this contract)
- 30% to relayers (RelayerRegistry)
- 10% to treasury

Staking rewards are distributed in the fee tokens (ETH, USDC, etc.)
not in TESS, ensuring sustainable tokenomics.
"""

from vyper.interfaces import ERC20

# Events
event Staked:
    user: indexed(address)
    amount: uint256
    shares: uint256

event UnstakeRequested:
    user: indexed(address)
    shares: uint256
    available_at: uint256

event Unstaked:
    user: indexed(address)
    amount: uint256

event EmergencyWithdraw:
    user: indexed(address)
    amount: uint256
    penalty: uint256

event RewardsDistributed:
    token: indexed(address)
    amount: uint256
    total_shares: uint256

event RewardsClaimed:
    user: indexed(address)
    token: indexed(address)
    amount: uint256

event CooldownUpdated:
    old_cooldown: uint256
    new_cooldown: uint256

# Staking state
struct StakeInfo:
    shares: uint256                    # User's share of the pool
    stake_time: uint256                # When user staked
    pending_unstake: uint256           # Shares pending unstake
    unstake_available_at: uint256      # When unstake becomes available

stakers: public(HashMap[address, StakeInfo])
total_shares: public(uint256)
total_staked: public(uint256)

# Reward tracking per token
# Using "reward per share" model for gas-efficient distribution
struct RewardInfo:
    accumulated_per_share: uint256     # Accumulated rewards per share (scaled by 1e18)
    last_update_block: uint256

reward_tokens: public(DynArray[address, 10])  # Supported reward tokens
reward_info: public(HashMap[address, RewardInfo])

# User reward tracking
user_reward_debt: HashMap[address, HashMap[address, uint256]]  # user -> token -> debt
user_pending_rewards: HashMap[address, HashMap[address, uint256]]  # user -> token -> pending

# Configuration
TESS_TOKEN: public(immutable(address))
COOLDOWN_PERIOD: public(uint256)
EMERGENCY_PENALTY_BPS: constant(uint256) = 1000  # 10% penalty for emergency withdraw
MIN_STAKE: constant(uint256) = 1000 * 10 ** 18   # Minimum 1000 TESS

PRECISION: constant(uint256) = 10 ** 18

# Access control
owner: public(address)
fee_distributor: public(address)  # Contract that can distribute rewards

# Constants
MAX_COOLDOWN: constant(uint256) = 30 * 86400  # 30 days max
DEFAULT_COOLDOWN: constant(uint256) = 7 * 86400  # 7 days default


@external
def __init__(tess_token: address):
    """Initialize staking contract."""
    TESS_TOKEN = tess_token
    self.owner = msg.sender
    self.fee_distributor = msg.sender
    self.COOLDOWN_PERIOD = DEFAULT_COOLDOWN


@internal
def _update_rewards(user: address):
    """Update reward calculations for a user before balance changes."""
    for token in self.reward_tokens:
        if self.stakers[user].shares > 0:
            # Calculate pending rewards
            acc_per_share: uint256 = self.reward_info[token].accumulated_per_share
            user_shares: uint256 = self.stakers[user].shares
            debt: uint256 = self.user_reward_debt[user][token]

            pending: uint256 = (user_shares * acc_per_share / PRECISION) - debt
            self.user_pending_rewards[user][token] += pending

        # Update debt to current accumulated
        self.user_reward_debt[user][token] = (
            self.stakers[user].shares * self.reward_info[token].accumulated_per_share / PRECISION
        )


@external
def stake(amount: uint256):
    """
    Stake TESS tokens to earn protocol fees.

    Tokens are transferred from sender and shares are minted proportionally.
    """
    assert amount >= MIN_STAKE or self.stakers[msg.sender].shares > 0, "Below minimum stake"

    # Update rewards before balance change
    self._update_rewards(msg.sender)

    # Transfer TESS tokens
    assert ERC20(TESS_TOKEN).transferFrom(msg.sender, self, amount), "Transfer failed"

    # Calculate shares to mint
    shares_to_mint: uint256 = 0
    if self.total_shares == 0:
        shares_to_mint = amount
    else:
        shares_to_mint = (amount * self.total_shares) / self.total_staked

    assert shares_to_mint > 0, "Zero shares"

    # Update state
    self.stakers[msg.sender].shares += shares_to_mint
    self.stakers[msg.sender].stake_time = block.timestamp
    self.total_shares += shares_to_mint
    self.total_staked += amount

    # Update reward debt
    for token in self.reward_tokens:
        self.user_reward_debt[msg.sender][token] = (
            self.stakers[msg.sender].shares * self.reward_info[token].accumulated_per_share / PRECISION
        )

    log Staked(msg.sender, amount, shares_to_mint)


@external
def request_unstake(shares: uint256):
    """
    Request to unstake shares.

    Starts the cooldown period. Call unstake() after cooldown completes.
    """
    assert shares > 0, "Zero shares"
    assert self.stakers[msg.sender].shares >= shares, "Insufficient shares"
    assert self.stakers[msg.sender].pending_unstake == 0, "Unstake already pending"

    # Update rewards
    self._update_rewards(msg.sender)

    # Set pending unstake
    self.stakers[msg.sender].pending_unstake = shares
    self.stakers[msg.sender].unstake_available_at = block.timestamp + self.COOLDOWN_PERIOD

    log UnstakeRequested(msg.sender, shares, block.timestamp + self.COOLDOWN_PERIOD)


@external
def unstake():
    """
    Complete unstake after cooldown period.

    Returns TESS tokens proportional to shares.
    """
    assert self.stakers[msg.sender].pending_unstake > 0, "No pending unstake"
    assert block.timestamp >= self.stakers[msg.sender].unstake_available_at, "Cooldown not complete"

    # Update rewards
    self._update_rewards(msg.sender)

    shares: uint256 = self.stakers[msg.sender].pending_unstake

    # Calculate TESS to return
    amount: uint256 = (shares * self.total_staked) / self.total_shares

    # Update state
    self.stakers[msg.sender].shares -= shares
    self.stakers[msg.sender].pending_unstake = 0
    self.stakers[msg.sender].unstake_available_at = 0
    self.total_shares -= shares
    self.total_staked -= amount

    # Update reward debt
    for token in self.reward_tokens:
        self.user_reward_debt[msg.sender][token] = (
            self.stakers[msg.sender].shares * self.reward_info[token].accumulated_per_share / PRECISION
        )

    # Transfer TESS
    assert ERC20(TESS_TOKEN).transfer(msg.sender, amount), "Transfer failed"

    log Unstaked(msg.sender, amount)


@external
def cancel_unstake():
    """Cancel a pending unstake request."""
    assert self.stakers[msg.sender].pending_unstake > 0, "No pending unstake"

    self.stakers[msg.sender].pending_unstake = 0
    self.stakers[msg.sender].unstake_available_at = 0


@external
def emergency_withdraw():
    """
    Emergency withdraw with penalty.

    Bypasses cooldown but takes 10% penalty to treasury.
    Use only in emergencies.
    """
    shares: uint256 = self.stakers[msg.sender].shares
    assert shares > 0, "No stake"

    # Update rewards first
    self._update_rewards(msg.sender)

    # Calculate TESS to return
    amount: uint256 = (shares * self.total_staked) / self.total_shares

    # Calculate penalty
    penalty: uint256 = (amount * EMERGENCY_PENALTY_BPS) / 10000
    return_amount: uint256 = amount - penalty

    # Update state
    self.stakers[msg.sender].shares = 0
    self.stakers[msg.sender].pending_unstake = 0
    self.stakers[msg.sender].unstake_available_at = 0
    self.total_shares -= shares
    self.total_staked -= amount

    # Clear reward debt
    for token in self.reward_tokens:
        self.user_reward_debt[msg.sender][token] = 0

    # Transfer (penalty stays in contract for next distribution)
    assert ERC20(TESS_TOKEN).transfer(msg.sender, return_amount), "Transfer failed"

    log EmergencyWithdraw(msg.sender, return_amount, penalty)


# Reward Distribution

@external
def distribute_rewards(token: address, amount: uint256):
    """
    Distribute fee rewards to stakers.

    Called by fee distributor contract when fees are collected.
    """
    assert msg.sender == self.fee_distributor or msg.sender == self.owner, "Not authorized"
    assert amount > 0, "Zero amount"
    assert self.total_shares > 0, "No stakers"

    # Transfer reward tokens
    assert ERC20(token).transferFrom(msg.sender, self, amount), "Transfer failed"

    # Add to supported tokens if new
    is_new: bool = True
    for existing in self.reward_tokens:
        if existing == token:
            is_new = False
            break

    if is_new:
        assert len(self.reward_tokens) < 10, "Too many reward tokens"
        self.reward_tokens.append(token)

    # Update accumulated per share
    self.reward_info[token].accumulated_per_share += (amount * PRECISION) / self.total_shares
    self.reward_info[token].last_update_block = block.number

    log RewardsDistributed(token, amount, self.total_shares)


@external
def claim_rewards():
    """Claim all pending rewards across all tokens."""
    self._update_rewards(msg.sender)

    for token in self.reward_tokens:
        pending: uint256 = self.user_pending_rewards[msg.sender][token]
        if pending > 0:
            self.user_pending_rewards[msg.sender][token] = 0
            assert ERC20(token).transfer(msg.sender, pending), "Transfer failed"
            log RewardsClaimed(msg.sender, token, pending)


@external
def claim_reward(token: address):
    """Claim pending rewards for a specific token."""
    self._update_rewards(msg.sender)

    pending: uint256 = self.user_pending_rewards[msg.sender][token]
    assert pending > 0, "No pending rewards"

    self.user_pending_rewards[msg.sender][token] = 0
    assert ERC20(token).transfer(msg.sender, pending), "Transfer failed"

    log RewardsClaimed(msg.sender, token, pending)


# View Functions

@view
@external
def get_stake_info(user: address) -> (uint256, uint256, uint256, uint256):
    """Get staking info for a user."""
    info: StakeInfo = self.stakers[user]
    staked_amount: uint256 = 0
    if self.total_shares > 0:
        staked_amount = (info.shares * self.total_staked) / self.total_shares
    return (info.shares, staked_amount, info.pending_unstake, info.unstake_available_at)


@view
@external
def pending_rewards(user: address, token: address) -> uint256:
    """Calculate pending rewards for a user and token."""
    if self.stakers[user].shares == 0:
        return self.user_pending_rewards[user][token]

    acc_per_share: uint256 = self.reward_info[token].accumulated_per_share
    user_shares: uint256 = self.stakers[user].shares
    debt: uint256 = self.user_reward_debt[user][token]

    pending: uint256 = (user_shares * acc_per_share / PRECISION) - debt
    return pending + self.user_pending_rewards[user][token]


@view
@external
def get_exchange_rate() -> uint256:
    """Get current TESS per share rate (scaled by 1e18)."""
    if self.total_shares == 0:
        return PRECISION
    return (self.total_staked * PRECISION) / self.total_shares


@view
@external
def get_reward_tokens() -> DynArray[address, 10]:
    """Get list of reward tokens."""
    return self.reward_tokens


# Admin Functions

@external
def set_fee_distributor(new_distributor: address):
    """Set the fee distributor address."""
    assert msg.sender == self.owner, "Only owner"
    assert new_distributor != empty(address), "Invalid address"
    self.fee_distributor = new_distributor


@external
def set_cooldown_period(new_cooldown: uint256):
    """Update the cooldown period."""
    assert msg.sender == self.owner, "Only owner"
    assert new_cooldown <= MAX_COOLDOWN, "Cooldown too long"

    old_cooldown: uint256 = self.COOLDOWN_PERIOD
    self.COOLDOWN_PERIOD = new_cooldown

    log CooldownUpdated(old_cooldown, new_cooldown)


@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    assert msg.sender == self.owner, "Only owner"
    assert new_owner != empty(address), "Invalid owner"
    self.owner = new_owner


@external
def recover_tokens(token: address, amount: uint256):
    """
    Recover accidentally sent tokens.

    Cannot recover TESS (staked tokens) or reward tokens with balances.
    """
    assert msg.sender == self.owner, "Only owner"
    assert token != TESS_TOKEN, "Cannot recover staked tokens"

    # Check it's not a reward token with balance
    for reward_token in self.reward_tokens:
        if token == reward_token:
            assert False, "Cannot recover reward tokens"

    assert ERC20(token).transfer(self.owner, amount), "Transfer failed"
