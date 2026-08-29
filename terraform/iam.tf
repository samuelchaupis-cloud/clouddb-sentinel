# =============================================================================
# CloudDB Sentinel — IAM Least-Privilege Identity & Policy (Fase 5 Enterprise)
# =============================================================================

# Service Account User for Automated Backup Agent
resource "aws_iam_user" "backup_agent" {
  name = "${var.iam_user_name}-${var.environment}"
  path = "/service-accounts/databases/"

  tags = {
    Role        = "DatabaseReliabilityEngineer-Agent"
    Description = "Automated agent for streaming encrypted database dumps to S3"
  }
}

# Access Keys for the Backup Agent (Stored in AWS Secrets Manager / Vault in prod)
resource "aws_iam_access_key" "backup_agent_key" {
  user = aws_iam_user.backup_agent.name
}

# Least-Privilege IAM Policy for Sentinel S3 Operations
resource "aws_iam_policy" "backup_policy" {
  name        = "CloudDBSentinelBackupPolicy-${var.environment}"
  path        = "/service-policies/"
  description = "Strict least-privilege IAM policy allowing Sentinel agents to upload, verify and manage backups."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSentinelBucketListing"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning"
        ]
        Resource = [
          aws_s3_bucket.backup_storage.arn
        ]
        Condition = {
          StringLike = {
            "s3:prefix" : [
              "",
              "backups/*"
            ]
          }
        }
      },
      {
        Sid    = "AllowSentinelObjectOperations"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:AbortMultipartUpload"
        ]
        Resource = [
          "${aws_s3_bucket.backup_storage.arn}/backups/*"
        ]
      }
    ]
  })
}

# Policy Attachment
resource "aws_iam_user_policy_attachment" "backup_attachment" {
  user       = aws_iam_user.backup_agent.name
  policy_arn = aws_iam_policy.backup_policy.arn
}
