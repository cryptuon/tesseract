# Tesseract Terraform Infrastructure

AWS infrastructure for the Tesseract cross-chain relayer.

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              AWS Cloud                   │
                    │                                          │
    Internet ───────┤► ALB ──► ECS Fargate (Relayer)          │
                    │              │                           │
                    │              ▼                           │
                    │         RDS PostgreSQL                   │
                    │              │                           │
                    │              ▼                           │
                    │       Secrets Manager                    │
                    │                                          │
                    │   CloudWatch ◄── Prometheus Metrics      │
                    └─────────────────────────────────────────┘
```

## Components

- **VPC**: Multi-AZ with public, private, and database subnets
- **ECS Fargate**: Auto-scaling relayer containers (2-10 instances)
- **ALB**: Application load balancer with health checks
- **RDS PostgreSQL**: Multi-AZ in production, performance insights enabled
- **Secrets Manager**: Secure storage for API keys and private keys
- **CloudWatch**: Logs, metrics, and alarms

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.5.0
3. S3 bucket for state: `tesseract-terraform-state`
4. DynamoDB table for locks: `tesseract-terraform-locks`

### Create State Resources

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket tesseract-terraform-state \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket tesseract-terraform-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket tesseract-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

# Create DynamoDB table for locks
aws dynamodb create-table \
  --table-name tesseract-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

## Deployment

### Staging

```bash
cd infrastructure/terraform

# Initialize with staging backend
terraform init \
  -backend-config=environments/staging/backend.tf \
  -reconfigure

# Plan
terraform plan -var-file=environments/staging/terraform.tfvars

# Apply
terraform apply -var-file=environments/staging/terraform.tfvars
```

### Production

```bash
cd infrastructure/terraform

# Initialize with production backend
terraform init \
  -backend-config=environments/production/backend.tf \
  -reconfigure

# Plan
terraform plan -var-file=environments/production/terraform.tfvars

# Apply (requires approval)
terraform apply -var-file=environments/production/terraform.tfvars
```

## Post-Deployment Configuration

After deploying, manually configure secrets in AWS Secrets Manager:

```bash
# Update Alchemy API key
aws secretsmanager put-secret-value \
  --secret-id tesseract/staging/alchemy-api-key \
  --secret-string "your-alchemy-key"

# Update Infura API key
aws secretsmanager put-secret-value \
  --secret-id tesseract/staging/infura-api-key \
  --secret-string "your-infura-key"

# Update relayer private key (CRITICAL: Keep secure!)
aws secretsmanager put-secret-value \
  --secret-id tesseract/staging/relayer-private-key \
  --secret-string "0x..."

# Update contract addresses
aws secretsmanager put-secret-value \
  --secret-id tesseract/staging/contract-addresses \
  --secret-string '{
    "ethereum": "0x...",
    "polygon": "0x...",
    "arbitrum": "0x...",
    "optimism": "0x..."
  }'
```

## Monitoring

### CloudWatch Alarms

The infrastructure creates alarms for:
- High CPU utilization (>80%)
- High memory utilization (>80%)

### Prometheus Metrics

The relayer exposes metrics on port 9090. Configure your monitoring stack to scrape:
- `http://<alb-dns>:9090/metrics`

### Grafana Dashboard

Import the dashboard from:
- `relayer/monitoring/grafana/provisioning/dashboards/tesseract-overview.json`

## Cost Estimates

### Staging
- ECS Fargate: ~$30/month (1 vCPU, 2GB, 1 task)
- RDS: ~$25/month (db.t3.small)
- ALB: ~$20/month
- **Total: ~$75/month**

### Production
- ECS Fargate: ~$150/month (2 vCPU, 4GB, 2-10 tasks)
- RDS Multi-AZ: ~$200/month (db.r6g.large)
- ALB: ~$30/month
- **Total: ~$400/month**

## Security Considerations

1. **Private Keys**: Never commit or log private keys
2. **VPC**: Relayer runs in private subnets, no public IP
3. **RDS**: Encrypted at rest, accessible only from ECS
4. **Secrets**: Rotation recommended every 90 days
5. **IAM**: Least-privilege roles for ECS tasks

## Destroy

```bash
# Staging (safe)
terraform destroy -var-file=environments/staging/terraform.tfvars

# Production (requires confirmation, has deletion protection)
terraform destroy -var-file=environments/production/terraform.tfvars
```
