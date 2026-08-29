# =============================================================================
# CloudDB Sentinel — Terraform Variables (Fase 5 Enterprise)
# =============================================================================

variable "aws_region" {
  description = "Target AWS region for deploying CloudDB Sentinel backup infrastructure"
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]{1}$", var.aws_region))
    error_message = "The aws_region must follow the standard AWS region naming pattern (e.g., us-east-1, sa-east-1)."
  }
}

variable "environment" {
  description = "Deployment environment tier (production, staging, development, dr-lab)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "development", "dr-lab"], var.environment)
    error_message = "The environment variable must be one of: production, staging, development, dr-lab."
  }
}

variable "bucket_name" {
  description = "Globally unique name for the S3 backup and disaster recovery bucket"
  type        = string
  default     = "clouddb-backups-b2b"

  validation {
    condition     = length(var.bucket_name) >= 3 && length(var.bucket_name) <= 63 && can(regex("^[a-z0-9.-]+$", var.bucket_name))
    error_message = "The bucket_name must be between 3 and 63 characters long and contain only lowercase letters, numbers, hyphens, and periods."
  }
}

variable "enable_versioning" {
  description = "Enables object versioning for zero-trust disaster recovery and ransomware protection"
  type        = bool
  default     = true
}

variable "retention_glacier_days" {
  description = "Number of days after creation before transitioning database backups to Glacier Flexible Retrieval"
  type        = number
  default     = 30

  validation {
    condition     = var.retention_glacier_days >= 1 && var.retention_glacier_days <= 365
    error_message = "The retention_glacier_days must be an integer between 1 and 365 days."
  }
}

variable "retention_expiration_days" {
  description = "Total retention period in days before non-current backup objects are permanently expired"
  type        = number
  default     = 90

  validation {
    condition     = var.retention_expiration_days >= 30 && var.retention_expiration_days <= 3650
    error_message = "The retention_expiration_days must be an integer between 30 and 3650 days."
  }
}

variable "iam_user_name" {
  description = "IAM user name for the automated Sentinel DBRE backup agent"
  type        = string
  default     = "sentinel-backup-agent"
}

variable "enable_localstack" {
  description = "Set to true to route all AWS SDK calls to local LocalStack instance for offline testing"
  type        = bool
  default     = false
}

variable "localstack_endpoint" {
  description = "LocalStack API endpoint URL for local emulation"
  type        = string
  default     = "http://localhost:4566"
}
