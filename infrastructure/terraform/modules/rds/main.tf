# RDS PostgreSQL Module for Tesseract

variable "environment" {}
variable "vpc_id" {}
variable "database_subnets" {}
variable "instance_class" {}
variable "allocated_storage" {}
variable "allowed_security_groups" {}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "tesseract-${var.environment}"
  subnet_ids = var.database_subnets

  tags = {
    Name = "tesseract-${var.environment}-db-subnet"
  }
}

# Security Group
resource "aws_security_group" "rds" {
  name        = "tesseract-${var.environment}-rds"
  description = "Security group for Tesseract RDS"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_groups
  }

  tags = {
    Name = "tesseract-${var.environment}-rds"
  }
}

# Random password for RDS
resource "random_password" "rds" {
  length  = 32
  special = false
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "tesseract-${var.environment}"

  engine               = "postgres"
  engine_version       = "16.1"
  instance_class       = var.instance_class
  allocated_storage    = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 2

  db_name  = "tesseract_relayer"
  username = "tesseract"
  password = random_password.rds.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az               = var.environment == "production"
  storage_encrypted      = true
  storage_type           = "gp3"

  backup_retention_period = var.environment == "production" ? 30 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  deletion_protection = var.environment == "production"
  skip_final_snapshot = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "tesseract-${var.environment}-final" : null

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name = "tesseract-${var.environment}"
  }
}

# RDS Monitoring Role
resource "aws_iam_role" "rds_monitoring" {
  name = "tesseract-${var.environment}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Store password in Secrets Manager
resource "aws_secretsmanager_secret" "rds_password" {
  name = "tesseract/${var.environment}/rds-password"
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id     = aws_secretsmanager_secret.rds_password.id
  secret_string = random_password.rds.result
}

# Store full connection URL
resource "aws_secretsmanager_secret" "database_url" {
  name = "tesseract/${var.environment}/database-url"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = "postgres://tesseract:${random_password.rds.result}@${aws_db_instance.main.endpoint}/tesseract_relayer"
}

output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "database_url_secret_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}
