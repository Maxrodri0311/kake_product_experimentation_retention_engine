# kake_product_data_scientist_bridge_project - Infrastructure Outputs
# Target Stack: Snowflake, AWS S3 Lakehouse, Terraform

output "telemetry_bucket_arn" {
  description = "ARN of the primary AWS S3 telemetry lakehouse bucket"
  value       = aws_s3_bucket.telemetry_lake.arn
}

output "snowflake_database_name" {
  description = "Snowflake Analytical Database Name"
  value       = snowflake_database.product_analytics_db.name
}

output "snowflake_warehouse_name" {
  description = "Dedicated Snowflake Analytics Warehouse"
  value       = snowflake_warehouse.analytics_wh.name
}

output "snowflake_stage_uri" {
  description = "Snowflake external stage URI referencing S3 telemetry"
  value       = snowflake_stage.s3_telemetry_stage.url
}

output "snowflake_role_name" {
  description = "RBAC Role for Product Data Scientists"
  value       = snowflake_role.product_data_scientist_role.name
}