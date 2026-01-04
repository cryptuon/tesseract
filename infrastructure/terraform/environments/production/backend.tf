# Production Backend Configuration
# Run: terraform init -backend-config=backend.tf

terraform {
  backend "s3" {
    bucket         = "tesseract-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "tesseract-terraform-locks"
  }
}
