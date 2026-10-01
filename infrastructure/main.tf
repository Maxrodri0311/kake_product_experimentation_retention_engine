# kake_product_data_scientist_bridge_project - Enterprise Infrastructure as Code (IaC)
# Target Stack: Snowflake, AWS S3 Lakehouse, Eppo/Superset Integration, Terraform
# Staff-Level Architecture Blueprint for Kake Product Data Science

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.87"
    }
  }
}

# -----------------------------------------------------------------------------
# AWS Telemetry Lakehouse Layer
# -----------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "kake-product-experimentation-retention-engine"
      TargetRole  = "Product Data Scientist"
      ManagedBy   = "Terraform"
      Environment = "Production"
      DataTier    = "TelemetryLake"
    }
  }
}

variable "aws_region" {
  description = "AWS deployment region for telemetry storage"
  type        = string
  default     = "us-east-1"
}

variable "snowflake_account" {
  description = "Snowflake Account Identifier (e.g., xy12345.us-east-1)"
  type        = string
  default     = "kake_partner_prod.us-east-1"
}

resource "aws_s3_bucket" "telemetry_lake" {
  bucket        = "kake-product-telemetry-lakehouse-prod"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "telemetry_lake_versioning" {
  bucket = aws_s3_bucket.telemetry_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "telemetry_crypto" {
  bucket = aws_s3_bucket.telemetry_lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "telemetry_lifecycle" {
  bucket = aws_s3_bucket.telemetry_lake.id

  rule {
    id     = "archive_old_telemetry"
    status = "Enabled"

    filter {
      prefix = "raw_events/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# IAM Role for Snowflake S3 Storage Integration
resource "aws_iam_role" "snowflake_storage_integration_role" {
  name = "kake_snowflake_storage_integration_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::123456789012:root" # Placeholder Snowflake AWS VPCE ARN
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "KAKE_SNOWFLAKE_STORAGE_INTEGRATION_TOKEN"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "snowflake_s3_read_policy" {
  name        = "kake_snowflake_s3_read_policy"
  description = "Allows Snowflake analytical warehouse to read raw telemetry Parquet events"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.telemetry_lake.arn,
          "${aws_s3_bucket.telemetry_lake.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "snowflake_s3_attach" {
  role       = aws_iam_role.snowflake_storage_integration_role.name
  policy_arn = aws_iam_policy.snowflake_s3_read_policy.arn
}

# -----------------------------------------------------------------------------
# Snowflake Data Warehouse & Modeling Layer
# -----------------------------------------------------------------------------
resource "snowflake_database" "product_analytics_db" {
  name                        = "KAKE_PRODUCT_ANALYTICS"
  comment                     = "Production database for Kake product experiments, CUPED variance reduction and Weibull cohorts"
  data_retention_time_in_days = 14
}

resource "snowflake_schema" "experimentation_schema" {
  database            = snowflake_database.product_analytics_db.name
  name                = "EXPERIMENTATION"
  comment             = "A/B Testing, CUPED pre-experiment metrics and SRM telemetry"
  is_transient        = false
  data_retention_days = 14
}

resource "snowflake_schema" "lifecycles_schema" {
  database            = snowflake_database.product_analytics_db.name
  name                = "LIFECYCLES"
  comment             = "Longitudinal cohort retention, Kaplan-Meier & Weibull hazard curves"
  is_transient        = false
  data_retention_days = 14
}

resource "snowflake_warehouse" "analytics_wh" {
  name                = "ANALYTICS_WH"
  comment             = "Dedicated compute warehouse for product data science and Superset BI queries"
  warehouse_size      = "X-SMALL"
  auto_suspend        = 60
  auto_resume         = true
  min_cluster_count   = 1
  max_cluster_count   = 2
  scaling_policy      = "ECONOMY"
  initially_suspended = true
}

resource "snowflake_file_format" "parquet_format" {
  name        = "PARQUET_FORMAT"
  database    = snowflake_database.product_analytics_db.name
  schema      = snowflake_schema.experimentation_schema.name
  format_type = "PARQUET"
  compression = "SNAPPY"
  comment     = "Columnar Parquet format for fast vectorized Lakehouse ingestion"
}

resource "snowflake_file_format" "csv_format" {
  name        = "CSV_FORMAT"
  database    = snowflake_database.product_analytics_db.name
  schema      = snowflake_schema.experimentation_schema.name
  format_type = "CSV"
  field_delimiter = ","
  skip_header     = 1
  null_if         = ["NULL", ""]
  comment         = "Standard CSV format for sample event validation"
}

resource "snowflake_stage" "s3_telemetry_stage" {
  name        = "S3_TELEMETRY_STAGE"
  database    = snowflake_database.product_analytics_db.name
  schema      = snowflake_schema.experimentation_schema.name
  url         = "s3://${aws_s3_bucket.telemetry_lake.id}/raw_events/"
  file_format = "FORMAT_NAME = ${snowflake_database.product_analytics_db.name}.${snowflake_schema.experimentation_schema.name}.${snowflake_file_format.parquet_format.name}"
  comment     = "External Snowflake stage linked directly to S3 Telemetry Lake"
}

# Analytical Data Scientist Role & RBAC
resource "snowflake_role" "product_data_scientist_role" {
  name    = "PRODUCT_DATA_SCIENTIST"
  comment = "Engineering role for Product Data Scientists executing CUPED modeling and cohort tracking"
}

resource "snowflake_database_grant" "db_usage" {
  database_name = snowflake_database.product_analytics_db.name
  privilege     = "USAGE"
  roles         = [snowflake_role.product_data_scientist_role.name]
}

resource "snowflake_schema_grant" "experimentation_usage" {
  database_name = snowflake_database.product_analytics_db.name
  schema_name   = snowflake_schema.experimentation_schema.name
  privilege     = "USAGE"
  roles         = [snowflake_role.product_data_scientist_role.name]
}

resource "snowflake_warehouse_grant" "wh_usage" {
  warehouse_name = snowflake_warehouse.analytics_wh.name
  privilege      = "USAGE"
  roles          = [snowflake_role.product_data_scientist_role.name]
}