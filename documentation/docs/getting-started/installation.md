# Installation

Complete installation guide for Tesseract development and deployment.

---

## System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required for Vyper compiler |
| uv | Latest | Python package manager |
| Vyper | 0.3.10 | Smart contract compiler |
| Git | 2.x+ | Version control |
| Rust | 1.75+ | Optional, for relayer development |
| Anvil | Latest | Optional, for local testing (via Foundry) |

---

## Installation Methods

### Using uv (Recommended)

```bash
# Clone repository
git clone https://github.com/cryptuon/tesseract.git
cd tesseract

# Install all dependencies
uv sync

# Verify installation
uv run python --version
uv run python -c "import vyper; print(f'Vyper: {vyper.__version__}')"
```

### Development Installation

For contributors:

```bash
# Install with extras (matches CONTRIBUTING.md workflow)
uv sync --all-extras
```

### Building the Rust Relayer (Optional)

```bash
cd relayer && cargo build --release
```

---

## Environment Configuration

### Create Environment File

```bash
# Copy the example environment file (if provided in repo)
cp .env.example .env 2>/dev/null || touch .env
```

### Configure Variables

Edit `.env` with your settings. Tesseract supports five networks (mainnet + testnet):

```bash
# Network RPC URLs - Testnets
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_API_KEY
POLYGON_AMOY_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_API_KEY
ARBITRUM_SEPOLIA_RPC_URL=https://arb-sepolia.g.alchemy.com/v2/YOUR_API_KEY
OPTIMISM_SEPOLIA_RPC_URL=https://opt-sepolia.g.alchemy.com/v2/YOUR_API_KEY
BASE_SEPOLIA_RPC_URL=https://base-sepolia.g.alchemy.com/v2/YOUR_API_KEY

# Deployment keys (NEVER commit these!)
PRIVATE_KEY=0x...
```

!!! danger "Security Warning"
    Never commit private keys to version control. For production, use AWS Secrets Manager (the reference infrastructure stack uses this for relayer keys).

---

## Verify Installation

### Check Dependencies

```bash
# List installed packages
uv pip list

# Check Vyper version
uv run python -c "import vyper; print(vyper.__version__)"
```

### Test Compilation

```bash
# Compile all 7 production contracts
uv run pytest tests/test_compilation.py -v
```

### Run Test Suite

```bash
# Execute all tests
uv run pytest tests/ -v
# Expected: 86 passed, 40 xfailed, 9 xpassed

# Run a specific test file
uv run pytest tests/test_tokenomics.py -v
```

---

## IDE Setup

### VS Code

Recommended extensions:

- **Python** - Microsoft Python extension
- **Vyper** - Vyper language support
- **rust-analyzer** - For the relayer (optional)

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
2. Configure interpreter: `Settings > Project > Python Interpreter`
3. Select the `.venv` created by `uv sync`

---

## Updating

```bash
# Pull latest changes
git pull origin main

# Update dependencies
uv sync

# Verify
uv run pytest tests/test_compilation.py -v
```

---

## Uninstalling

```bash
# Remove the uv-managed virtual environment
rm -rf .venv/
```

---

## Next Steps

- [Your First Transaction](first-transaction.md) - Create a cross-rollup transaction
- [Deployment Guide](../guides/deployment.md) - Deploy to testnets
- [API Reference](../api/contract-api.md) - Explore the contract API
