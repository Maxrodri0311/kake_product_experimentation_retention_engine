"""
src/data_generator.py - Calibrated Stochastic Domain Data Generator.
Physics: CUPED Causal Experimentation & Weibull Retention Survival for Kake (GP-123).
Generates realistic A/B experiment telemetry and cohort survival curves with zero toy placeholders.
"""

import os
import time
import argparse
from datetime import datetime, timedelta
import numpy as np
import pandas as pd


def generate_domain_dataset(
    num_records: int = 50000,
    output_path: str = "data/raw_dataset.parquet",
    seed: int = 42,
    treatment_lift: float = 0.085,
    weibull_shape: float = 1.35,
    weibull_scale: float = 45.0,
) -> pd.DataFrame:
    """
    Generates 50,000+ realistic product telemetry records for Kake A/B testing and retention modeling.
    
    Mathematical Invariants:
    1. Pre-experiment covariate X: Log-Normal(3.2, 0.70) modeling baseline active minutes.
    2. Post-experiment metric Y: Y = 5.0 + 0.85*X + N(0, 14) with correlation rho ~ 0.68.
       Treatment group receives an injected lift of `treatment_lift` (+8.5%).
    3. Survival duration T: Weibull(shape=k, scale=lambda) modeling steep D1-D14 drop-off.
    4. Censoring: Window of 90 days. If T > 90, churn_observed = False (censored), duration = 90.0.
    """
    print(f"[Data Generator] Generating {num_records:,} calibrated product events for Kake...")
    start_time = time.time()
    rng = np.random.default_rng(seed)

    # 1. Identifiers
    user_ids = [f"usr_{i:07d}" for i in range(1, num_records + 1)]

    # 2. Experiment Allocation (50/50 Control vs Treatment)
    groups = rng.choice(["control", "treatment_v2"], size=num_records, p=[0.50, 0.50])

    # 3. Pre-experiment baseline metric (Covariate X for CUPED)
    pre_activity = rng.lognormal(mean=3.2, sigma=0.70, size=num_records)
    pre_activity = np.clip(pre_activity, 1.0, 500.0)

    # 4. Post-experiment outcome metric (Metric Y)
    baseline_noise = rng.normal(loc=0.0, scale=14.0, size=num_records)
    treatment_multiplier = np.where(groups == "treatment_v2", 1.0 + treatment_lift, 1.0)
    
    post_activity = (5.0 + 0.85 * pre_activity + baseline_noise) * treatment_multiplier
    post_activity = np.clip(post_activity, 0.5, 750.0)

    # 5. Cohort Temporal Window & Invariants (Last 90 days)
    base_date = datetime(2026, 9, 30)
    random_days_ago = rng.integers(1, 91, size=num_records)
    signup_dates = [base_date - timedelta(days=int(d)) for d in random_days_ago]
    cohorts = [d.strftime("%Y-%m") for d in signup_dates]

    # 6. Weibull Time-to-Event Survival Physics (k=1.35 captures steep onboarding drop-off)
    u = rng.uniform(0.0001, 0.9999, size=num_records)
    survival_days = weibull_scale * (-np.log(u)) ** (1.0 / weibull_shape)
    
    # Treatment group enjoys a slight retention bonus (+15% scale life)
    survival_days = np.where(groups == "treatment_v2", survival_days * 1.15, survival_days)
    
    # Max observation window is 90 days (Right-censoring)
    churn_observed = survival_days <= 90.0
    duration_days = np.where(churn_observed, survival_days, 90.0)
    duration_days = np.round(duration_days, 2)

    # 7. Categorical Dimensions (Acquisition & Platform)
    channels = rng.choice(
        ["organic", "paid_growth", "referral", "b2b_partner"],
        size=num_records,
        p=[0.40, 0.35, 0.15, 0.10],
    )
    platforms = rng.choice(
        ["web_app", "ios", "android"],
        size=num_records,
        p=[0.50, 0.30, 0.20],
    )

    df = pd.DataFrame({
        "user_id": user_ids,
        "signup_date": [d.strftime("%Y-%m-%d") for d in signup_dates],
        "cohort": cohorts,
        "experiment_group": groups,
        "pre_experiment_activity": np.round(pre_activity, 4),
        "post_experiment_activity": np.round(post_activity, 4),
        "duration_days": duration_days,
        "churn_observed": churn_observed,
        "acquisition_channel": channels,
        "device_platform": platforms,
    })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_parquet(output_path, index=False, compression="snappy")

    # Also export sample CSV for Snowflake External Stage demo
    csv_sample_path = os.path.join(os.path.dirname(output_path), "sample_snowflake_events.csv")
    df.head(5000).to_csv(csv_sample_path, index=False)

    elapsed = time.time() - start_time
    print(f"[Data Generator] Successfully generated {len(df):,} records in {elapsed:.2f}s -> {output_path}")
    print(f"  - Control mean (raw):   {df[df['experiment_group'] == 'control']['post_experiment_activity'].mean():.2f}")
    print(f"  - Treatment mean (raw): {df[df['experiment_group'] == 'treatment_v2']['post_experiment_activity'].mean():.2f}")
    print(f"  - Injected Lift:        ~{treatment_lift*100:.1f}%")
    print(f"  - Churn Rate (90d):     {df['churn_observed'].mean()*100:.1f}%")
    print(f"  - Snowflake Sample CSV: {csv_sample_path}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate domain dataset.")
    parser.add_argument("--records", type=int, default=50000)
    parser.add_argument("--output", type=str, default="data/raw_dataset.parquet")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    generate_domain_dataset(
        num_records=args.records,
        output_path=args.output,
        seed=args.seed,
    )