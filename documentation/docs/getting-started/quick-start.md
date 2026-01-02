# Quick Start

Get Tesseract running in under 5 minutes.

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** - [Download Python](https://python.org)
- **Poetry** - [Install Poetry](https://python-poetry.org/docs/#installation)
- **Git** - [Install Git](https://git-scm.com/)

---

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/tesseract.git
cd tesseract

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

---

## Step 2: Verify Installation

Test that the contract compiles successfully:

```bash
poetry run python scripts/test_compilation.py
```

Expected output:

```
Compiling TesseractSimple.vy...
Compilation successful!
Bytecode length: 7,276 bytes
ABI contains 18 items
All tests passed!
```

---

## Step 3: Run Tests

Execute the test suite:

```bash
# Run all tests
poetry run pytest tests/

# Run with verbose output
poetry run pytest tests/ -v
```

---

## Step 4: Deploy Locally

Deploy to a local blockchain (requires a running node):

```bash
poetry run python scripts/deploy_simple.py
```

!!! tip "Local Development"
    For local testing, you can use [Anvil](https://book.getfoundry.sh/anvil/) or [Ganache](https://trufflesuite.com/ganache/) as your local blockchain.

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

??? question "Poetry not found"
    Install Poetry using the official installer:
    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    ```

??? question "Python version mismatch"
    Tesseract requires Python 3.11+. Check your version:
    ```bash
    python --version
    ```

??? question "Vyper compilation errors"
    Ensure Vyper 0.3.10 is installed:
    ```bash
    poetry run python -c "import vyper; print(vyper.__version__)"
    ```

Need more help? Check the [Troubleshooting Guide](../guides/troubleshooting.md) or [open an issue](https://github.com/your-org/tesseract/issues).
