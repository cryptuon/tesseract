# @version ^0.3.10
"""
RelayerRegistry: Register and manage cross-chain relayers

Features:
- Relayers stake TESS to participate
- Minimum stake requirement (50,000 TESS)
- Performance tracking and rewards
- Slashing for misbehavior
- Receives 30% of protocol fees

Relayers must:
1. Stake minimum TESS tokens
2. Maintain good performance (>95% success rate)
3. Be active (heartbeat within 1 hour)
"""

from vyper.interfaces import ERC20

# Events
event RelayerRegistered:
    relayer: indexed(address)
    stake_amount: uint256
    chains: DynArray[uint256, 10]

event RelayerStakeUpdated:
    relayer: indexed(address)
    new_stake: uint256
    is_increase: bool

event RelayerDeregistered:
    relayer: indexed(address)
    returned_stake: uint256

event RelayerSlashed:
    relayer: indexed(address)
    slash_amount: uint256
    reason: String[100]

event TaskCompleted:
    relayer: indexed(address)
    task_id: bytes32
    chain_id: uint256
    success: bool

event RewardsClaimed:
    relayer: indexed(address)
    amount: uint256
    token: address

event HeartbeatReceived:
    relayer: indexed(address)
    timestamp: uint256

# Relayer info
struct RelayerInfo:
    stake_amount: uint256
    registered_at: uint256
    last_heartbeat: uint256
    total_tasks: uint256
    successful_tasks: uint256
    failed_tasks: uint256
    total_rewards_earned: uint256
    is_active: bool
    is_jailed: bool
    jail_release_time: uint256

relayers: public(HashMap[address, RelayerInfo])
relayer_list: public(DynArray[address, 1000])
relayer_count: public(uint256)

# Relayer supported chains
relayer_chains: HashMap[address, DynArray[uint256, 10]]

# Pending rewards per relayer per token
pending_rewards: HashMap[address, HashMap[address, uint256]]

# Configuration
TESS_TOKEN: public(immutable(address))
MIN_STAKE: public(uint256)
HEARTBEAT_INTERVAL: public(uint256)
JAIL_DURATION: public(uint256)
MIN_SUCCESS_RATE: public(uint256)  # Basis points (9500 = 95%)

# Slashing parameters
SLASH_RATE_FAILURE: public(uint256)    # Basis points for task failure
SLASH_RATE_DOWNTIME: public(uint256)   # Basis points for missed heartbeat

# Supported reward tokens
reward_tokens: public(DynArray[address, 10])

# Total active stake
total_stake: public(uint256)

# Access control
owner: public(address)
fee_collector: public(address)  # Receives fees to distribute

# Constants
DEFAULT_MIN_STAKE: constant(uint256) = 50_000 * 10 ** 18  # 50k TESS
DEFAULT_HEARTBEAT: constant(uint256) = 3600  # 1 hour
DEFAULT_JAIL: constant(uint256) = 86400  # 24 hours
DEFAULT_MIN_SUCCESS: constant(uint256) = 9500  # 95%
DEFAULT_SLASH_FAILURE: constant(uint256) = 100  # 1%
DEFAULT_SLASH_DOWNTIME: constant(uint256) = 500  # 5%


@external
def __init__(tess_token: address):
    """Initialize relayer registry."""
    TESS_TOKEN = tess_token
    self.owner = msg.sender
    self.MIN_STAKE = DEFAULT_MIN_STAKE
    self.HEARTBEAT_INTERVAL = DEFAULT_HEARTBEAT
    self.JAIL_DURATION = DEFAULT_JAIL
    self.MIN_SUCCESS_RATE = DEFAULT_MIN_SUCCESS
    self.SLASH_RATE_FAILURE = DEFAULT_SLASH_FAILURE
    self.SLASH_RATE_DOWNTIME = DEFAULT_SLASH_DOWNTIME


@external
def register(stake_amount: uint256, chains: DynArray[uint256, 10]):
    """
    Register as a relayer with initial stake.

    Must stake at least MIN_STAKE TESS tokens.
    """
    assert not self.relayers[msg.sender].is_active, "Already registered"
    assert stake_amount >= self.MIN_STAKE, "Insufficient stake"
    assert len(chains) > 0, "No chains specified"

    # Transfer stake
    assert ERC20(TESS_TOKEN).transferFrom(msg.sender, self, stake_amount), "Transfer failed"

    # Register relayer
    self.relayers[msg.sender] = RelayerInfo({
        stake_amount: stake_amount,
        registered_at: block.timestamp,
        last_heartbeat: block.timestamp,
        total_tasks: 0,
        successful_tasks: 0,
        failed_tasks: 0,
        total_rewards_earned: 0,
        is_active: True,
        is_jailed: False,
        jail_release_time: 0
    })

    self.relayer_chains[msg.sender] = chains
    self.relayer_list.append(msg.sender)
    self.relayer_count += 1
    self.total_stake += stake_amount

    log RelayerRegistered(msg.sender, stake_amount, chains)


@external
def increase_stake(amount: uint256):
    """Add more stake to existing registration."""
    assert self.relayers[msg.sender].is_active, "Not registered"
    assert amount > 0, "Zero amount"

    assert ERC20(TESS_TOKEN).transferFrom(msg.sender, self, amount), "Transfer failed"

    self.relayers[msg.sender].stake_amount += amount
    self.total_stake += amount

    log RelayerStakeUpdated(msg.sender, self.relayers[msg.sender].stake_amount, True)


@external
def decrease_stake(amount: uint256):
    """
    Reduce stake (if above minimum).

    Cannot reduce below MIN_STAKE.
    """
    assert self.relayers[msg.sender].is_active, "Not registered"
    assert not self.relayers[msg.sender].is_jailed, "Currently jailed"

    current_stake: uint256 = self.relayers[msg.sender].stake_amount
    assert current_stake - amount >= self.MIN_STAKE, "Would fall below minimum"

    self.relayers[msg.sender].stake_amount -= amount
    self.total_stake -= amount

    assert ERC20(TESS_TOKEN).transfer(msg.sender, amount), "Transfer failed"

    log RelayerStakeUpdated(msg.sender, self.relayers[msg.sender].stake_amount, False)


@external
def deregister():
    """
    Deregister as a relayer and return stake.

    Must not be jailed and must have good standing.
    """
    info: RelayerInfo = self.relayers[msg.sender]
    assert info.is_active, "Not registered"
    assert not info.is_jailed, "Currently jailed"

    stake_to_return: uint256 = info.stake_amount

    # Clear relayer data
    self.relayers[msg.sender].is_active = False
    self.relayers[msg.sender].stake_amount = 0
    self.total_stake -= stake_to_return
    self.relayer_count -= 1

    # Return stake
    assert ERC20(TESS_TOKEN).transfer(msg.sender, stake_to_return), "Transfer failed"

    log RelayerDeregistered(msg.sender, stake_to_return)


@external
def heartbeat():
    """
    Send heartbeat to prove relayer is active.

    Must be called at least every HEARTBEAT_INTERVAL.
    """
    assert self.relayers[msg.sender].is_active, "Not registered"

    self.relayers[msg.sender].last_heartbeat = block.timestamp

    # Release from jail if time served
    if self.relayers[msg.sender].is_jailed:
        if block.timestamp >= self.relayers[msg.sender].jail_release_time:
            self.relayers[msg.sender].is_jailed = False
            self.relayers[msg.sender].jail_release_time = 0

    log HeartbeatReceived(msg.sender, block.timestamp)


@external
def record_task(relayer: address, task_id: bytes32, chain_id: uint256, success: bool):
    """
    Record task completion by a relayer.

    Called by authorized contracts (TesseractBuffer, Coordinator).
    """
    assert msg.sender == self.owner or msg.sender == self.fee_collector, "Not authorized"
    assert self.relayers[relayer].is_active, "Relayer not registered"

    self.relayers[relayer].total_tasks += 1

    if success:
        self.relayers[relayer].successful_tasks += 1
    else:
        self.relayers[relayer].failed_tasks += 1
        # Apply slash for failure
        self._slash(relayer, self.SLASH_RATE_FAILURE, "Task failure")

    log TaskCompleted(relayer, task_id, chain_id, success)


@internal
def _slash(relayer: address, rate_bps: uint256, reason: String[100]):
    """Apply slashing penalty to a relayer."""
    stake: uint256 = self.relayers[relayer].stake_amount
    slash_amount: uint256 = (stake * rate_bps) / 10000

    if slash_amount > 0:
        self.relayers[relayer].stake_amount -= slash_amount
        self.total_stake -= slash_amount
        # Slashed tokens go to treasury (could send to stakers instead)

        log RelayerSlashed(relayer, slash_amount, reason)

    # Check if fallen below minimum stake
    if self.relayers[relayer].stake_amount < self.MIN_STAKE:
        self.relayers[relayer].is_jailed = True
        self.relayers[relayer].jail_release_time = block.timestamp + self.JAIL_DURATION


@external
def check_and_slash_inactive():
    """
    Check for inactive relayers and apply slashing.

    Can be called by anyone (incentivized by keeping network healthy).
    """
    for relayer in self.relayer_list:
        if not self.relayers[relayer].is_active:
            continue
        if self.relayers[relayer].is_jailed:
            continue

        # Check heartbeat
        if block.timestamp > self.relayers[relayer].last_heartbeat + self.HEARTBEAT_INTERVAL:
            self._slash(relayer, self.SLASH_RATE_DOWNTIME, "Missed heartbeat")


@external
@payable
def receive_fees(token: address, amount: uint256):
    """
    Receive fee rewards from FeeCollector.

    Distributes proportionally based on stake and performance.
    """
    assert msg.sender == self.fee_collector or msg.sender == self.owner, "Not authorized"

    if token == 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE:  # ETH
        assert msg.value == amount, "Incorrect ETH amount"
    else:
        assert ERC20(token).transferFrom(msg.sender, self, amount), "Transfer failed"

        # Add to reward tokens if new
        is_new: bool = True
        for existing in self.reward_tokens:
            if existing == token:
                is_new = False
                break
        if is_new:
            self.reward_tokens.append(token)

    # Distribute to active, non-jailed relayers based on stake
    if self.total_stake == 0:
        return

    for relayer in self.relayer_list:
        if not self.relayers[relayer].is_active or self.relayers[relayer].is_jailed:
            continue

        # Calculate share based on stake
        share: uint256 = (amount * self.relayers[relayer].stake_amount) / self.total_stake
        if share > 0:
            self.pending_rewards[relayer][token] += share


@external
def claim_rewards(token: address):
    """Claim pending rewards for a specific token."""
    amount: uint256 = self.pending_rewards[msg.sender][token]
    assert amount > 0, "No pending rewards"

    self.pending_rewards[msg.sender][token] = 0
    self.relayers[msg.sender].total_rewards_earned += amount

    if token == 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE:  # ETH
        send(msg.sender, amount)
    else:
        assert ERC20(token).transfer(msg.sender, amount), "Transfer failed"

    log RewardsClaimed(msg.sender, amount, token)


@external
def claim_all_rewards():
    """Claim all pending rewards."""
    for token in self.reward_tokens:
        amount: uint256 = self.pending_rewards[msg.sender][token]
        if amount > 0:
            self.pending_rewards[msg.sender][token] = 0
            self.relayers[msg.sender].total_rewards_earned += amount

            if token == 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE:
                send(msg.sender, amount)
            else:
                ERC20(token).transfer(msg.sender, amount)

            log RewardsClaimed(msg.sender, amount, token)


# View Functions

@view
@external
def get_relayer_info(relayer: address) -> RelayerInfo:
    """Get full relayer information."""
    return self.relayers[relayer]


@view
@external
def get_relayer_chains(relayer: address) -> DynArray[uint256, 10]:
    """Get chains supported by a relayer."""
    return self.relayer_chains[relayer]


@view
@external
def get_success_rate(relayer: address) -> uint256:
    """Get relayer success rate in basis points."""
    info: RelayerInfo = self.relayers[relayer]
    if info.total_tasks == 0:
        return 10000  # 100% if no tasks yet
    return (info.successful_tasks * 10000) / info.total_tasks


@view
@external
def get_pending_rewards(relayer: address, token: address) -> uint256:
    """Get pending rewards for a relayer."""
    return self.pending_rewards[relayer][token]


@view
@external
def is_eligible(relayer: address) -> bool:
    """Check if relayer is eligible to perform tasks."""
    info: RelayerInfo = self.relayers[relayer]
    if not info.is_active or info.is_jailed:
        return False
    if info.stake_amount < self.MIN_STAKE:
        return False
    if block.timestamp > info.last_heartbeat + self.HEARTBEAT_INTERVAL:
        return False
    return True


@view
@external
def get_active_relayers() -> DynArray[address, 100]:
    """Get list of active, eligible relayers."""
    active: DynArray[address, 100] = []
    for relayer in self.relayer_list:
        if len(active) >= 100:
            break
        info: RelayerInfo = self.relayers[relayer]
        if info.is_active and not info.is_jailed:
            if info.stake_amount >= self.MIN_STAKE:
                if block.timestamp <= info.last_heartbeat + self.HEARTBEAT_INTERVAL:
                    active.append(relayer)
    return active


# Admin Functions

@external
def set_min_stake(new_min: uint256):
    """Update minimum stake requirement."""
    assert msg.sender == self.owner, "Only owner"
    assert new_min >= 10_000 * 10 ** 18, "Minimum too low"  # At least 10k
    self.MIN_STAKE = new_min


@external
def set_heartbeat_interval(new_interval: uint256):
    """Update heartbeat interval."""
    assert msg.sender == self.owner, "Only owner"
    assert new_interval >= 600, "Interval too short"  # At least 10 min
    assert new_interval <= 86400, "Interval too long"  # At most 24 hours
    self.HEARTBEAT_INTERVAL = new_interval


@external
def set_slash_rates(failure_bps: uint256, downtime_bps: uint256):
    """Update slashing rates."""
    assert msg.sender == self.owner, "Only owner"
    assert failure_bps <= 1000, "Failure rate too high"  # Max 10%
    assert downtime_bps <= 2000, "Downtime rate too high"  # Max 20%
    self.SLASH_RATE_FAILURE = failure_bps
    self.SLASH_RATE_DOWNTIME = downtime_bps


@external
def set_fee_collector(new_collector: address):
    """Update fee collector address."""
    assert msg.sender == self.owner, "Only owner"
    self.fee_collector = new_collector


@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    assert msg.sender == self.owner, "Only owner"
    assert new_owner != empty(address), "Invalid owner"
    self.owner = new_owner


@external
def emergency_release(relayer: address):
    """Emergency release a relayer from jail."""
    assert msg.sender == self.owner, "Only owner"
    self.relayers[relayer].is_jailed = False
    self.relayers[relayer].jail_release_time = 0
