# =============================================================================
# CloudDB Sentinel — Terraform Provider & Core Configuration (Fase 5 Enterprise)
# =============================================================================
# HashiCorp Terraform configuration for Enterprise S3 Backup Storage and IAM.
# Compatible with AWS Cloud and LocalStack (local simulation).
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional S3 Backend for State Locking (uncomment for production use)
  # backend "s3" {
  #   bucket         = "clouddb-sentinel-tfstate"
  #   key            = "enterprise/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "clouddb-sentinel-tflocks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  # Transparent LocalStack Support
  dynamic "endpoints" {
    for_each = var.enable_localstack ? [1] : []
    content {
      s3       = var.localstack_endpoint
      iam      = var.localstack_endpoint
      sts      = var.localstack_endpoint
      dynamodb = var.localstack_endpoint
    }
  }

  skip_credentials_validation = var.enable_localstack
  skip_metadata_api_check     = var.enable_localstack
  skip_requesting_account_id  = var.enable_localstack
  s3_use_path_style           = var.enable_localstack

  default_tags {
    tags = {
      Project            = "CloudDB-Sentinel"
      Environment        = var.environment
      ManagedBy          = "Terraform"
      ArchitecturePhase  = "Fase-5-Enterprise"
      SecurityCompliance = "ISO-27001-CIS-DBRE"
    }
  }
}
