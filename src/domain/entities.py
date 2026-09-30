"""
src/domain/entities.py - Pure domain models for Kake Product Experimentation & Retention Engine.
Strictly decoupled from external I/O, database drivers, or vendor SDKs.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class ExperimentSubject(BaseModel):
    """Domain model representing a single user participating in a product experiment."""
    user_id: str
    experiment_group: str = Field(description="'control' or 'treatment_v2'")
    pre_experiment_activity: float = Field(ge=0.0, description="Baseline metric used as CUPED covariate")
    post_experiment_activity: float = Field(ge=0.0, description="Observed outcome metric during experiment")
    duration_days: float = Field(ge=0.0, description="Observed survival duration in days")
    churn_observed: bool = Field(description="True if churn event was observed; False if censored")
    acquisition_channel: str = Field(default="organic")
    device_platform: str = Field(default="web_app")


class ExperimentSummary(BaseModel):
    """Statistical summary of A/B test results comparing naive vs CUPED-adjusted metrics."""
    sample_size_control: int
    sample_size_treatment: int
    raw_control_mean: float
    raw_treatment_mean: float
    raw_lift_pct: float
    cuped_control_mean: float
    cuped_treatment_mean: float
    cuped_lift_pct: float
    theta_coefficient: float
    variance_reduction_pct: float
    p_value: float
    is_significant: bool
    srm_p_value: float
    srm_detected: bool


class SurvivalSummary(BaseModel):
    """Parametric Weibull survival and retention profile for user cohorts."""
    shape_parameter: float
    scale_parameter: float
    median_survival_days: float
    retention_d7_pct: float
    retention_d14_pct: float
    retention_d30_pct: float


class ExecutionContext(BaseModel):
    """Runtime parameters governing statistical inference and telemetry bounds."""
    execution_id: str
    alpha: float = 0.05
    srm_alpha: float = 0.001
    minimum_detectable_effect: float = 0.05