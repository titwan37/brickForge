"""Performance baseline and scan metrics test suite.

Measures:
- Ingestion throughput (files/sec, symbols/sec)
- Parse and extraction duration
- Database write latency
- Catalog FTS & filtered search query latency
- Peak memory allocation during indexing (tracemalloc)
"""

from dataclasses import dataclass
from pathlib import Path
import time
import tracemalloc
from typing import Dict, List
import pytest

from brickforge.ingestion.discovery import walk_registered_roots
from brickforge.ingestion.pipeline import IngestionPipeline
from brickforge.ingestion.planner import ScanPlanner
from brickforge.search.service import CatalogQuery, CatalogSearchService
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@dataclass
class IngestionBenchmarkReport:
    file_count: int
    symbol_count: int
    scan_plan_seconds: float
    ingestion_seconds: float
    files_per_second: float
    symbols_per_second: float
    avg_search_latency_ms: float
    peak_memory_mb: float


def generate_benchmark_corpus(root: Path, num_modules: int = 30) -> None:
    """Generate a realistic synthetic corpus of Python modules."""
    for i in range(num_modules):
        mod_file = root / f"module_{i:03d}.py"
        code = f'''"""Module {i} benchmark test corpus."""

import os
import sys
from typing import Any, Dict, List, Optional

CONSTANT_{i} = {i} * 42

class ServiceHandler_{i}:
    """Handler service for module {i}."""

    def __init__(self, name: str = "service_{i}") -> None:
        self.name = name
        self.state: Dict[str, Any] = {{"id": {i}}}

    def execute_task(self, param: int) -> int:
        """Process benchmark task computation."""
        result = param + {i}
        return result

    def get_details(self) -> Dict[str, Any]:
        return self.state


def process_module_{i}(data: List[int]) -> List[int]:
    """Top-level helper function for module {i}."""
    handler = ServiceHandler_{i}()
    return [handler.execute_task(x) for x in data]


def utility_{i}_a():
    return {i}


def utility_{i}_b():
    return {i} * 2
'''
        mod_file.write_text(code, encoding="utf-8")


@pytest.fixture
def benchmark_env(tmp_path: Path):
    db_file = tmp_path / "bench.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    corpus_dir = tmp_path / "bench_corpus"
    corpus_dir.mkdir()
    generate_benchmark_corpus(corpus_dir, num_modules=25)

    with db_mgr.connection() as conn:
        conn.execute(
            "INSERT INTO repositories (id, name, root_path) VALUES ('bench-repo', 'Benchmark Repo', ?);",
            (str(corpus_dir),),
        )
        conn.commit()

    brick_repo = BrickRepository(db_mgr)
    planner = ScanPlanner(db_mgr)
    pipeline = IngestionPipeline("bench-repo", brick_repo, root_path=corpus_dir)
    search_service = CatalogSearchService(db_mgr)

    return db_mgr, corpus_dir, brick_repo, planner, pipeline, search_service


def test_ingestion_and_search_baseline(benchmark_env):
    db_mgr, corpus_dir, brick_repo, planner, pipeline, search_service = benchmark_env

    tracemalloc.start()
    t_start = time.perf_counter()

    # 1. Scan Planning Phase
    t_plan_start = time.perf_counter()
    plan = planner.plan_repository_scan("bench-repo", corpus_dir)
    t_plan_end = time.perf_counter()
    plan_duration = t_plan_end - t_plan_start

    assert len(plan.added) == 25

    # 2. Ingestion & AST Extraction & Database Write Phase
    t_ingest_start = time.perf_counter()
    total_bricks = 0
    for action in plan.added:
        sf_id, report, brick_ids = pipeline.process_file_on_disk(action.relative_path)
        assert report.parse_status == "ok"
        total_bricks += len(brick_ids)

    planner.finalize_scan_run(plan.scan_run_id, status="completed", symbols_indexed=total_bricks)
    t_ingest_end = time.perf_counter()
    ingest_duration = t_ingest_end - t_ingest_start

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_memory_mb = peak_mem / (1024 * 1024)
    files_per_sec = len(plan.added) / ingest_duration if ingest_duration > 0 else 0.0
    symbols_per_sec = total_bricks / ingest_duration if ingest_duration > 0 else 0.0

    # 3. Search Latency Benchmark
    search_queries = [
        "execute_task",
        "ServiceHandler",
        "process_module",
        "utility",
        "benchmark",
    ]
    latencies: List[float] = []
    for q in search_queries:
        t0 = time.perf_counter()
        results = search_service.search(CatalogQuery(query=q, limit=10))
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # ms
        assert len(results) > 0

    avg_search_ms = sum(latencies) / len(latencies)

    report = IngestionBenchmarkReport(
        file_count=len(plan.added),
        symbol_count=total_bricks,
        scan_plan_seconds=plan_duration,
        ingestion_seconds=ingest_duration,
        files_per_second=files_per_sec,
        symbols_per_second=symbols_per_sec,
        avg_search_latency_ms=avg_search_ms,
        peak_memory_mb=peak_memory_mb,
    )

    # 4. Assert baseline quality standards
    assert report.file_count == 25
    assert report.symbol_count >= 100  # ~5 symbols per file (class, methods, functions)
    assert report.files_per_second > 5.0, f"Throughput too low: {report.files_per_second:.1f} files/s"
    assert report.avg_search_latency_ms < 100.0, f"Search latency too high: {report.avg_search_latency_ms:.2f}ms"
    assert report.peak_memory_mb < 200.0, f"Peak memory excessive: {report.peak_memory_mb:.2f}MB"


def test_incremental_scan_performance_is_sublinear(benchmark_env):
    """Verify that scanning an unchanged corpus takes negligible time."""
    db_mgr, corpus_dir, brick_repo, planner, pipeline, search_service = benchmark_env

    # Initial scan
    plan = planner.plan_repository_scan("bench-repo", corpus_dir)
    for action in plan.added:
        pipeline.process_file_on_disk(action.relative_path)
    planner.finalize_scan_run(plan.scan_run_id, status="completed")

    # Second scan with 0 modifications
    t0 = time.perf_counter()
    second_plan = planner.plan_repository_scan("bench-repo", corpus_dir)
    t1 = time.perf_counter()

    duration = t1 - t0
    assert len(second_plan.unchanged) == 25
    assert len(second_plan.added) == 0
    assert len(second_plan.changed) == 0
    # Unchanged scan planning must complete in under 500ms
    assert duration < 0.5, f"Unchanged scan was too slow: {duration:.3f}s"

