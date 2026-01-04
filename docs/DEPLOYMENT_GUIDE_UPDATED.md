# Tesseract Deployment Guide

## Overview

This guide covers deploying the Tesseract protocol (7 Vyper smart contracts) and the Rust relayer to testnet and production environments.

### Contracts to Deploy
1. `TesseractBuffer.vy` - Core transaction buffering
2. `AtomicSwapCoordinator.vy` - Swap order book
3. `TesseractToken.vy` - TESS governance token
4. `TesseractStaking.vy` - Staking with rewards
5. `FeeCollector.vy` - Protocol fee collection
6. `RelayerRegistry.vy` - Relayer management
7. `TesseractGovernor.vy` - On-chain governance

## Prerequisites

### System Requirements
- Python 3.11+
- Poetry (for dependency management)
- Git
- At least 2GB RAM

### Required Setup
- Testnet funds (for deployment)
- RPC provider API key (Alchemy recommended)

## Step 1: Environment Setup

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/tesseract.git
cd tesseract

# Install dependencies using uv
uv sync

# Verify installation
uv run python --version
uv run python -c "import vyper; print(f'Vyper: {vyper.__version__}')"
```

### Verify Contract Compilation

```bash
# Test contract compilation
uv run pytest tests/test_compilation.py -v

# Expected output: All tests pass
```

### Validate Environment

```bash
# Run environment setup check
uv run python scripts/setup_environment.py local
```

## Step 2: Testnet Setup (First Time)

### 2.1 Create Alchemy Account

1. Go to https://www.alchemy.com/
2. Create a free account
3. Create a new app:
   - Name: "Tesseract"
   - Chain: Ethereum
   - Network: Sepolia
4. Copy your API key from the dashboard

### 2.2 Get Testnet Funds

**Ethereum Sepolia:**
- Faucet: https://sepoliafaucet.com/
- Alchemy Faucet: https://www.alchemy.com/faucets/ethereum-sepolia
- Amount needed: ~0.05 ETH

**Polygon Amoy** (Mumbai deprecated):
- Faucet: https://faucet.polygon.technology/
- Amount needed: ~1 MATIC

### 2.3 Configure Environment

Create a `.env` file in the project root:

```bash
# .env file
DEPLOYER_PRIVATE_KEY=0x...your_private_key_here...
ALCHEMY_API_KEY=...your_alchemy_api_key...
```

**IMPORTANT**: Never commit your `.env` file to version control!

### 2.4 Validate Testnet Setup

```bash
# Check Sepolia configuration
uv run python scripts/setup_environment.py sepolia

# Expected output:
# [OK] .env file found
# [OK] Contract compiles successfully
# [OK] DEPLOYER_PRIVATE_KEY is configured
# [OK] ALCHEMY_API_KEY is configured
# [OK] Connected to Ethereum Sepolia
# [OK] Sufficient balance for deployment
```

## Step 3: Local Development Testing

### Start Local Network

```bash
# Option 1: Use Hardhat
npx hardhat node

# Option 2: Use Ganache
ganache-cli --deterministic --accounts 10 --host 0.0.0.0
```

### Deploy Locally

```bash
# Deploy to local network
uv run python scripts/deploy_simple.py local

# Expected output:
# Tesseract Deployment Script
# ================
# Target network: local
# Deploying to Local Hardhat...
# [OK] Contract deployed successfully!
```

### Verify Deployment

```bash
# Verify the deployment
uv run python scripts/verify_deployment.py local
```

## Step 4: Testnet Deployment

### Deploy to Sepolia

```bash
# Deploy to Ethereum Sepolia
uv run python scripts/deploy_simple.py sepolia

# Expected output:
# Deploying to Ethereum Sepolia...
# Connected to network (Chain ID: 11155111)
# Deployer: 0x...
# Balance: 0.05 ETH
# [OK] Contract deployed successfully!
# Contract address: 0x...
```

### Verify Deployment

```bash
# Verify on testnet
uv run python scripts/verify_deployment.py sepolia

# Check health
uv run python scripts/health_check.py sepolia
```

### Deploy to Polygon Amoy (Optional)

```bash
uv run python scripts/deploy_simple.py polygon_amoy
uv run python scripts/verify_deployment.py polygon_amoy
```

### Verify on Block Explorers

```bash
# Automated verification
uv run python scripts/verify_on_explorer.py sepolia

# Verify specific contract
uv run python scripts/verify_on_explorer.py sepolia --contract TesseractBuffer
```

## Step 5: Post-Deployment Operations

### Add Operators

```bash
# Add an operator
uv run python scripts/manage_operators.py sepolia add 0x...operator_address...

# Check operator roles
uv run python scripts/manage_operators.py sepolia check 0x...operator_address...

# List contract info
uv run python scripts/manage_operators.py sepolia list
```

### Monitor Events

```bash
# View historical events
uv run python scripts/monitor_events.py sepolia

# Watch for new events in real-time
uv run python scripts/monitor_events.py sepolia --watch
```

### Health Checks

```bash
# Run health check
uv run python scripts/health_check.py sepolia

# Get JSON output for automation
uv run python scripts/health_check.py sepolia json
```

## Step 6: Emergency Procedures

### Check Contract Status

```bash
uv run python scripts/emergency.py sepolia status
```

### Pause Contract (Emergency)

```bash
# Preview (no action)
uv run python scripts/emergency.py sepolia pause

# Execute pause
uv run python scripts/emergency.py sepolia pause --confirm
```

### Unpause Contract

```bash
uv run python scripts/emergency.py sepolia unpause --confirm
```

### Reset Circuit Breaker

```bash
uv run python scripts/emergency.py sepolia reset-cb --confirm
```

## Step 7: Contract Verification on Etherscan

1. Go to https://sepolia.etherscan.io/
2. Search for your contract address
3. Click "Contract" tab
4. Click "Verify and Publish"
5. Choose:
   - Compiler Type: Vyper
   - Compiler Version: 0.3.10
   - License: MIT
6. Paste your contract source code
7. Submit verification

## Available Scripts

| Script | Description |
|--------|-------------|
| `scripts/setup_environment.py` | Validate environment configuration |
| `scripts/deploy_simple.py` | Deploy to any network |
| `scripts/verify_deployment.py` | Verify deployed contract |
| `scripts/health_check.py` | Check contract health |
| `scripts/monitor_events.py` | Monitor contract events |
| `scripts/manage_operators.py` | Manage operator roles |
| `scripts/emergency.py` | Emergency procedures |

## Network Configuration

Network configurations are stored in `config/networks.json`:

```json
{
  "networks": {
    "local": {"chain_id": 31337, "name": "Local Hardhat"},
    "sepolia": {"chain_id": 11155111, "name": "Ethereum Sepolia"},
    "polygon_amoy": {"chain_id": 80002, "name": "Polygon Amoy"},
    "arbitrum_sepolia": {"chain_id": 421614, "name": "Arbitrum Sepolia"},
    "optimism_sepolia": {"chain_id": 11155420, "name": "Optimism Sepolia"},
    "base_sepolia": {"chain_id": 84532, "name": "Base Sepolia"}
  }
}
```

## Troubleshooting

### Cannot Connect to Network

```bash
# Check RPC connectivity
uv run python scripts/setup_environment.py sepolia
```

### Insufficient Balance

Get testnet funds from the faucets listed in Step 2.2.

### Transaction Reverted

Check the error message in the transaction receipt. Common issues:
- Insufficient gas
- Contract paused
- Invalid input parameters

### Deployment File Not Found

Ensure you've deployed to the network first:
```bash
uv run python scripts/deploy_simple.py <network>
```

## Security Checklist

### Pre-Deployment
- [ ] Contract compilation successful
- [ ] All tests pass (run `uv run pytest`)
- [ ] Private key secured (never committed to git)
- [ ] Environment variables configured

### Post-Deployment
- [ ] Contract address saved in `deployments/`
- [ ] Deployment verified (`verify_deployment.py`)
- [ ] Health check passing (`health_check.py`)
- [ ] Operators configured if needed

## Next Steps After Testnet

1. Run comprehensive tests on testnet
2. Monitor for any issues
3. Schedule professional security audit
4. Prepare mainnet deployment plan
5. Set up production monitoring

## Step 8: Relayer Deployment

### Build Relayer

```bash
cd relayer
cargo build --release
```

### Configure Relayer

Create `relayer/config/production.toml`:

```toml
[database]
url = "postgres://user:pass@localhost/tesseract"

[chains.sepolia]
chain_id = 11155111
rpc_urls = ["https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY"]
contract_address = "0x..."  # Deployed TesseractBuffer
confirmation_blocks = 32

[relayer]
max_retries = 3
retry_delay_ms = 1000
```

### Run Relayer

```bash
export RELAYER_PRIVATE_KEY="0x..."
export DATABASE_URL="postgres://..."
cargo run --release
```

### Deploy to AWS (Production)

```bash
cd infrastructure/terraform

# Initialize
terraform init -backend-config=environments/production/backend.tf

# Deploy
terraform apply -var-file=environments/production/terraform.tfvars
```

See `infrastructure/terraform/README.md` and `relayer/README.md` for detailed relayer deployment instructions.

---

This deployment guide covers the complete workflow from development to production deployment of the Tesseract protocol.
