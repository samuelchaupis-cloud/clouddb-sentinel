# =============================================================================
# CloudDB Sentinel — S3 Disaster Recovery Storage (Fase 5 Enterprise)
# =============================================================================

resource "aws_s3_bucket" "backup_storage" {
  bucket        = var.bucket_name
  force_destroy = var.environment != "production"

  tags = {
    Name               = var.bucket_name
    DataClassification = "Confidential-B2B-Backups"
    BackupTier         = "Mission-Critical-DR"
  }
}

# Ownership Controls (Enforce BucketOwnerEnforced)
resource "aws_s3_bucket_ownership_controls" "backup_storage" {
  bucket = aws_s3_bucket.backup_storage.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Strict Zero-Trust Public Access Block
resource "aws_s3_bucket_public_access_block" "backup_storage" {
  bucket = aws_s3_bucket.backup_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Object Versioning (Ransomware and Accidental Deletion Protection)
resource "aws_s3_bucket_versioning" "backup_storage" {
  bucket = aws_s3_bucket.backup_storage.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

# Server-Side Encryption (SSE-S3 AES-256 at Rest)
resource "aws_s3_bucket_server_side_encryption_configuration" "backup_storage" {
  bucket = aws_s3_bucket.backup_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Lifecycle Rules: Transition to Glacier and Expiration
resource "aws_s3_bucket_lifecycle_configuration" "backup_storage" {
  bucket = aws_s3_bucket.backup_storage.id

  depends_on = [aws_s3_bucket_versioning.backup_storage]

  rule {
    id     = "clouddb-backup-lifecycle-retention"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    # Transition current versions to Glacier after threshold
    transition {
      days          = var.retention_glacier_days
      storage_class = "GLACIER"
    }

    # Expire current versions after total retention window
    expiration {
      days = var.retention_expiration_days
    }

    # Manage noncurrent versions
    noncurrent_version_transition {
      noncurrent_days = var.retention_glacier_days
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = var.retention_expiration_days
    }

    # Abort incomplete multipart uploads after 7 days
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
