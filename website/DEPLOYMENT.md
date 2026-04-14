# Tesseract Demo Deployment Guide

This guide covers deploying the Tesseract website with an embedded relayer node that connects to real testnets.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
├─────────────────────────────────────────────┤
│  Website (Nginx) ──> Relayer ──> PostgreSQL │
│       :80              :8080       :5432    │
│         │                │                  │
│         │                ▼                  │
│         │        Sepolia Testnet            │
│         │       (via public RPC)            │
└─────────────────────────────────────────────┘
```

## Prerequisites

1. **Docker & Docker Compose** installed
2. **Sepolia ETH** for the relayer wallet (gas fees)
3. **Deployed contracts** on Sepolia testnet

## Step 1: Deploy Smart Contracts

First, deploy the Tesseract contracts to Sepolia:

```bash
# From the project root
cd /path/to/tesseract

# Create a .env file with your deployer private key
echo "DEPLOYER_PRIVATE_KEY=0x..." > .env

# Deploy to Sepolia
uv run python scripts/deploy_simple.py sepolia
```

Save the deployed contract addresses:
- `TesseractBuffer`: 0x...
- `AtomicSwapCoordinator`: 0x...

## Step 2: Get Test ETH

Get Sepolia ETH for the relayer wallet from a faucet:

- https://sepoliafaucet.com
- https://www.alchemy.com/faucets/ethereum-sepolia
- https://faucet.quicknode.com/ethereum/sepolia

The relayer needs ~0.1 ETH for gas fees.

## Step 3: Configure Environment

```bash
cd website
cp .env.example .env
```

Edit `.env` with your values:

```bash
# Relayer wallet private key (needs Sepolia ETH)
RELAYER_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE

# Contract addresses from Step 1
TESSERACT_BUFFER_ADDRESS=0xYOUR_BUFFER_ADDRESS
COORDINATOR_ADDRESS=0xYOUR_COORDINATOR_ADDRESS

# Optional
POSTGRES_PASSWORD=tesseract
```

## Step 4: Build and Run Locally

```bash
# Build all services
docker-compose build

# Start the stack
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify health
curl http://localhost/api/health
curl http://localhost/api/ready
```

Open http://localhost in your browser. The dashboard should show "Connected".

## Step 5: Deploy to CapRover

### Option A: Using CapRover CLI

```bash
# Install CapRover CLI
npm install -g caprover

# Login to your CapRover instance
caprover login

# Deploy
caprover deploy
```

### Option B: Using Git Push

1. Add the CapRover remote:
   ```bash
   git remote add caprover captain@your-server.com:tesseract-demo
   ```

2. Push to deploy:
   ```bash
   git push caprover main
   ```

### Set Environment Variables in CapRover

In the CapRover dashboard, set these environment variables:

| Variable | Value |
|----------|-------|
| `RELAYER_PRIVATE_KEY` | Your relayer wallet private key |
| `TESSERACT_BUFFER_ADDRESS` | Deployed TesseractBuffer address |
| `COORDINATOR_ADDRESS` | Deployed AtomicSwapCoordinator address |
| `POSTGRES_PASSWORD` | Your database password |

## Troubleshooting

### Dashboard shows "Disconnected"

1. Check relayer logs:
   ```bash
   docker-compose logs relayer
   ```

2. Verify database is running:
   ```bash
   docker-compose logs postgres
   ```

3. Check API health:
   ```bash
   curl http://localhost/api/health
   ```

### Relayer can't connect to chain

1. Verify RPC endpoints are accessible
2. Check contract addresses are correct
3. Ensure relayer wallet has ETH for gas

### Database connection failed

1. Wait for PostgreSQL to fully start (30+ seconds)
2. Check PostgreSQL logs:
   ```bash
   docker-compose logs postgres
   ```

## Monitoring

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f relayer
```

### Check Stats
```bash
# Transaction statistics
curl http://localhost/api/stats

# Chain status
curl http://localhost/api/ready

# Relayer version
curl http://localhost/api/health
```

## Enabling Additional Chains

Edit `relayer-config/demo.toml` to enable more chains:

```toml
[chains.polygon_amoy]
# ... other config ...
enabled = true  # Change from false to true
```

Make sure to:
1. Deploy contracts to that chain
2. Update the contract addresses
3. Get native tokens for gas (MATIC for Polygon, etc.)

## Security Notes

- The `RELAYER_PRIVATE_KEY` should only hold minimal funds for gas
- Use environment variables, never commit private keys
- For production, consider using a hardware wallet or KMS
- The demo uses public RPCs which may be rate-limited

## Resource Requirements

| Service | CPU | Memory |
|---------|-----|--------|
| Website | 0.1 | 128MB |
| Relayer | 0.5 | 512MB |
| PostgreSQL | 0.2 | 256MB |

Total: ~1GB RAM recommended
