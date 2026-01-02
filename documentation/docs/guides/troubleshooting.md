# Troubleshooting

Common issues and solutions for Tesseract.

---

## Quick Diagnostics

### Check Contract Status

```python
def diagnose(contract):
    """Run diagnostics on contract."""

    print("=== Tesseract Diagnostics ===\n")

    # Basic info
    print(f"Contract: {contract.address}")
    print(f"Owner: {contract.functions.owner().call()}")
    print(f"Transaction count: {contract.functions.transaction_count().call()}")
    print(f"Coordination window: {contract.functions.coordination_window().call()}s")

    # Check for paused state
    try:
        paused = contract.functions.paused().call()
        print(f"Paused: {paused}")
    except:
        print("Paused: N/A")

    print()
```

---

## Installation Issues

??? question "Poetry not found"
    **Problem:** `poetry: command not found`

    **Solution:**
    ```bash
    # Install Poetry
    curl -sSL https://install.python-poetry.org | python3 -

    # Add to PATH
    export PATH="$HOME/.local/bin:$PATH"
    ```

??? question "Python version mismatch"
    **Problem:** `Python ^3.11 is required`

    **Solution:**
    ```bash
    # Check version
    python --version

    # Install Python 3.11+
    # On Ubuntu:
    sudo apt install python3.11

    # Configure Poetry to use it
    poetry env use python3.11
    ```

??? question "Vyper compilation fails"
    **Problem:** Import errors or compilation errors

    **Solution:**
    ```bash
    # Verify Vyper version
    poetry run python -c "import vyper; print(vyper.__version__)"

    # Should be 0.3.10
    # If not, reinstall:
    poetry add vyper@0.3.10
    ```

---

## Deployment Issues

??? question "Transaction underpriced"
    **Problem:** `replacement transaction underpriced`

    **Solution:**
    ```python
    # Increase gas price
    tx = contract.functions.method().build_transaction({
        'gasPrice': w3.eth.gas_price * 2,  # Double gas price
        'nonce': w3.eth.get_transaction_count(account, 'pending')
    })
    ```

??? question "Out of gas"
    **Problem:** `out of gas` or transaction reverts

    **Solution:**
    ```python
    # Increase gas limit
    tx = contract.functions.buffer_transaction(...).build_transaction({
        'gas': 300000,  # Higher limit
    })

    # Or estimate first
    estimated = contract.functions.buffer_transaction(...).estimate_gas()
    tx = contract.functions.buffer_transaction(...).build_transaction({
        'gas': int(estimated * 1.2)  # 20% buffer
    })
    ```

??? question "Nonce too low"
    **Problem:** `nonce too low`

    **Solution:**
    ```python
    # Get pending nonce
    nonce = w3.eth.get_transaction_count(account.address, 'pending')

    tx = contract.functions.method().build_transaction({
        'nonce': nonce
    })
    ```

??? question "Insufficient funds"
    **Problem:** `insufficient funds for gas * price + value`

    **Solution:**
    ```python
    # Check balance
    balance = w3.eth.get_balance(account.address)
    print(f"Balance: {balance / 1e18} ETH")

    # Get testnet funds from faucet
    ```

---

## Contract Errors

??? question "Not authorized"
    **Problem:** Transaction reverts with `Not authorized`

    **Solution:**
    ```python
    # Check if address is operator
    is_operator = contract.functions.authorized_operators(address).call()
    print(f"Is operator: {is_operator}")

    # Add as operator (as owner)
    contract.functions.add_operator(address).transact({'from': owner})
    ```

??? question "Transaction already exists"
    **Problem:** `Transaction already exists`

    **Solution:**
    ```python
    # Use unique transaction ID
    import hashlib
    import time

    # Generate unique ID
    data = f"{origin}{target}{time.time()}".encode()
    tx_id = hashlib.sha256(data).digest()
    ```

??? question "Timestamp cannot be in the past"
    **Problem:** `Timestamp cannot be in the past`

    **Solution:**
    ```python
    import time

    # Use future timestamp
    timestamp = int(time.time()) + 60  # 1 minute from now
    ```

??? question "Transaction not in buffered state"
    **Problem:** `Transaction not in buffered state`

    **Solution:**
    ```python
    # Check current state
    state = contract.functions.get_transaction_state(tx_id).call()
    print(f"State: {state}")  # 0=EMPTY, 1=BUFFERED, 2=READY, 3=EXECUTED

    # Only BUFFERED transactions can be resolved
    ```

??? question "Transaction not ready"
    **Problem:** `Transaction not ready`

    **Solution:**
    ```python
    # Check if ready
    is_ready = contract.functions.is_transaction_ready(tx_id).call()
    print(f"Ready: {is_ready}")

    # Resolve dependencies first
    contract.functions.resolve_dependency(tx_id).transact()
    ```

---

## Resolution Issues

??? question "Dependency not satisfied"
    **Problem:** Transaction fails resolution with `Dependency not satisfied`

    **Solution:**
    ```python
    # Check dependency status
    details = contract.functions.get_transaction_details(tx_id).call()
    dependency_id = details[2]

    dep_state = contract.functions.get_transaction_state(dependency_id).call()
    print(f"Dependency state: {dep_state}")

    # Resolve dependency first
    if dep_state == 1:  # BUFFERED
        contract.functions.resolve_dependency(dependency_id).transact()
    ```

??? question "Transaction expired"
    **Problem:** Transaction fails with `Transaction expired`

    **Solution:**
    ```python
    # Check coordination window
    window = contract.functions.coordination_window().call()
    print(f"Window: {window}s")

    # Get transaction timestamp
    details = contract.functions.get_transaction_details(tx_id).call()
    timestamp = details[3]

    # Check if within window
    current = int(time.time())
    if current > timestamp + window:
        print("Transaction has expired, create new one")
    ```

---

## Network Issues

??? question "Cannot connect to RPC"
    **Problem:** Connection refused or timeout

    **Solution:**
    ```python
    # Test connection
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider('YOUR_RPC_URL'))
    print(f"Connected: {w3.is_connected()}")
    print(f"Block: {w3.eth.block_number}")

    # Try alternative RPC endpoints
    # - Infura: https://mainnet.infura.io/v3/YOUR_KEY
    # - Alchemy: https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
    # - Public: https://rpc.ankr.com/eth
    ```

??? question "Rate limited"
    **Problem:** `429 Too Many Requests`

    **Solution:**
    ```python
    import time

    # Add delays between requests
    time.sleep(0.1)

    # Use paid RPC tier for higher limits
    # Or run your own node
    ```

---

## Event Issues

??? question "Missing events"
    **Problem:** Events not appearing in filter

    **Solution:**
    ```python
    # Check fromBlock
    filter = contract.events.TransactionBuffered.createFilter(
        fromBlock=0  # Start from beginning
    )

    # Get all historical events
    events = filter.get_all_entries()
    print(f"Found {len(events)} events")
    ```

??? question "Filter not supported"
    **Problem:** `filter not found` or filter errors

    **Solution:**
    ```python
    # Use getLogs instead of filters
    events = contract.events.TransactionBuffered.getLogs(
        fromBlock=start_block,
        toBlock='latest'
    )

    # Or use WebSocket provider
    w3 = Web3(Web3.WebsocketProvider('wss://...'))
    ```

---

## Debug Commands

### Check Transaction Details

```python
def debug_transaction(contract, tx_id):
    """Print transaction debug info."""

    print(f"Transaction: {tx_id.hex()}")

    # Get state
    state = contract.functions.get_transaction_state(tx_id).call()
    state_names = ['EMPTY', 'BUFFERED', 'READY', 'EXECUTED']
    print(f"State: {state_names[state]}")

    if state == 0:
        print("Transaction does not exist")
        return

    # Get details
    details = contract.functions.get_transaction_details(tx_id).call()
    origin, target, dependency, timestamp, _ = details

    print(f"Origin: {origin}")
    print(f"Target: {target}")
    print(f"Dependency: {dependency.hex()}")
    print(f"Timestamp: {timestamp}")

    # Check timing
    window = contract.functions.coordination_window().call()
    current = int(time.time())
    expires = timestamp + window

    print(f"Current time: {current}")
    print(f"Expires: {expires}")
    print(f"Expired: {current > expires}")

    # Check dependency
    if dependency != b'\x00' * 32:
        dep_state = contract.functions.get_transaction_state(dependency).call()
        print(f"Dependency state: {state_names[dep_state]}")
```

### Test Full Workflow

```python
def test_full_workflow(contract, operator):
    """Test complete transaction lifecycle."""

    tx_id = b'\xff' * 32  # Test ID

    print("1. Buffering transaction...")
    try:
        contract.functions.buffer_transaction(
            tx_id,
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            b"test",
            b'\x00' * 32,
            int(time.time()) + 10
        ).transact({'from': operator})
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        return

    print("2. Waiting for timestamp...")
    time.sleep(12)
    print("   OK")

    print("3. Resolving dependency...")
    try:
        contract.functions.resolve_dependency(tx_id).transact({'from': operator})
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        return

    print("4. Checking readiness...")
    is_ready = contract.functions.is_transaction_ready(tx_id).call()
    print(f"   Ready: {is_ready}")

    print("5. Marking executed...")
    try:
        contract.functions.mark_executed(tx_id).transact({'from': operator})
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        return

    print("\nWorkflow completed successfully!")
```

---

## Getting Help

If you're still stuck:

1. Check the [GitHub Issues](https://github.com/your-org/tesseract/issues)
2. Search existing issues for similar problems
3. Create a new issue with:
   - Error message
   - Steps to reproduce
   - Environment details (Python version, network, etc.)
   - Relevant code snippets

---

## Next Steps

- [Deployment Guide](deployment.md) - Proper deployment
- [Monitoring](monitoring.md) - Set up monitoring
- [API Reference](../api/contract-api.md) - Contract details
