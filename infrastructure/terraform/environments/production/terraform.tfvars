# Tesseract Production Environment Configuration

environment = "production"
aws_region  = "us-east-1"

# VPC Configuration
vpc_cidr         = "10.1.0.0/16"
private_subnets  = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
public_subnets   = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]
database_subnets = ["10.1.201.0/24", "10.1.202.0/24", "10.1.203.0/24"]

# ECS Relayer Configuration (production-grade)
relayer_image     = "ghcr.io/tesseract/relayer:latest"
relayer_cpu       = 2048   # 2 vCPU
relayer_memory    = 4096   # 4 GB
relayer_min_count = 2
relayer_max_count = 10

# RDS Configuration (production-grade)
db_instance_class    = "db.r6g.large"
db_allocated_storage = 100
