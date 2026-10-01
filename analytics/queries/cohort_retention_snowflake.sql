-- ============================================================================
-- Kake Product Experimentation & Retention Engine (GP-123)
-- Snowflake Production Analytical SQL Pipeline: CUPED Variance Reduction & Cohorts
-- Target Role: Product Data Scientist | Stack: Snowflake + Apache Superset + Eppo
-- ============================================================================

USE DATABASE KAKE_PRODUCT_ANALYTICS;
USE SCHEMA EXPERIMENTATION;
USE WAREHOUSE ANALYTICS_WH;

-- ----------------------------------------------------------------------------
-- 1. STAGED EVENT INGESTION CTE: Read Columnar Parquet from S3 Telemetry Stage
-- ----------------------------------------------------------------------------
WITH staged_telemetry_events AS (
    SELECT
        $1:user_id::VARCHAR AS user_id,
        $1:cohort::VARCHAR AS cohort_month,
        $1:acquisition_channel::VARCHAR AS acquisition_channel,
        $1:experiment_group::VARCHAR AS experiment_group,
        $1:pre_experiment_activity::FLOAT AS pre_experiment_activity,   -- Covariate X
        $1:post_experiment_activity::FLOAT AS post_experiment_activity, -- Outcome Y
        $1:duration_days::FLOAT AS duration_days,
        $1:churn_observed::BOOLEAN AS churn_observed,
        $1:event_timestamp::TIMESTAMP_NTZ AS event_timestamp
    FROM @KAKE_PRODUCT_ANALYTICS.EXPERIMENTATION.S3_TELEMETRY_STAGE
    (FILE_FORMAT => 'PARQUET_FORMAT')
),

-- ----------------------------------------------------------------------------
-- 2. CUPED THETA (θ) DERIVATION IN PURE SQL
-- Formula: θ = Cov(Y, X) / Var(X) across pooled baseline population
-- ----------------------------------------------------------------------------
cuped_parameters AS (
    SELECT
        COVAR_SAMP(post_experiment_activity, pre_experiment_activity) AS cov_xy,
        VAR_SAMP(pre_experiment_activity) AS var_x,
        AVG(pre_experiment_activity) AS mean_x,
        VAR_SAMP(post_experiment_activity) AS var_y_raw,
        -- Guard against division by zero in degenerate cohorts
        CASE 
            WHEN VAR_SAMP(pre_experiment_activity) > 0 
            THEN COVAR_SAMP(post_experiment_activity, pre_experiment_activity) / VAR_SAMP(pre_experiment_activity)
            ELSE 0.0 
        END AS theta
    FROM staged_telemetry_events
),

-- ----------------------------------------------------------------------------
-- 3. USER-LEVEL METRIC TRANSFORMATION
-- Formula: Y_cuped = Y - θ * (X - mean(X))
-- ----------------------------------------------------------------------------
user_level_cuped AS (
    SELECT
        e.user_id,
        e.cohort_month,
        e.acquisition_channel,
        e.experiment_group,
        e.pre_experiment_activity,
        e.post_experiment_activity AS y_raw,
        -- Apply CUPED variance reduction formula
        (e.post_experiment_activity - p.theta * (e.pre_experiment_activity - p.mean_x)) AS y_cuped,
        e.duration_days,
        e.churn_observed
    FROM staged_telemetry_events e
    CROSS JOIN cuped_parameters p
),

-- ----------------------------------------------------------------------------
-- 4. EXPERIMENT VARIANT SUMMARY: Raw Lift vs CUPED Lift & Noise Reduction
-- Feeds directly into Eppo / Superset A/B Test Monitoring Dashboards
-- ----------------------------------------------------------------------------
variant_statistical_summary AS (
    SELECT
        experiment_group,
        COUNT(DISTINCT user_id) AS sample_size_n,
        -- Raw Engagement Metrics
        ROUND(AVG(y_raw), 4) AS raw_mean_engagement,
        ROUND(VAR_SAMP(y_raw), 4) AS raw_sample_variance,
        ROUND(STDDEV_SAMP(y_raw) / SQRT(COUNT(DISTINCT user_id)), 4) AS raw_standard_error,
        -- CUPED Adjusted Metrics
        ROUND(AVG(y_cuped), 4) AS cuped_mean_engagement,
        ROUND(VAR_SAMP(y_cuped), 4) AS cuped_sample_variance,
        ROUND(STDDEV_SAMP(y_cuped) / SQRT(COUNT(DISTINCT user_id)), 4) AS cuped_standard_error,
        -- Variance Reduction Metric
        ROUND((1.0 - (VAR_SAMP(y_cuped) / NULLIF(VAR_SAMP(y_raw), 0))) * 100, 2) AS variance_reduction_pct
    FROM user_level_cuped
    GROUP BY experiment_group
),

-- ----------------------------------------------------------------------------
-- 5. SRM (Sample Ratio Mismatch) Diagnostic View
-- Validates that assignment distribution adheres to intended 50/50 allocation
-- ----------------------------------------------------------------------------
srm_validation AS (
    SELECT
        COUNT(CASE WHEN experiment_group = 'control' THEN 1 END) AS n_control,
        COUNT(CASE WHEN experiment_group = 'treatment_v2' THEN 1 END) AS n_treatment,
        COUNT(*) AS n_total,
        -- SRM Chi-square statistic: sum((observed - expected)^2 / expected)
        ROUND(
            (POWER(COUNT(CASE WHEN experiment_group = 'control' THEN 1 END) - (COUNT(*) * 0.5), 2) / (COUNT(*) * 0.5)) +
            (POWER(COUNT(CASE WHEN experiment_group = 'treatment_v2' THEN 1 END) - (COUNT(*) * 0.5), 2) / (COUNT(*) * 0.5)),
            4
        ) AS chi2_srm_statistic,
        CASE
            -- Chi-square critical value for df=1 at alpha=0.01 is 6.635
            WHEN (
                (POWER(COUNT(CASE WHEN experiment_group = 'control' THEN 1 END) - (COUNT(*) * 0.5), 2) / (COUNT(*) * 0.5)) +
                (POWER(COUNT(CASE WHEN experiment_group = 'treatment_v2' THEN 1 END) - (COUNT(*) * 0.5), 2) / (COUNT(*) * 0.5))
            ) > 6.635 THEN 'SRM_ALERT_REJECT_EXPERIMENT'
            ELSE 'SRM_PASSED_HEALTHY_ASSIGNMENT'
        END AS srm_status
    FROM staged_telemetry_events
),

-- ----------------------------------------------------------------------------
-- 6. LONGITUDINAL COHORT RETENTION & ONBOARDING DECAY
-- Feeds Apache Superset Cohort Retention Heatmap (D7, D14, D30, D60)
-- ----------------------------------------------------------------------------
cohort_lifecycle_retention AS (
    SELECT
        cohort_month,
        acquisition_channel,
        COUNT(DISTINCT user_id) AS cohort_size,
        -- Early Onboarding Milestones
        ROUND(AVG(CASE WHEN duration_days >= 7 THEN 1.0 ELSE 0.0 END) * 100, 1) AS retention_d7_pct,
        ROUND(AVG(CASE WHEN duration_days >= 14 THEN 1.0 ELSE 0.0 END) * 100, 1) AS retention_d14_pct,
        -- Medium-Term Retention
        ROUND(AVG(CASE WHEN duration_days >= 30 THEN 1.0 ELSE 0.0 END) * 100, 1) AS retention_d30_pct,
        ROUND(AVG(CASE WHEN duration_days >= 60 THEN 1.0 ELSE 0.0 END) * 100, 1) AS retention_d60_pct,
        -- Terminal Churn
        ROUND(AVG(CASE WHEN churn_observed THEN 1.0 ELSE 0.0 END) * 100, 1) AS cumulative_churn_pct,
        ROUND(AVG(post_experiment_activity), 2) AS avg_engagement_intensity
    FROM user_level_cuped
    GROUP BY cohort_month, acquisition_channel
)

-- Final Superset BI Presentation View
SELECT
    c.cohort_month,
    c.acquisition_channel,
    c.cohort_size,
    c.retention_d7_pct,
    c.retention_d14_pct,
    c.retention_d30_pct,
    c.retention_d60_pct,
    c.cumulative_churn_pct,
    c.avg_engagement_intensity,
    DENSE_RANK() OVER (PARTITION BY c.cohort_month ORDER BY c.cohort_size DESC) AS channel_volume_rank
FROM cohort_lifecycle_retention c
ORDER BY c.cohort_month DESC, c.cohort_size DESC;
