# Secrets Manager Module for Tesseract

variable "environment" {}
variable "create_placeholders" {
  default = true
}

# API Keys (to be populated manually)
resource "aws_secretsmanager_secret" "alchemy_api_key" {
  name = "tesseract/${var.environment}/alchemy-api-key"
}

resource "aws_secretsmanager_secret" "infura_api_key" {
  name = "tesseract/${var.environment}/infura-api-key"
}

# Relayer private key
resource "aws_secretsmanager_secret" "relayer_private_key" {
  name = "tesseract/${var.environment}/relayer-private-key"
}

# Contract addresses per chain
resource "aws_secretsmanager_secret" "contract_addresses" {
  name = "tesseract/${var.environment}/contract-addresses"
}

# Slack webhook for alerts
resource "aws_secretsmanager_secret" "slack_webhook" {
  name = "tesseract/${var.environment}/slack-webhook"
}

# Create placeholder values if requested
resource "aws_secretsmanager_secret_version" "alchemy_placeholder" {
  count         = var.create_placeholders ? 1 : 0
  secret_id     = aws_secretsmanager_secret.alchemy_api_key.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret_version" "infura_placeholder" {
  count         = var.create_placeholders ? 1 : 0
  secret_id     = aws_secretsmanager_secret.infura_api_key.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret_version" "relayer_key_placeholder" {
  count         = var.create_placeholders ? 1 : 0
  secret_id     = aws_secretsmanager_secret.relayer_private_key.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

output "alchemy_api_key_arn" {
  value = aws_secretsmanager_secret.alchemy_api_key.arn
}

output "infura_api_key_arn" {
  value = aws_secretsmanager_secret.infura_api_key.arn
}

output "relayer_private_key_arn" {
  value = aws_secretsmanager_secret.relayer_private_key.arn
}

output "database_url_arn" {
  value = "" # Set by RDS module
}

output "all_secret_arns" {
  value = [
    aws_secretsmanager_secret.alchemy_api_key.arn,
    aws_secretsmanager_secret.infura_api_key.arn,
    aws_secretsmanager_secret.relayer_private_key.arn,
    aws_secretsmanager_secret.contract_addresses.arn,
    aws_secretsmanager_secret.slack_webhook.arn,
  ]
}
