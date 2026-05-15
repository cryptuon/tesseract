# Quick Start

Get Tesseract running in under 5 minutes.

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** - [Download Python](https://python.org)
- **uv** - [Install uv](https://docs.astral.sh/uv/) (Python package manager)
- **Git** - [Install Git](https://git-scm.com/)

Optional:

- **Rust 1.75+** - For building the relayer
- **Anvil** - For local testing (install via [Foundry](https://book.getfoundry.sh/))

---

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/cryptuon/tesseract.git
cd tesseract

# Install dependencies
uv sync
```

---

## Step 2: Verify Installation

Test that all contracts compile successfully:

```bash
uv run pytest tests/test_compilation.py -v
```

The repository ships **7 production Vyper contracts**, plus a `TesseractSimple.vy` reference implementation. Compilation of all contracts is covered by the test suite.

You can also confirm the Vyper compiler version directly:

```bash
uv run python -c "import vyper; print(f'Vyper: {vyper.__version__}')"
```

---

## Step 3: Run Tests

Execute the full test suite (135 tests):

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific category
uv run pytest tests/test_compilation.py -v   # Contract compilation
uv run pytest tests/test_tokenomics.py -v    # Token, staking, governance
uv run pytest tests/test_defi_security.py -v # DeFi security features
```

---

## Step 4: Deploy

Deploy to a public testnet:

```bash
# Set environment
export PRIVATE_KEY="0x..."
export SEPOLIA_RPC_URL="https://eth-sepolia.g.alchemy.com/v2/..."

# Deploy
uv run python scripts/deploy_simple.py sepolia
```

!!! tip "Local Development"
    For local testing, use [Anvil](https://book.getfoundry.sh/anvil/) as your local blockchain.

---

## Next Steps

Now that you have Tesseract installed:

1. **[Installation Guide](installation.md)** - Detailed setup instructions
2. **[Your First Transaction](first-transaction.md)** - Create your first cross-rollup transaction
3. **[Core Concepts](../concepts/overview.md)** - Understand how Tesseract works
4. **[Deploy to Testnet](../guides/deployment.md)** - Go live on Sepolia

---

## Troubleshooting

### Common Issues

??? question "uv not found"
    Install uv using the official installer:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

??? question "Python version mismatch"
    Tesseract requires Python 3.11+. Check your version:
    ```bash
    python --version
    ```

??? question "Vyper compilation errors"
    Ensure Vyper 0.3.10 is installed:
    ```bash
    uv run python -c "import vyper; print(vyper.__version__)"
    ```

Need more help? Check the [Troubleshooting Guide](../guides/troubleshooting.md) or [open an issue](https://github.com/cryptuon/tesseract/issues).
