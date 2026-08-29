# =============================================================================
# CloudDB Sentinel — Terraform Outputs (Fase 5 Enterprise)
# =============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 Disaster Recovery bucket for backups"
  value       = aws_s3_bucket.backup_storage.id
}

output "s3_bucket_arn" {
  description = "Amazon Resource Name (ARN) of the S3 backup bucket"
  value       = aws_s3_bucket.backup_storage.arn
}

output "s3_bucket_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.backup_storage.bucket_regional_domain_name
}

output "iam_user_name" {
  description = "Name of the IAM service account user created for Sentinel"
  value       = aws_iam_user.backup_agent.name
}

output "iam_user_arn" {
  description = "ARN of the IAM user for Sentinel agent"
  value       = aws_iam_user.backup_agent.arn
}

output "iam_policy_arn" {
  description = "ARN of the attached least-privilege IAM policy"
  value       = aws_iam_policy.backup_policy.arn
}

output "iam_access_key_id" {
  description = "Access Key ID for configuring the Sentinel S3 client in .env"
  value       = aws_iam_access_key.backup_agent_key.id
}

output "iam_secret_access_key" {
  description = "Secret Access Key for the Sentinel backup agent"
  value       = aws_iam_access_key.backup_agent_key.secret
  sensitive   = true
}
