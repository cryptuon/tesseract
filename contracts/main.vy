from vyper.interfaces import ERC20

# Event to signal that a transaction is buffered with a dependency and timestamp
event TransactionBuffered:
    tx_id: indexed(bytes32)
    origin_rollup: indexed(address)
    target_rollup: indexed(address)
    dependency_tx_id: bytes32
    timestamp: uint256

# Event to signal that a transaction is ready to be executed
event TransactionReady:
    tx_id: indexed(bytes32)

# Struct to hold transaction details
struct BufferedTransaction:
    origin_rollup: address
    target_rollup: address
    payload: String[1024]
    dependency_tx_id: bytes32
    timestamp: uint256
    is_ready: bool

# Mapping of transaction ids to their buffered transactions
buffered_transactions: HashMap[bytes32, BufferedTransaction]

@external
def buffer_transaction(tx_id: bytes32, origin_rollup: address, target_rollup: address, payload: String[1024], dependency_tx_id: bytes32, timestamp: uint256):
    """
    Buffer a new transaction with a dependency and timestamp
    """
    assert self.buffered_transactions[tx_id].origin_rollup == ZERO_ADDRESS, "Transaction already exists"
    self.buffered_transactions[tx_id] = BufferedTransaction({
        origin_rollup: origin_rollup,
        target_rollup: target_rollup,
        payload: payload,
        dependency_tx_id: dependency_tx_id,
        timestamp: timestamp,
        is_ready: False
    })
    log TransactionBuffered(tx_id, origin_rollup, target_rollup, dependency_tx_id, timestamp)

@external
def resolve_dependency(tx_id: bytes32):
    """
    Resolve a dependency for a buffered transaction, making it ready for execution
    """
    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
    assert buffered_tx.origin_rollup != ZERO_ADDRESS, "Transaction does not exist"
    
    # Check if the dependency has been resolved and if the timestamps are within the acceptable range
    dependency_tx: BufferedTransaction = self.buffered_transactions[buffered_tx.dependency_tx_id]
    current_time: uint256 = block.timestamp
    is_dependency_resolved: bool = dependency_tx.is_ready and current_time >= buffered_tx.timestamp
    is_within_time_frame: bool = current_time <= (buffered_tx.timestamp + 30)  # <30s the acceptable time range for the transaction to be considered concurrent

    if is_dependency_resolved and is_within_time_frame:
        buffered_tx.is_ready = True
        log TransactionReady(tx_id)
    else:
        raise("Dependency not resolved or timestamp not within range.")

@view
@external
def is_transaction_ready(tx_id: bytes32) -> bool:
    """
    Check if a buffered transaction is ready for execution based on dependency and timestamp
    """
    buffered_tx: BufferedTransaction = self.buffered_transactions[tx_id]
    return buffered_tx.is_ready and (block.timestamp >= buffered_tx.timestamp)
