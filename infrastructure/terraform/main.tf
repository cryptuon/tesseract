# Tesseract Infrastructure - Main Configuration
# AWS-based deployment for the Tesseract relayer

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state storage (configure for your environment)
  backend "s3" {
    bucket         = "tesseract-terraform-state"
    key            = "relayer/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "tesseract-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Tesseract"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "tesseract-${var.environment}"
  cidr = var.vpc_cidr

  azs              = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets  = var.private_subnets
  public_subnets   = var.public_subnets
  database_subnets = var.database_subnets

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true

  tags = {
    Name = "tesseract-${var.environment}-vpc"
  }
}

# ECS Cluster
module "ecs" {
  source = "./modules/ecs"

  environment    = var.environment
  cluster_name   = "tesseract-${var.environment}"
  vpc_id         = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnets
  public_subnets  = module.vpc.public_subnets

  # Relayer configuration
  relayer_image       = var.relayer_image
  relayer_cpu         = var.relayer_cpu
  relayer_memory      = var.relayer_memory
  relayer_min_count   = var.relayer_min_count
  relayer_max_count   = var.relayer_max_count

  # Database connection
  database_url_secret_arn = module.secrets.database_url_arn

  # Secrets
  secrets_arns = module.secrets.all_secret_arns

  depends_on = [module.rds, module.secrets]
}

# RDS PostgreSQL
module "rds" {
  source = "./modules/rds"

  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  database_subnets = module.vpc.database_subnets

  instance_class  = var.db_instance_class
  allocated_storage = var.db_allocated_storage

  # Security
  allowed_security_groups = [module.ecs.relayer_security_group_id]
}

# Secrets Manager
module "secrets" {
  source = "./modules/secrets"

  environment = var.environment

  # These will be manually populated after creation
  create_placeholders = true
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "relayer_cpu_high" {
  alarm_name          = "tesseract-${var.environment}-relayer-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Relayer CPU utilization is high"

  dimensions = {
    ClusterName = module.ecs.cluster_name
    ServiceName = module.ecs.relayer_service_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "relayer_memory_high" {
  alarm_name          = "tesseract-${var.environment}-relayer-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Relayer memory utilization is high"

  dimensions = {
    ClusterName = module.ecs.cluster_name
    ServiceName = module.ecs.relayer_service_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "tesseract-${var.environment}-alerts"
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "relayer_service_name" {
  value = module.ecs.relayer_service_name
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "api_endpoint" {
  value = module.ecs.api_endpoint
}
