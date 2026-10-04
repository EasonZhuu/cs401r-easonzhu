locals {
  name_prefix = "${var.project}-${var.environment}"

  feature_definitions = {
    customer_id              = "String"
    event_time               = "Fractional"
    days_since_last_purchase = "Fractional"
    customer_tenure_days     = "Fractional"
    purchase_frequency_30d   = "Fractional"
    purchase_frequency_90d   = "Fractional"
    purchase_frequency_180d  = "Fractional"
    avg_order_value          = "Fractional"
    total_spend_90d          = "Fractional"
    total_lifetime_value     = "Fractional"
    avg_basket_size_6m       = "Fractional"
    category_diversity_score = "Fractional"
    online_to_store_ratio    = "Fractional"
    loyalty_tier             = "String"
    churn_risk_score         = "Fractional"
    churn_label              = "Integral"
  }
}

resource "aws_sagemaker_feature_group" "customers" {
  feature_group_name             = "${local.name_prefix}-customer-features"
  description                    = "Customer features from historical transactions and a holdout churn label"
  record_identifier_feature_name = "customer_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.data_engineer_role_arn

  dynamic "feature_definition" {
    for_each = local.feature_definitions
    content {
      feature_name = feature_definition.key
      feature_type = feature_definition.value
    }
  }

  online_store_config {
    enable_online_store = true
    storage_type        = "Standard"
  }

  offline_store_config {
    disable_glue_table_creation = false
    table_format                = "Glue"

    data_catalog_config {
      catalog    = "AwsDataCatalog"
      database   = var.glue_database_name
      table_name = replace("${local.name_prefix}-customer-features", "-", "_")
    }

    s3_storage_config {
      s3_uri = "s3://${var.bucket_name}/features/offline-store/"
    }
  }
}
