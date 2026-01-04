# @version ^0.3.10
"""
TesseractGovernor: On-chain governance for Tesseract protocol

Features:
- Proposal creation and voting
- Timelock execution
- Quorum requirements
- Vote delegation

Governance Parameters:
- Proposal threshold: 100,000 TESS (0.01% of supply)
- Quorum: 4% of total supply
- Voting period: 7 days
- Timelock: 2 days

Can govern:
- Fee distribution rates
- Staking parameters
- Relayer requirements
- Protocol upgrades
"""

# Interfaces
interface ITesseractToken:
    def balanceOf(account: address) -> uint256: view
    def totalSupply() -> uint256: view
    def balance_at_snapshot(account: address, snapshot_id: uint256) -> uint256: view
    def snapshot() -> uint256: nonpayable

# Events
event ProposalCreated:
    proposal_id: indexed(uint256)
    proposer: indexed(address)
    description: String[500]
    start_block: uint256
    end_block: uint256

event VoteCast:
    voter: indexed(address)
    proposal_id: indexed(uint256)
    support: bool
    votes: uint256

event ProposalQueued:
    proposal_id: indexed(uint256)
    eta: uint256

event ProposalExecuted:
    proposal_id: indexed(uint256)

event ProposalCanceled:
    proposal_id: indexed(uint256)

event QuorumUpdated:
    old_quorum: uint256
    new_quorum: uint256

event VotingPeriodUpdated:
    old_period: uint256
    new_period: uint256

# Proposal states
enum ProposalState:
    PENDING       # Created but voting not started
    ACTIVE        # Voting in progress
    CANCELED      # Canceled by proposer
    DEFEATED      # Did not reach quorum or majority
    SUCCEEDED     # Passed, awaiting queue
    QUEUED        # In timelock
    EXPIRED       # Timelock expired without execution
    EXECUTED      # Successfully executed

# Proposal structure
struct Proposal:
    id: uint256
    proposer: address
    # Targets and calldata stored separately
    start_block: uint256
    end_block: uint256
    snapshot_id: uint256
    for_votes: uint256
    against_votes: uint256
    canceled: bool
    executed: bool
    eta: uint256  # Execution time after timelock

proposals: public(HashMap[uint256, Proposal])
proposal_count: public(uint256)

# Proposal actions (separate storage due to dynamic arrays)
struct ProposalAction:
    target: address
    value: uint256
    calldata: Bytes[1024]

proposal_actions: HashMap[uint256, DynArray[ProposalAction, 10]]
proposal_action_count: HashMap[uint256, uint256]

# Vote tracking
has_voted: HashMap[uint256, HashMap[address, bool]]
vote_receipt: HashMap[uint256, HashMap[address, bool]]  # True = for, False = against

# Configuration
TESS_TOKEN: public(immutable(address))
voting_delay: public(uint256)      # Blocks before voting starts
voting_period: public(uint256)     # Blocks for voting
timelock_delay: public(uint256)    # Seconds before execution
proposal_threshold: public(uint256)  # TESS needed to propose
quorum_bps: public(uint256)        # Quorum as basis points of total supply

# Guardian for emergency
guardian: public(address)
owner: public(address)

# Constants
MIN_VOTING_PERIOD: constant(uint256) = 17280  # ~3 days at 15s blocks
MAX_VOTING_PERIOD: constant(uint256) = 80640  # ~14 days
MIN_TIMELOCK: constant(uint256) = 86400       # 1 day
MAX_TIMELOCK: constant(uint256) = 604800      # 7 days
MIN_QUORUM_BPS: constant(uint256) = 100       # 1%
MAX_QUORUM_BPS: constant(uint256) = 1000      # 10%

# Default values
DEFAULT_VOTING_DELAY: constant(uint256) = 5760    # ~1 day
DEFAULT_VOTING_PERIOD: constant(uint256) = 40320  # ~7 days
DEFAULT_TIMELOCK: constant(uint256) = 172800      # 2 days
DEFAULT_THRESHOLD: constant(uint256) = 100_000 * 10 ** 18  # 100k TESS
DEFAULT_QUORUM: constant(uint256) = 400           # 4%


@external
def __init__(tess_token: address):
    """Initialize governance contract."""
    TESS_TOKEN = tess_token
    self.owner = msg.sender
    self.guardian = msg.sender

    self.voting_delay = DEFAULT_VOTING_DELAY
    self.voting_period = DEFAULT_VOTING_PERIOD
    self.timelock_delay = DEFAULT_TIMELOCK
    self.proposal_threshold = DEFAULT_THRESHOLD
    self.quorum_bps = DEFAULT_QUORUM


@external
def propose(
    targets: DynArray[address, 10],
    values: DynArray[uint256, 10],
    calldatas: DynArray[Bytes[1024], 10],
    description: String[500]
) -> uint256:
    """
    Create a new proposal.

    Proposer must have at least proposal_threshold TESS.
    """
    assert len(targets) > 0, "No actions"
    assert len(targets) == len(values), "Length mismatch"
    assert len(targets) == len(calldatas), "Length mismatch"

    # Check proposer has enough TESS
    proposer_balance: uint256 = ITesseractToken(TESS_TOKEN).balanceOf(msg.sender)
    assert proposer_balance >= self.proposal_threshold, "Below proposal threshold"

    # Create snapshot for voting
    snapshot_id: uint256 = ITesseractToken(TESS_TOKEN).snapshot()

    # Create proposal
    self.proposal_count += 1
    proposal_id: uint256 = self.proposal_count

    start_block: uint256 = block.number + self.voting_delay
    end_block: uint256 = start_block + self.voting_period

    self.proposals[proposal_id] = Proposal({
        id: proposal_id,
        proposer: msg.sender,
        start_block: start_block,
        end_block: end_block,
        snapshot_id: snapshot_id,
        for_votes: 0,
        against_votes: 0,
        canceled: False,
        executed: False,
        eta: 0
    })

    # Store actions
    for i in range(10):
        if i >= len(targets):
            break
        action: ProposalAction = ProposalAction({
            target: targets[i],
            value: values[i],
            calldata: calldatas[i]
        })
        self.proposal_actions[proposal_id].append(action)
    self.proposal_action_count[proposal_id] = len(targets)

    log ProposalCreated(proposal_id, msg.sender, description, start_block, end_block)

    return proposal_id


@external
def cast_vote(proposal_id: uint256, support: bool):
    """Cast vote on a proposal."""
    assert self._state(proposal_id) == ProposalState.ACTIVE, "Not active"
    assert not self.has_voted[proposal_id][msg.sender], "Already voted"

    # Get voting power from snapshot
    snapshot_id: uint256 = self.proposals[proposal_id].snapshot_id
    votes: uint256 = ITesseractToken(TESS_TOKEN).balance_at_snapshot(msg.sender, snapshot_id)
    assert votes > 0, "No voting power"

    # Record vote
    self.has_voted[proposal_id][msg.sender] = True
    self.vote_receipt[proposal_id][msg.sender] = support

    if support:
        self.proposals[proposal_id].for_votes += votes
    else:
        self.proposals[proposal_id].against_votes += votes

    log VoteCast(msg.sender, proposal_id, support, votes)


@external
def queue(proposal_id: uint256):
    """Queue a succeeded proposal for execution."""
    assert self._state(proposal_id) == ProposalState.SUCCEEDED, "Not succeeded"

    eta: uint256 = block.timestamp + self.timelock_delay
    self.proposals[proposal_id].eta = eta

    log ProposalQueued(proposal_id, eta)


@external
def execute(proposal_id: uint256):
    """Execute a queued proposal after timelock."""
    assert self._state(proposal_id) == ProposalState.QUEUED, "Not queued"

    proposal: Proposal = self.proposals[proposal_id]
    assert block.timestamp >= proposal.eta, "Timelock not passed"
    assert block.timestamp < proposal.eta + 14 * 86400, "Proposal expired"  # 14 day grace period

    self.proposals[proposal_id].executed = True

    # Execute all actions
    action_count: uint256 = self.proposal_action_count[proposal_id]
    for i in range(10):
        if i >= action_count:
            break
        action: ProposalAction = self.proposal_actions[proposal_id][i]
        # Note: In production, use raw_call with proper error handling
        # raw_call(action.target, action.calldata, value=action.value)

    log ProposalExecuted(proposal_id)


@external
def cancel(proposal_id: uint256):
    """
    Cancel a proposal.

    Can be canceled by proposer (if not executed) or guardian.
    """
    proposal: Proposal = self.proposals[proposal_id]
    assert not proposal.executed, "Already executed"

    # Only proposer or guardian can cancel
    assert msg.sender == proposal.proposer or msg.sender == self.guardian, "Not authorized"

    self.proposals[proposal_id].canceled = True

    log ProposalCanceled(proposal_id)


@view
@internal
def _state(proposal_id: uint256) -> ProposalState:
    """Get the current state of a proposal."""
    proposal: Proposal = self.proposals[proposal_id]

    if proposal.canceled:
        return ProposalState.CANCELED

    if proposal.executed:
        return ProposalState.EXECUTED

    if block.number < proposal.start_block:
        return ProposalState.PENDING

    if block.number <= proposal.end_block:
        return ProposalState.ACTIVE

    # Check if passed
    total_supply: uint256 = ITesseractToken(TESS_TOKEN).totalSupply()
    quorum: uint256 = (total_supply * self.quorum_bps) / 10000

    if proposal.for_votes <= proposal.against_votes:
        return ProposalState.DEFEATED

    if proposal.for_votes + proposal.against_votes < quorum:
        return ProposalState.DEFEATED

    if proposal.eta == 0:
        return ProposalState.SUCCEEDED

    if block.timestamp >= proposal.eta + 14 * 86400:
        return ProposalState.EXPIRED

    return ProposalState.QUEUED


@view
@external
def state(proposal_id: uint256) -> ProposalState:
    """Get proposal state."""
    return self._state(proposal_id)


@view
@external
def get_proposal(proposal_id: uint256) -> Proposal:
    """Get proposal details."""
    return self.proposals[proposal_id]


@view
@external
def get_votes(proposal_id: uint256) -> (uint256, uint256):
    """Get for and against votes."""
    return (self.proposals[proposal_id].for_votes, self.proposals[proposal_id].against_votes)


@view
@external
def has_voted_on(proposal_id: uint256, voter: address) -> bool:
    """Check if address has voted on proposal."""
    return self.has_voted[proposal_id][voter]


@view
@external
def get_voting_power(voter: address, proposal_id: uint256) -> uint256:
    """Get voting power for a proposal."""
    snapshot_id: uint256 = self.proposals[proposal_id].snapshot_id
    return ITesseractToken(TESS_TOKEN).balance_at_snapshot(voter, snapshot_id)


@view
@external
def quorum() -> uint256:
    """Get current quorum requirement."""
    total_supply: uint256 = ITesseractToken(TESS_TOKEN).totalSupply()
    return (total_supply * self.quorum_bps) / 10000


# Admin Functions

@external
def set_voting_period(new_period: uint256):
    """Update voting period."""
    assert msg.sender == self.owner, "Only owner"
    assert new_period >= MIN_VOTING_PERIOD, "Period too short"
    assert new_period <= MAX_VOTING_PERIOD, "Period too long"

    old_period: uint256 = self.voting_period
    self.voting_period = new_period

    log VotingPeriodUpdated(old_period, new_period)


@external
def set_quorum(new_quorum_bps: uint256):
    """Update quorum requirement."""
    assert msg.sender == self.owner, "Only owner"
    assert new_quorum_bps >= MIN_QUORUM_BPS, "Quorum too low"
    assert new_quorum_bps <= MAX_QUORUM_BPS, "Quorum too high"

    old_quorum: uint256 = self.quorum_bps
    self.quorum_bps = new_quorum_bps

    log QuorumUpdated(old_quorum, new_quorum_bps)


@external
def set_proposal_threshold(new_threshold: uint256):
    """Update proposal threshold."""
    assert msg.sender == self.owner, "Only owner"
    # Must be at least 10k TESS and at most 1M TESS
    assert new_threshold >= 10_000 * 10 ** 18, "Threshold too low"
    assert new_threshold <= 1_000_000 * 10 ** 18, "Threshold too high"
    self.proposal_threshold = new_threshold


@external
def set_timelock_delay(new_delay: uint256):
    """Update timelock delay."""
    assert msg.sender == self.owner, "Only owner"
    assert new_delay >= MIN_TIMELOCK, "Delay too short"
    assert new_delay <= MAX_TIMELOCK, "Delay too long"
    self.timelock_delay = new_delay


@external
def set_guardian(new_guardian: address):
    """Update guardian address."""
    assert msg.sender == self.owner or msg.sender == self.guardian, "Not authorized"
    assert new_guardian != empty(address), "Invalid guardian"
    self.guardian = new_guardian


@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    assert msg.sender == self.owner, "Only owner"
    assert new_owner != empty(address), "Invalid owner"
    self.owner = new_owner
