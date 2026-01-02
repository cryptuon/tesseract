# Installation

Complete installation guide for Tesseract development and deployment.

---

## System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required for Vyper compiler |
| Poetry | Latest | Dependency management |
| Git | 2.x+ | Version control |
| Node.js | 18+ | Optional, for additional tooling |

---

## Installation Methods

### Using Poetry (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/tesseract.git
cd tesseract

# Install all dependencies
poetry install

# Verify installation
poetry run python --version
poetry run python -c "import vyper; print(f'Vyper: {vyper.__version__}')"
```

### Development Installation

For contributors and developers:

```bash
# Install with development dependencies
poetry install --with dev

# Install pre-commit hooks (optional)
poetry run pre-commit install
```

---

## Environment Configuration

### Create Environment File

```bash
# Copy the example environment file
cp .env.example .env
```

### Configure Variables

Edit `.env` with your settings:

```bash
# Network RPC URLs
ETHEREUM_RPC_URL=https://sepolia.infura.io/v3/YOUR_API_KEY
POLYGON_RPC_URL=https://polygon-mumbai.infura.io/v3/YOUR_API_KEY
ARBITRUM_RPC_URL=https://arb-goerli.g.alchemy.com/v2/YOUR_API_KEY
OPTIMISM_RPC_URL=https://opt-goerli.g.alchemy.com/v2/YOUR_API_KEY

# Deployment keys (NEVER commit these!)
DEPLOYER_PRIVATE_KEY=0x...
OPERATOR_PRIVATE_KEY=0x...
```

!!! danger "Security Warning"
    Never commit private keys to version control. Use hardware wallets for production deployments.

---

## Verify Installation

### Check Dependencies

```bash
# Verify Python packages
poetry show

# Check Vyper version
poetry run vyper --version
```

### Test Compilation

```bash
# Compile the contract
poetry run python scripts/test_compilation.py
```

### Run Test Suite

```bash
# Execute all tests
poetry run pytest tests/ -v

# Run with coverage
poetry run pytest tests/ --cov=tesseract
```

---

## IDE Setup

### VS Code

Recommended extensions:

- **Python** - Microsoft Python extension
- **Vyper** - Vyper language support
- **Prettier** - Code formatting

Settings (`.vscode/settings.json`):

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter"
    }
}
```

### PyCharm

1. Open project folder
2. Configure Poetry interpreter: `Settings > Project > Python Interpreter`
3. Select existing Poetry environment

---

## Updating

To update Tesseract and dependencies:

```bash
# Pull latest changes
git pull origin main

# Update dependencies
poetry update

# Verify
poetry run python scripts/test_compilation.py
```

---

## Uninstalling

```bash
# Remove virtual environment
poetry env remove python

# Or remove manually
rm -rf .venv/
```

---

## Next Steps

- [Your First Transaction](first-transaction.md) - Create a cross-rollup transaction
- [Deployment Guide](../guides/deployment.md) - Deploy to testnets
- [API Reference](../api/contract-api.md) - Explore the contract API
