# @version ^0.3.10
"""
FeeCollector: Collect and distribute protocol fees

Collects fees from AtomicSwapCoordinator and distributes:
- 60% to TESS stakers
- 30% to relayers
- 10% to treasury

Supports multiple fee tokens (ETH, USDC, WETH, etc.)
Batches distributions for gas efficiency.
"""

from vyper.interfaces import ERC20

# Events
event FeeCollected:
    token: indexed(address)
    amount: uint256
    order_id: bytes32

event FeesDistributed:
    token: indexed(address)
    staker_amount: uint256
    relayer_amount: uint256
    treasury_amount: uint256

event FeeRatesUpdated:
    staker_rate: uint256
    relayer_rate: uint256
    treasury_rate: uint256

event TokenWhitelisted:
    token: indexed(address)
    enabled: bool

# Fee distribution (basis points, 10000 = 100%)
staker_fee_bps: public(uint256)      # Default 6000 (60%)
relayer_fee_bps: public(uint256)     # Default 3000 (30%)
treasury_fee_bps: public(uint256)    # Default 1000 (10%)

# Accumulated fees per token
accumulated_fees: public(HashMap[address, uint256])

# Distribution targets
staking_contract: public(address)
relayer_registry: public(address)
treasury: public(address)

# Whitelisted fee tokens
whitelisted_tokens: public(HashMap[address, bool])
token_list: public(DynArray[address, 20])

# Authorized fee collectors (AtomicSwapCoordinator contracts)
authorized_collectors: public(HashMap[address, bool])

# Minimum distribution threshold (to batch for gas efficiency)
min_distribution_amount: public(HashMap[address, uint256])

# Access control
owner: public(address)

# ETH handling
ETH_ADDRESS: constant(address) = 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE


@external
def __init__(
    _staking_contract: address,
    _relayer_registry: address,
    _treasury: address
):
    """Initialize fee collector."""
    self.owner = msg.sender
    self.staking_contract = _staking_contract
    self.relayer_registry = _relayer_registry
    self.treasury = _treasury

    # Default fee distribution: 60/30/10
    self.staker_fee_bps = 6000
    self.relayer_fee_bps = 3000
    self.treasury_fee_bps = 1000


@external
@payable
def collect_fee(token: address, amount: uint256, order_id: bytes32):
    """
    Collect fees from a swap.

    Called by authorized AtomicSwapCoordinator contracts.
    """
    assert self.authorized_collectors[msg.sender], "Not authorized"
    assert amount > 0, "Zero amount"

    if token == ETH_ADDRESS:
        assert msg.value == amount, "Incorrect ETH amount"
    else:
        assert self.whitelisted_tokens[token], "Token not whitelisted"
        assert ERC20(token).transferFrom(msg.sender, self, amount), "Transfer failed"

    self.accumulated_fees[token] += amount

    log FeeCollected(token, amount, order_id)


@external
@payable
def __default__():
    """Accept ETH payments."""
    if msg.value > 0:
        self.accumulated_fees[ETH_ADDRESS] += msg.value


@external
def distribute_fees(token: address):
    """
    Distribute accumulated fees for a token.

    Can be called by anyone - gas cost incentivizes batching.
    """
    amount: uint256 = self.accumulated_fees[token]
    min_amount: uint256 = self.min_distribution_amount[token]

    assert amount > 0, "No fees to distribute"
    assert amount >= min_amount, "Below minimum distribution"

    # Calculate distribution
    staker_amount: uint256 = (amount * self.staker_fee_bps) / 10000
    relayer_amount: uint256 = (amount * self.relayer_fee_bps) / 10000
    treasury_amount: uint256 = amount - staker_amount - relayer_amount  # Remainder to treasury

    # Clear accumulated (before transfers to prevent reentrancy)
    self.accumulated_fees[token] = 0

    # Distribute
    if token == ETH_ADDRESS:
        # ETH distribution
        if staker_amount > 0:
            send(self.staking_contract, staker_amount)
        if relayer_amount > 0:
            send(self.relayer_registry, relayer_amount)
        if treasury_amount > 0:
            send(self.treasury, treasury_amount)
    else:
        # ERC-20 distribution
        if staker_amount > 0:
            # Approve and notify staking contract
            ERC20(token).approve(self.staking_contract, staker_amount)
            # Note: Staking contract should have a receive_fees function
            # For simplicity, we transfer directly here
            assert ERC20(token).transfer(self.staking_contract, staker_amount), "Staker transfer failed"

        if relayer_amount > 0:
            assert ERC20(token).transfer(self.relayer_registry, relayer_amount), "Relayer transfer failed"

        if treasury_amount > 0:
            assert ERC20(token).transfer(self.treasury, treasury_amount), "Treasury transfer failed"

    log FeesDistributed(token, staker_amount, relayer_amount, treasury_amount)


@external
def distribute_all():
    """Distribute fees for all tokens above threshold."""
    for token in self.token_list:
        amount: uint256 = self.accumulated_fees[token]
        min_amount: uint256 = self.min_distribution_amount[token]

        if amount >= min_amount and amount > 0:
            self._distribute_single(token, amount)

    # Also check ETH
    eth_amount: uint256 = self.accumulated_fees[ETH_ADDRESS]
    eth_min: uint256 = self.min_distribution_amount[ETH_ADDRESS]
    if eth_amount >= eth_min and eth_amount > 0:
        self._distribute_single(ETH_ADDRESS, eth_amount)


@internal
def _distribute_single(token: address, amount: uint256):
    """Internal distribution helper."""
    staker_amount: uint256 = (amount * self.staker_fee_bps) / 10000
    relayer_amount: uint256 = (amount * self.relayer_fee_bps) / 10000
    treasury_amount: uint256 = amount - staker_amount - relayer_amount

    self.accumulated_fees[token] = 0

    if token == ETH_ADDRESS:
        if staker_amount > 0:
            send(self.staking_contract, staker_amount)
        if relayer_amount > 0:
            send(self.relayer_registry, relayer_amount)
        if treasury_amount > 0:
            send(self.treasury, treasury_amount)
    else:
        if staker_amount > 0:
            ERC20(token).transfer(self.staking_contract, staker_amount)
        if relayer_amount > 0:
            ERC20(token).transfer(self.relayer_registry, relayer_amount)
        if treasury_amount > 0:
            ERC20(token).transfer(self.treasury, treasury_amount)

    log FeesDistributed(token, staker_amount, relayer_amount, treasury_amount)


# View Functions

@view
@external
def get_pending_fees(token: address) -> uint256:
    """Get accumulated fees pending distribution."""
    return self.accumulated_fees[token]


@view
@external
def get_distribution_preview(token: address) -> (uint256, uint256, uint256):
    """Preview how fees would be distributed."""
    amount: uint256 = self.accumulated_fees[token]
    staker_amount: uint256 = (amount * self.staker_fee_bps) / 10000
    relayer_amount: uint256 = (amount * self.relayer_fee_bps) / 10000
    treasury_amount: uint256 = amount - staker_amount - relayer_amount
    return (staker_amount, relayer_amount, treasury_amount)


@view
@external
def get_fee_rates() -> (uint256, uint256, uint256):
    """Get current fee distribution rates in basis points."""
    return (self.staker_fee_bps, self.relayer_fee_bps, self.treasury_fee_bps)


# Admin Functions

@external
def set_fee_rates(staker_bps: uint256, relayer_bps: uint256, treasury_bps: uint256):
    """Update fee distribution rates."""
    assert msg.sender == self.owner, "Only owner"
    assert staker_bps + relayer_bps + treasury_bps == 10000, "Must equal 100%"
    assert staker_bps >= 5000, "Staker rate too low"  # Min 50% to stakers
    assert treasury_bps <= 2000, "Treasury rate too high"  # Max 20% to treasury

    self.staker_fee_bps = staker_bps
    self.relayer_fee_bps = relayer_bps
    self.treasury_fee_bps = treasury_bps

    log FeeRatesUpdated(staker_bps, relayer_bps, treasury_bps)


@external
def whitelist_token(token: address, enabled: bool):
    """Add or remove token from whitelist."""
    assert msg.sender == self.owner, "Only owner"
    assert token != empty(address), "Invalid token"

    was_whitelisted: bool = self.whitelisted_tokens[token]
    self.whitelisted_tokens[token] = enabled

    # Update token list
    if enabled and not was_whitelisted:
        self.token_list.append(token)
    elif not enabled and was_whitelisted:
        # Remove from list (swap and pop)
        for i in range(20):
            if i >= len(self.token_list):
                break
            if self.token_list[i] == token:
                if i < len(self.token_list) - 1:
                    self.token_list[i] = self.token_list[len(self.token_list) - 1]
                self.token_list.pop()
                break

    log TokenWhitelisted(token, enabled)


@external
def set_min_distribution(token: address, min_amount: uint256):
    """Set minimum distribution threshold for a token."""
    assert msg.sender == self.owner, "Only owner"
    self.min_distribution_amount[token] = min_amount


@external
def authorize_collector(collector: address, authorized: bool):
    """Authorize or revoke a fee collector (swap coordinator)."""
    assert msg.sender == self.owner, "Only owner"
    self.authorized_collectors[collector] = authorized


@external
def set_staking_contract(new_staking: address):
    """Update staking contract address."""
    assert msg.sender == self.owner, "Only owner"
    assert new_staking != empty(address), "Invalid address"
    self.staking_contract = new_staking


@external
def set_relayer_registry(new_registry: address):
    """Update relayer registry address."""
    assert msg.sender == self.owner, "Only owner"
    assert new_registry != empty(address), "Invalid address"
    self.relayer_registry = new_registry


@external
def set_treasury(new_treasury: address):
    """Update treasury address."""
    assert msg.sender == self.owner, "Only owner"
    assert new_treasury != empty(address), "Invalid address"
    self.treasury = new_treasury


@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    assert msg.sender == self.owner, "Only owner"
    assert new_owner != empty(address), "Invalid owner"
    self.owner = new_owner


@external
def emergency_withdraw(token: address, amount: uint256, recipient: address):
    """Emergency withdrawal of stuck tokens."""
    assert msg.sender == self.owner, "Only owner"
    assert recipient != empty(address), "Invalid recipient"

    if token == ETH_ADDRESS:
        send(recipient, amount)
    else:
        assert ERC20(token).transfer(recipient, amount), "Transfer failed"
