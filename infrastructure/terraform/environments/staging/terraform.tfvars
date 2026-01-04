# Tesseract Staging Environment Configuration

environment = "staging"
aws_region  = "us-east-1"

# VPC Configuration
vpc_cidr         = "10.0.0.0/16"
private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
public_subnets   = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
database_subnets = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]

# ECS Relayer Configuration
relayer_image     = "ghcr.io/tesseract/relayer:staging"
relayer_cpu       = 1024   # 1 vCPU
relayer_memory    = 2048   # 2 GB
relayer_min_count = 1
relayer_max_count = 3

# RDS Configuration (smaller for staging)
db_instance_class   = "db.t3.small"
db_allocated_storage = 20
