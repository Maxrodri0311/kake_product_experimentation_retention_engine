"""
tests/test_suite.py - Automated Pytest Suite.
Verifies data generation, schema integrity, and Dependency Inversion Principle (DIP).
"""

import os
import tempfile
import pytest
import pandas as pd
from src.data_generator import generate_domain_dataset
from src.core_engine import DomainAnalyticsEngine, DuckDBStorageAdapter, create_engine
from src.domain.contracts import AnalyticalStorageProtocol


@pytest.fixture(scope="session")
def test_dataset(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data") / "test_data.parquet"
    df = generate_domain_dataset(num_records=2000, output_path=str(fn))
    return str(fn)


def test_data_generation_integrity(test_dataset):
    df = pd.read_parquet(test_dataset)
    assert "user_id" in df.columns
    assert "pre_experiment_activity" in df.columns
    assert "post_experiment_activity" in df.columns
    assert "experiment_group" in df.columns
    assert "duration_days" in df.columns
    assert "churn_observed" in df.columns
    assert set(df["experiment_group"].unique()) == {"control", "treatment_v2"}
    assert df.isnull().sum().sum() == 0


def test_core_engine_execution_with_duckdb(test_dataset):
    adapter = DuckDBStorageAdapter()
    engine = DomainAnalyticsEngine(storage=adapter, data_path=test_dataset)
    res = engine.execute_analysis()
    assert len(res) == 1
    assert "mean_primary_metric" in res.columns
    assert res.iloc[0]["total_records"] == 2000


def test_core_engine_dependency_inversion_mock():
    """Validates that domain logic works with an in-memory mock without DuckDB or disk I/O."""
    class MockStorageAdapter:
        def execute_query(self, query: str) -> pd.DataFrame:
            return pd.DataFrame([
                {"total_records": 500, "mean_primary_metric": 42.0}
            ])
        def scan_dataset(self, base_path: str) -> pd.DataFrame:
            return pd.DataFrame()

    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        engine = DomainAnalyticsEngine(storage=MockStorageAdapter(), data_path=tmp.name)
        res = engine.execute_analysis()
        assert len(res) == 1
        assert res.iloc[0]["mean_primary_metric"] == 42.0