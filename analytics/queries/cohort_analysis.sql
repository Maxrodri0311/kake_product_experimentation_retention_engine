-- ============================================================================
-- Kake Product Analytics - Unified Cohort & Retention Analysis
-- Dialect: ANSI SQL / DuckDB / PostgreSQL Compatible
-- ============================================================================

WITH raw_user_metrics AS (
    SELECT
        user_id,
        cohort,
        acquisition_channel,
        experiment_group,
        pre_experiment_activity,
        post_experiment_activity,
        duration_days,
        churn_observed,
        -- Milestone flags
        CASE WHEN duration_days >= 7 THEN 1.0 ELSE 0.0 END AS retained_d7,
        CASE WHEN duration_days >= 14 THEN 1.0 ELSE 0.0 END AS retained_d14,
        CASE WHEN duration_days >= 30 THEN 1.0 ELSE 0.0 END AS retained_d30,
        CASE WHEN churn_observed THEN 1.0 ELSE 0.0 END AS churned
    FROM telemetry_events
),
cohort_summary AS (
    SELECT
        cohort,
        acquisition_channel,
        COUNT(DISTINCT user_id) AS total_users,
        ROUND(AVG(post_experiment_activity), 2) AS avg_engagement,
        ROUND(AVG(retained_d7) * 100.0, 1) AS retention_d7_pct,
        ROUND(AVG(retained_d14) * 100.0, 1) AS retention_d14_pct,
        ROUND(AVG(retained_d30) * 100.0, 1) AS retention_d30_pct,
        ROUND(AVG(churned) * 100.0, 1) AS churn_rate_pct,
        DENSE_RANK() OVER (
            PARTITION BY cohort 
            ORDER BY COUNT(DISTINCT user_id) DESC
        ) AS channel_rank_within_cohort
    FROM raw_user_metrics
    GROUP BY cohort, acquisition_channel
)
SELECT
    cohort,
    acquisition_channel,
    total_users,
    avg_engagement,
    retention_d7_pct,
    retention_d14_pct,
    retention_d30_pct,
    churn_rate_pct,
    channel_rank_within_cohort
FROM cohort_summary
ORDER BY cohort DESC, total_users DESC;