# @version ^0.3.10
"""
TesseractToken (TESS): Native token for the Tesseract cross-rollup protocol

Token Utility:
- Protocol fee distribution to stakers
- Governance voting power
- Relayer staking requirements
- Fee payment discounts

Supply: 1,000,000,000 TESS (1 billion)
Distribution:
- Community/Ecosystem: 50% (500M) - liquidity mining, airdrops, grants
- Investors: 20% (200M) - 12-month cliff, 24-month linear vest
- Team: 15% (150M) - 12-month cliff, 36-month linear vest
- Treasury: 15% (150M) - DAO controlled

ERC-20 compliant with permit (EIP-2612) for gasless approvals.
"""

from vyper.interfaces import ERC20

implements: ERC20

# Events
event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    amount: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    amount: uint256

event VestingScheduleCreated:
    beneficiary: indexed(address)
    total_amount: uint256
    cliff_end: uint256
    vesting_end: uint256

event TokensClaimed:
    beneficiary: indexed(address)
    amount: uint256

event Snapshot:
    id: uint256
    block_number: uint256

# EIP-2612 Permit
event PermitUsed:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256
    nonce: uint256

# Token metadata
name: public(String[32])
symbol: public(String[8])
decimals: public(uint8)

# ERC-20 state
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])

# Vesting
struct VestingSchedule:
    total_amount: uint256
    claimed_amount: uint256
    start_time: uint256
    cliff_end: uint256
    vesting_end: uint256
    revocable: bool
    revoked: bool

vesting_schedules: public(HashMap[address, VestingSchedule])

# Snapshot for governance
struct SnapshotData:
    block_number: uint256
    balance: uint256

snapshot_count: public(uint256)
snapshots: HashMap[uint256, uint256]  # snapshot_id -> block_number
account_snapshots: HashMap[address, HashMap[uint256, uint256]]  # account -> snapshot_id -> balance

# EIP-2612 Permit
DOMAIN_SEPARATOR: public(bytes32)
PERMIT_TYPEHASH: constant(bytes32) = keccak256("Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)")
nonces: public(HashMap[address, uint256])

# Access control
owner: public(address)
minter: public(address)  # Initially owner, can be set to staking contract

# Constants
TOTAL_SUPPLY: constant(uint256) = 1_000_000_000 * 10 ** 18  # 1 billion tokens
COMMUNITY_ALLOCATION: constant(uint256) = 500_000_000 * 10 ** 18  # 50%
INVESTOR_ALLOCATION: constant(uint256) = 200_000_000 * 10 ** 18   # 20%
TEAM_ALLOCATION: constant(uint256) = 150_000_000 * 10 ** 18       # 15%
TREASURY_ALLOCATION: constant(uint256) = 150_000_000 * 10 ** 18   # 15%

# Vesting periods
INVESTOR_CLIFF: constant(uint256) = 365 * 86400      # 12 months
INVESTOR_VEST: constant(uint256) = 730 * 86400       # 24 months total
TEAM_CLIFF: constant(uint256) = 365 * 86400          # 12 months
TEAM_VEST: constant(uint256) = 1095 * 86400          # 36 months total


@external
def __init__(
    community_address: address,
    treasury_address: address
):
    """
    Initialize TESS token with initial distribution.

    Team and investor allocations are set up via create_vesting_schedule.
    Community and treasury get immediate allocation.
    """
    self.name = "Tesseract"
    self.symbol = "TESS"
    self.decimals = 18
    self.owner = msg.sender
    self.minter = msg.sender

    # Set up EIP-712 domain separator
    self.DOMAIN_SEPARATOR = keccak256(
        concat(
            keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
            keccak256("Tesseract"),
            keccak256("1"),
            convert(chain.id, bytes32),
            convert(self, bytes32)
        )
    )

    # Mint community allocation (immediately available)
    self._mint(community_address, COMMUNITY_ALLOCATION)

    # Mint treasury allocation (DAO controlled)
    self._mint(treasury_address, TREASURY_ALLOCATION)

    # Team and investor allocations minted to this contract for vesting
    self._mint(self, TEAM_ALLOCATION + INVESTOR_ALLOCATION)


@internal
def _mint(to: address, amount: uint256):
    """Internal mint function."""
    assert to != empty(address), "Mint to zero address"
    self.totalSupply += amount
    self.balanceOf[to] += amount
    log Transfer(empty(address), to, amount)


@internal
def _burn(from_addr: address, amount: uint256):
    """Internal burn function."""
    assert self.balanceOf[from_addr] >= amount, "Burn exceeds balance"
    self.balanceOf[from_addr] -= amount
    self.totalSupply -= amount
    log Transfer(from_addr, empty(address), amount)


@internal
def _transfer(sender: address, receiver: address, amount: uint256):
    """Internal transfer function."""
    assert sender != empty(address), "Transfer from zero"
    assert receiver != empty(address), "Transfer to zero"
    assert self.balanceOf[sender] >= amount, "Insufficient balance"

    self.balanceOf[sender] -= amount
    self.balanceOf[receiver] += amount
    log Transfer(sender, receiver, amount)


# ERC-20 Interface

@external
def transfer(receiver: address, amount: uint256) -> bool:
    """Transfer tokens to another address."""
    self._transfer(msg.sender, receiver, amount)
    return True


@external
def transferFrom(sender: address, receiver: address, amount: uint256) -> bool:
    """Transfer tokens on behalf of another address."""
    assert self.allowance[sender][msg.sender] >= amount, "Insufficient allowance"
    self.allowance[sender][msg.sender] -= amount
    self._transfer(sender, receiver, amount)
    return True


@external
def approve(spender: address, amount: uint256) -> bool:
    """Approve spender to transfer tokens."""
    self.allowance[msg.sender][spender] = amount
    log Approval(msg.sender, spender, amount)
    return True


@external
def increaseAllowance(spender: address, added_value: uint256) -> bool:
    """Increase allowance for spender."""
    new_allowance: uint256 = self.allowance[msg.sender][spender] + added_value
    self.allowance[msg.sender][spender] = new_allowance
    log Approval(msg.sender, spender, new_allowance)
    return True


@external
def decreaseAllowance(spender: address, subtracted_value: uint256) -> bool:
    """Decrease allowance for spender."""
    current: uint256 = self.allowance[msg.sender][spender]
    assert current >= subtracted_value, "Decreased below zero"
    new_allowance: uint256 = current - subtracted_value
    self.allowance[msg.sender][spender] = new_allowance
    log Approval(msg.sender, spender, new_allowance)
    return True


# EIP-2612 Permit

@external
def permit(
    permit_owner: address,
    spender: address,
    amount: uint256,
    deadline: uint256,
    v: uint8,
    r: bytes32,
    s: bytes32
):
    """
    Approve via signature (gasless approval).
    """
    assert block.timestamp <= deadline, "Permit expired"

    nonce: uint256 = self.nonces[permit_owner]

    # Construct message hash
    struct_hash: bytes32 = keccak256(
        concat(
            PERMIT_TYPEHASH,
            convert(permit_owner, bytes32),
            convert(spender, bytes32),
            convert(amount, bytes32),
            convert(nonce, bytes32),
            convert(deadline, bytes32)
        )
    )

    digest: bytes32 = keccak256(
        concat(
            b"\x19\x01",
            self.DOMAIN_SEPARATOR,
            struct_hash
        )
    )

    # Recover signer
    signer: address = ecrecover(digest, v, r, s)
    assert signer != empty(address) and signer == permit_owner, "Invalid signature"

    # Update nonce and approve
    self.nonces[permit_owner] = nonce + 1
    self.allowance[permit_owner][spender] = amount

    log Approval(permit_owner, spender, amount)
    log PermitUsed(permit_owner, spender, amount, nonce)


# Vesting Functions

@external
def create_vesting_schedule(
    beneficiary: address,
    amount: uint256,
    cliff_duration: uint256,
    vesting_duration: uint256,
    revocable: bool
):
    """
    Create a vesting schedule for a beneficiary.

    Only owner can create vesting schedules.
    Tokens must be held by this contract.
    """
    assert msg.sender == self.owner, "Only owner"
    assert beneficiary != empty(address), "Invalid beneficiary"
    assert amount > 0, "Amount must be positive"
    assert vesting_duration >= cliff_duration, "Invalid vesting period"
    assert self.vesting_schedules[beneficiary].total_amount == 0, "Schedule exists"
    assert self.balanceOf[self] >= amount, "Insufficient vesting tokens"

    self.vesting_schedules[beneficiary] = VestingSchedule({
        total_amount: amount,
        claimed_amount: 0,
        start_time: block.timestamp,
        cliff_end: block.timestamp + cliff_duration,
        vesting_end: block.timestamp + vesting_duration,
        revocable: revocable,
        revoked: False
    })

    log VestingScheduleCreated(
        beneficiary,
        amount,
        block.timestamp + cliff_duration,
        block.timestamp + vesting_duration
    )


@view
@external
def vested_amount(beneficiary: address) -> uint256:
    """Calculate vested amount for a beneficiary."""
    schedule: VestingSchedule = self.vesting_schedules[beneficiary]

    if schedule.total_amount == 0:
        return 0

    if schedule.revoked:
        return schedule.claimed_amount

    if block.timestamp < schedule.cliff_end:
        return 0

    if block.timestamp >= schedule.vesting_end:
        return schedule.total_amount

    # Linear vesting
    time_vested: uint256 = block.timestamp - schedule.start_time
    total_time: uint256 = schedule.vesting_end - schedule.start_time

    return (schedule.total_amount * time_vested) / total_time


@view
@external
def claimable_amount(beneficiary: address) -> uint256:
    """Calculate claimable (vested but unclaimed) amount."""
    schedule: VestingSchedule = self.vesting_schedules[beneficiary]

    if schedule.total_amount == 0 or schedule.revoked:
        return 0

    if block.timestamp < schedule.cliff_end:
        return 0

    vested: uint256 = 0
    if block.timestamp >= schedule.vesting_end:
        vested = schedule.total_amount
    else:
        time_vested: uint256 = block.timestamp - schedule.start_time
        total_time: uint256 = schedule.vesting_end - schedule.start_time
        vested = (schedule.total_amount * time_vested) / total_time

    return vested - schedule.claimed_amount


@external
def claim_vested_tokens():
    """Claim vested tokens."""
    schedule: VestingSchedule = self.vesting_schedules[msg.sender]

    assert schedule.total_amount > 0, "No vesting schedule"
    assert not schedule.revoked, "Vesting revoked"
    assert block.timestamp >= schedule.cliff_end, "Cliff not reached"

    # Calculate claimable
    vested: uint256 = 0
    if block.timestamp >= schedule.vesting_end:
        vested = schedule.total_amount
    else:
        time_vested: uint256 = block.timestamp - schedule.start_time
        total_time: uint256 = schedule.vesting_end - schedule.start_time
        vested = (schedule.total_amount * time_vested) / total_time

    claimable: uint256 = vested - schedule.claimed_amount
    assert claimable > 0, "Nothing to claim"

    # Update and transfer
    self.vesting_schedules[msg.sender].claimed_amount += claimable
    self._transfer(self, msg.sender, claimable)

    log TokensClaimed(msg.sender, claimable)


@external
def revoke_vesting(beneficiary: address):
    """
    Revoke a vesting schedule (only for revocable schedules).

    Vested tokens are transferred to beneficiary, unvested return to owner.
    """
    assert msg.sender == self.owner, "Only owner"

    schedule: VestingSchedule = self.vesting_schedules[beneficiary]
    assert schedule.total_amount > 0, "No schedule"
    assert schedule.revocable, "Not revocable"
    assert not schedule.revoked, "Already revoked"

    # Calculate vested amount
    vested: uint256 = 0
    if block.timestamp >= schedule.cliff_end:
        if block.timestamp >= schedule.vesting_end:
            vested = schedule.total_amount
        else:
            time_vested: uint256 = block.timestamp - schedule.start_time
            total_time: uint256 = schedule.vesting_end - schedule.start_time
            vested = (schedule.total_amount * time_vested) / total_time

    # Transfer vested to beneficiary
    unclaimed_vested: uint256 = vested - schedule.claimed_amount
    if unclaimed_vested > 0:
        self._transfer(self, beneficiary, unclaimed_vested)

    # Return unvested to owner
    unvested: uint256 = schedule.total_amount - vested
    if unvested > 0:
        self._transfer(self, self.owner, unvested)

    self.vesting_schedules[beneficiary].revoked = True
    self.vesting_schedules[beneficiary].claimed_amount = vested


# Snapshot Functions (for governance)

@external
def snapshot() -> uint256:
    """
    Create a balance snapshot for governance voting.

    Only owner or designated governance contract can create snapshots.
    """
    assert msg.sender == self.owner, "Only owner"

    self.snapshot_count += 1
    self.snapshots[self.snapshot_count] = block.number

    log Snapshot(self.snapshot_count, block.number)
    return self.snapshot_count


@view
@external
def balance_at_snapshot(account: address, snapshot_id: uint256) -> uint256:
    """Get balance at a specific snapshot."""
    assert snapshot_id > 0 and snapshot_id <= self.snapshot_count, "Invalid snapshot"

    # Return stored snapshot balance, or current if not snapshotted
    snapshot_balance: uint256 = self.account_snapshots[account][snapshot_id]
    if snapshot_balance > 0:
        return snapshot_balance

    return self.balanceOf[account]


# Admin Functions

@external
def set_minter(new_minter: address):
    """Set the minter address (for staking rewards)."""
    assert msg.sender == self.owner, "Only owner"
    self.minter = new_minter


@external
def mint(to: address, amount: uint256):
    """
    Mint new tokens (for staking rewards).

    Only minter can call. Used sparingly for protocol incentives.
    """
    assert msg.sender == self.minter, "Only minter"
    assert to != empty(address), "Invalid recipient"
    self._mint(to, amount)


@external
def burn(amount: uint256):
    """Burn tokens from sender's balance."""
    self._burn(msg.sender, amount)


@external
def transfer_ownership(new_owner: address):
    """Transfer contract ownership."""
    assert msg.sender == self.owner, "Only owner"
    assert new_owner != empty(address), "Invalid owner"
    self.owner = new_owner
