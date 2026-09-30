"""
src/domain/contracts.py - Inversion of Dependencies (DIP) Protocols.
Ensures domain logic never binds to concrete databases, DuckDB, Snowflake, or UI sinks.
"""

from typing import Protocol, Optional, List, Dict, Any
import pandas as pd
from .entities import (
    ExecutionContext,
    ExperimentSummary,
    SurvivalSummary,
    ExperimentSubject,
)


class AnalyticalStorageProtocol(Protocol):
    """Abstract analytical storage contract (DuckDB in-memory, Snowflake stage, or Mock)."""
    def execute_query(self, query: str) -> pd.DataFrame: ...
    def scan_dataset(self, base_path: str) -> pd.DataFrame: ...


class CUPEDExperimentEngineProtocol(Protocol):
    """Abstract contract for causal A/B experimentation and variance reduction."""
    def evaluate_experiment(
        self,
        data: pd.DataFrame,
        context: Optional[ExecutionContext] = None,
    ) -> ExperimentSummary: ...


class SurvivalLifecycleProtocol(Protocol):
    """Abstract contract for Weibull / Kaplan-Meier user lifecycle survival estimation."""
    def fit_lifecycle(
        self,
        data: pd.DataFrame,
    ) -> SurvivalSummary: ...


class DeliverySinkProtocol(Protocol):
    """Abstract delivery contract for presentation layers (Rich CLI / Superset output)."""
    def render_report(
        self,
        experiment: ExperimentSummary,
        survival: SurvivalSummary,
    ) -> Any: ...