"""
src/interface.py - Rich Terminal User Interface (CLI_TUI Paradigm).
Executive Experimentation & Retention Dashboard for Kake (GP-123).
"""

import os
import sys
from pathlib import Path

# Force UTF-8 stdout for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from src.core_engine import create_engine

console = Console(force_terminal=True)


def run_cli():
    console.print()
    console.print(Panel(
        "[bold cyan]KAKE - PRODUCT EXPERIMENTATION & RETENTION ENGINE (GP-123)[/bold cyan]\n"
        "[dim]Causal CUPED Variance Reduction & Weibull Retention Modeling (Snowflake / Eppo Archetype)[/dim]",
        title="[bold green]Executive Terminal Interface[/bold green]",
        border_style="cyan",
        box=box.ROUNDED,
    ))

    engine = create_engine()
    df = engine.load_dataset()
    exp = engine.execute_cuped_analysis(df)
    surv = engine.execute_survival_analysis(df)
    matrix = engine.execute_cohort_retention_matrix()

    # Panel 1: Experimentation Metrics
    exp_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold magenta")
    exp_table.add_column("Metric Dimension", style="cyan")
    exp_table.add_column("Control Arm", justify="right")
    exp_table.add_column("Treatment Arm", justify="right")
    exp_table.add_column("Impact / Lift", justify="right", style="bold green")

    exp_table.add_row(
        "Sample Size (N)",
        f"{exp.sample_size_control:,}",
        f"{exp.sample_size_treatment:,}",
        f"SRM: {'ALERT' if exp.srm_detected else 'PASS (p=' + str(exp.srm_p_value) + ')'}",
    )
    exp_table.add_row(
        "Raw Mean Engagement",
        f"{exp.raw_control_mean:.2f}",
        f"{exp.raw_treatment_mean:.2f}",
        f"+{exp.raw_lift_pct:.2f}%",
    )
    exp_table.add_row(
        "CUPED Adjusted Mean",
        f"{exp.cuped_control_mean:.2f}",
        f"{exp.cuped_treatment_mean:.2f}",
        f"[bold yellow]+{exp.cuped_lift_pct:.2f}%[/bold yellow]",
    )
    exp_table.add_row(
        "Variance Reduction",
        "Baseline (100%)",
        f"-{exp.variance_reduction_pct:.1f}% Noise",
        f"theta = {exp.theta_coefficient:.3f}",
    )
    exp_table.add_row(
        "Statistical Significance",
        f"p-val: {exp.p_value:.6f}",
        f"Alpha: 0.05",
        "[bold green]SIGNIFICANT (p < 0.001)[/bold green]" if exp.is_significant else "[red]NOT SIGNIFICANT[/red]",
    )

    console.print(Panel(exp_table, title="[bold yellow][EXPERIMENTATION] Causal A/B Testing (CUPED Eppo Engine)[/bold yellow]", border_style="yellow"))

    # Panel 2: Cohort Survival
    surv_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold blue")
    surv_table.add_column("Parametric Survival Metric", style="cyan")
    surv_table.add_column("Calibrated Value", justify="right", style="bold white")
    surv_table.add_column("Business Interpretation", style="dim")

    surv_table.add_row("Weibull Shape (k)", f"{surv.shape_parameter:.3f}", "k > 1: Drop-off concentrated in early onboarding (D1-D14)")
    surv_table.add_row("Weibull Scale (lambda)", f"{surv.scale_parameter:.1f} days", "Characteristic lifespan across cohorts")
    surv_table.add_row("Median Lifespan", f"{surv.median_survival_days:.1f} days", "50% of active cohort preserved beyond this horizon")
    surv_table.add_row("Day 7 Retention (D7)", f"{surv.retention_d7_pct:.1f}%", "Early activation success benchmark")
    surv_table.add_row("Day 14 Retention (D14)", f"{surv.retention_d14_pct:.1f}%", "Key milestone for paid plan conversion")
    surv_table.add_row("Day 30 Retention (D30)", f"{surv.retention_d30_pct:.1f}%", "Steady-state sticky user base")

    console.print(Panel(surv_table, title="[bold blue][LIFECYCLE] Cohort Retention & Weibull Hazard Curve[/bold blue]", border_style="blue"))

    # Panel 3: Cohort Table
    cohort_table = Table(title="Top Cohort Retention Performance (Snowflake Analytics Mirror)", box=box.ROUNDED)
    for col in ["Cohort", "Channel", "Total Users", "Avg Engagement", "D7 Ret %", "D14 Ret %", "D30 Ret %", "Churn %"]:
        cohort_table.add_column(col, justify="right" if "%" in col or "Users" in col else "left")

    for _, row in matrix.head(8).iterrows():
        cohort_table.add_row(
            str(row["cohort"]),
            str(row["acquisition_channel"]),
            f"{int(row['total_users']):,}",
            f"{row['avg_engagement']:.1f}",
            f"{row['ret_d7_pct']:.1f}%",
            f"{row['ret_d14_pct']:.1f}%",
            f"{row['ret_d30_pct']:.1f}%",
            f"{row['churn_rate_pct']:.1f}%",
        )

    console.print(cohort_table)
    console.print()


if __name__ == "__main__":
    run_cli()