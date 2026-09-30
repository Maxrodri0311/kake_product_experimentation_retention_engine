"""
tests/test_suite.py - Automated Pytest Suite.
Verifies data generation, CUPED causal variance reduction, SRM testing,
Weibull retention invariants, and Dependency Inversion Principle (DIP).
"""

import os
import tempfile
import pytest
import pandas as pd
import numpy as np

from src.data_generator import generate_domain_dataset
from src.core_engine import DomainAnalyticsEngine, DuckDBStorageAdapter, create_engine
from src.domain.contracts import AnalyticalStorageProtocol
from src.domain.entities import ExecutionContext


@pytest.fixture(scope="session")
def test_dataset(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data") / "test_data.parquet"
    df = generate_domain_dataset(num_records=5000, output_path=str(fn), seed=42)
    return str(fn)


def test_data_generation_integrity(test_dataset):
    df = pd.read_parquet(test_dataset)
    assert len(df) == 5000
    assert "user_id" in df.columns
    assert "pre_experiment_activity" in df.columns
    assert "post_experiment_activity" in df.columns
    assert "experiment_group" in df.columns
    assert "duration_days" in df.columns
    assert "churn_observed" in df.columns
    assert set(df["experiment_group"].unique()) == {"control", "treatment_v2"}
    assert df.isnull().sum().sum() == 0


def test_cuped_statistical_lift_and_variance_reduction(test_dataset):
    adapter = DuckDBStorageAdapter()
    engine = DomainAnalyticsEngine(storage=adapter, data_path=test_dataset)
    exp = engine.execute_cuped_analysis()

    assert exp.sample_size_control > 0
    assert exp.sample_size_treatment > 0
    assert exp.variance_reduction_pct > 30.0, "CUPED must achieve >30% variance reduction"
    assert exp.theta_coefficient > 0.0
    assert exp.cuped_lift_pct > 0.0
    assert not exp.srm_detected, "Balanced 50/50 sample must pass SRM check"


def test_srm_detection_on_unbalanced_data(test_dataset):
    """Verifies that the SRM Chi-Square test correctly flags allocation anomalies."""
    adapter = DuckDBStorageAdapter()
    engine = DomainAnalyticsEngine(storage=adapter, data_path=test_dataset)
    df = engine.load_dataset()

    # Artificially unbalance the dataset to 80/20 to trigger SRM
    ctrl = df[df["experiment_group"] == "control"].iloc[:400]
    treat = df[df["experiment_group"] == "treatment_v2"].iloc[:1600]
    unbalanced_df = pd.concat([ctrl, treat])

    exp = engine.execute_cuped_analysis(df=unbalanced_df)
    assert exp.srm_detected is True, "SRM must trigger when sample allocation is severely skewed"
    assert exp.srm_p_value < 0.001


def test_weibull_survival_retention_invariants(test_dataset):
    adapter = DuckDBStorageAdapter()
    engine = DomainAnalyticsEngine(storage=adapter, data_path=test_dataset)
    surv = engine.execute_survival_analysis()

    assert surv.shape_parameter > 1.0, "Shape k > 1 indicates wear-out / early onboarding drop-off"
    assert surv.scale_parameter > 0.0
    assert 0.0 < surv.retention_d7_pct < 100.0
    assert 0.0 < surv.retention_d14_pct < surv.retention_d7_pct, "D14 retention must be <= D7 retention"
    assert 0.0 < surv.retention_d30_pct < surv.retention_d14_pct, "D30 retention must be <= D14 retention"


def test_core_engine_execution_with_duckdb(test_dataset):
    adapter = DuckDBStorageAdapter()
    engine = DomainAnalyticsEngine(storage=adapter, data_path=test_dataset)
    res = engine.execute_analysis()

    assert len(res) == 1
    assert "cuped_lift_pct" in res.columns
    assert "var_reduction_pct" in res.columns
    assert res.iloc[0]["total_records"] == 5000
    assert res.iloc[0]["var_reduction_pct"] > 30.0


def test_core_engine_dependency_inversion_mock():
    """Validates that domain logic works with an in-memory mock without DuckDB or disk I/O (Sub-2ms)."""
    class MockStorageAdapter:
        def execute_query(self, query: str) -> pd.DataFrame:
            return pd.DataFrame([
                {"cohort": "2026-09", "total_users": 100, "avg_engagement": 35.0}
            ])
        def scan_dataset(self, base_path: str) -> pd.DataFrame:
            return pd.DataFrame({
                "user_id": [f"u_{i}" for i in range(100)],
                "experiment_group": ["control"] * 50 + ["treatment_v2"] * 50,
                "pre_experiment_activity": np.random.uniform(10, 50, 100),
                "post_experiment_activity": np.random.uniform(15, 60, 100),
                "duration_days": np.random.uniform(1, 90, 100),
                "churn_observed": [True] * 80 + [False] * 20,
            })

    engine = DomainAnalyticsEngine(storage=MockStorageAdapter(), data_path="mock/path.parquet")
    exp = engine.execute_cuped_analysis()
    assert exp.sample_size_control == 50
    assert exp.sample_size_treatment == 50
    assert exp.variance_reduction_pct >= 0.0