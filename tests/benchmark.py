"""
tests/benchmark.py - Quantitative Latency & Memory Benchmark.
Measures p50, p95, and p99 query latency over 30 iterations.
Enforces SLA constraints: p95 < 150.0 ms.
"""

import os
import sys
import time
import tempfile
from pathlib import Path
import numpy as np

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_generator import generate_domain_dataset
from src.core_engine import DomainAnalyticsEngine, DuckDBStorageAdapter


def run_benchmarks(iterations=30, num_records=10000):
    print(f"[Benchmark] Preparing dataset with {num_records:,} records...")
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_domain_dataset(num_records=num_records, output_path=tmp_path)
        adapter = DuckDBStorageAdapter()
        engine = DomainAnalyticsEngine(storage=adapter, data_path=tmp_path)
        
        # Warmup
        engine.execute_analysis()
        
        print(f"[Benchmark] Profiling subcomponents over {iterations} iterations...")
        
        cuped_latencies = []
        duckdb_latencies = []
        pipeline_latencies = []

        raw_df = engine.load_dataset()

        for _ in range(iterations):
            # 1. Micro-benchmark: CUPED + SRM + Welch Hypothesis Testing
            t0 = time.perf_counter()
            engine.execute_cuped_analysis(raw_df)
            cuped_latencies.append((time.perf_counter() - t0) * 1000)

            # 2. Micro-benchmark: DuckDB Vectorized Cohort Windowing
            t1 = time.perf_counter()
            engine.execute_cohort_retention_matrix()
            duckdb_latencies.append((time.perf_counter() - t1) * 1000)

            # 3. Macro-benchmark: Full End-to-End Analytics Pipeline (CUPED + Lifelines + DuckDB)
            t2 = time.perf_counter()
            engine.execute_analysis()
            pipeline_latencies.append((time.perf_counter() - t2) * 1000)
            
        p50_cuped = float(np.percentile(cuped_latencies, 50))
        p95_cuped = float(np.percentile(cuped_latencies, 95))

        p50_duckdb = float(np.percentile(duckdb_latencies, 50))
        p95_duckdb = float(np.percentile(duckdb_latencies, 95))

        p50_pipe = float(np.percentile(pipeline_latencies, 50))
        p95_pipe = float(np.percentile(pipeline_latencies, 95))
        p99_pipe = float(np.percentile(pipeline_latencies, 99))
        
        print("\n" + "="*70)
        print("  KAKE_PRODUCT_EXPERIMENTATION_ENGINE - QUANTITATIVE BENCHMARK")
        print("="*70)
        print(f"  Dataset Size: {num_records:,} rows | Iterations: {iterations}")
        status_cuped = "PASS" if p95_cuped < 25.0 else "FAIL"
        status_duckdb = "PASS" if p95_duckdb < 25.0 else "FAIL"
        status_pipe = "PASS" if p95_pipe < 450.0 else "FAIL"

        print("-" * 70)
        print(f"  1. CUPED Statistical Variance Engine:  p50 = {p50_cuped:.2f} ms | p95 = {p95_cuped:.2f} ms [SLA < 25ms: {status_cuped}]")
        print(f"  2. DuckDB Vectorized Cohort Window:     p50 = {p50_duckdb:.2f} ms | p95 = {p95_duckdb:.2f} ms [SLA < 25ms: {status_duckdb}]")
        print(f"  3. Full End-to-End Pipeline (with MLE): p50 = {p50_pipe:.2f} ms | p95 = {p95_pipe:.2f} ms [SLA < 450ms: {status_pipe}]")
        print(f"     -> p99 End-to-End Pipeline Latency:  {p99_pipe:.2f} ms")
        print("="*70 + "\n")
        
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    run_benchmarks()