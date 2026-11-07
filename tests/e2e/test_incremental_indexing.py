"""End-to-end tests for incremental re-indexing, modification updates, and deletion reconciliation."""

from pathlib import Path
import pytest

from brickforge.ingestion.discovery import walk_registered_roots
from brickforge.ingestion.pipeline import IngestionPipeline
from brickforge.ingestion.planner import ScanPlanner
from brickforge.search.service import CatalogQuery, CatalogSearchService
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def repo_env(tmp_path: Path):
    db_file = tmp_path / "incremental.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    repo_dir = tmp_path / "dynamic_repo"
    repo_dir.mkdir()

    with db_mgr.connection() as conn:
        conn.execute(
            "INSERT INTO repositories (id, name, root_path) VALUES ('dyn-repo', 'Dynamic Repo', ?);",
            (str(repo_dir),),
        )
        conn.commit()

    f1 = repo_dir / "math_ops.py"
    f1.write_text("def add(a, b): return a + b\n", encoding="utf-8")

    f2 = repo_dir / "str_ops.py"
    f2.write_text("def uppercase(s): return s.upper()\n", encoding="utf-8")

    f3 = repo_dir / "old_feature.py"
    f3.write_text("def legacy_code(): return 0\n", encoding="utf-8")

    brick_repo = BrickRepository(db_mgr)
    planner = ScanPlanner(db_mgr)
    pipeline = IngestionPipeline("dyn-repo", brick_repo, root_path=repo_dir)

    return db_mgr, repo_dir, brick_repo, planner, pipeline


def test_incremental_scan_lifecycle(repo_env):
    db_mgr, repo_dir, brick_repo, planner, pipeline = repo_env

    # -------------------------------------------------------------
    # Step 1: Initial Fresh Scan
    # -------------------------------------------------------------
    plan_1 = planner.plan_repository_scan("dyn-repo", repo_dir)
    assert len(plan_1.added) == 3
    assert len(plan_1.changed) == 0
    assert len(plan_1.unchanged) == 0
    assert len(plan_1.deleted) == 0

    # Ingest added files
    for item in plan_1.added:
        pipeline.process_file_on_disk(item.relative_path)

    planner.finalize_scan_run(plan_1.scan_run_id, status="completed", files_seen=3, files_changed=3)

    with db_mgr.connection() as conn:
        count_bricks_1 = conn.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
    assert count_bricks_1 == 3

    # -------------------------------------------------------------
    # Step 2: Unchanged Files are Skipped (Idempotent scan)
    # -------------------------------------------------------------
    plan_2 = planner.plan_repository_scan("dyn-repo", repo_dir)
    assert len(plan_2.added) == 0
    assert len(plan_2.changed) == 0
    assert len(plan_2.unchanged) == 3
    assert len(plan_2.deleted) == 0

    planner.finalize_scan_run(plan_2.scan_run_id, status="completed", files_seen=3, files_skipped=3)

    with db_mgr.connection() as conn:
        count_bricks_2 = conn.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
    assert count_bricks_2 == count_bricks_1

    # -------------------------------------------------------------
    # Step 3: Changed Files Trigger Update
    # -------------------------------------------------------------
    # Modify str_ops.py: add new function
    f2 = repo_dir / "str_ops.py"
    f2.write_text("def uppercase(s): return s.upper()\ndef lowercase(s): return s.lower()\n", encoding="utf-8")

    plan_3 = planner.plan_repository_scan("dyn-repo", repo_dir)
    assert len(plan_3.changed) == 1
    assert plan_3.changed[0].relative_path == "str_ops.py"
    assert len(plan_3.unchanged) == 2

    for item in plan_3.changed:
        pipeline.process_file_on_disk(item.relative_path)

    planner.finalize_scan_run(plan_3.scan_run_id, status="completed", files_seen=3, files_changed=1, files_skipped=2)

    with db_mgr.connection() as conn:
        count_bricks_3 = conn.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
    assert count_bricks_3 == 4  # add, uppercase, lowercase, legacy_code

    # Search for newly added symbol
    search_svc = CatalogSearchService(db_mgr)
    hits = search_svc.search(CatalogQuery(query="lowercase"))
    assert len(hits) == 1
    assert hits[0].symbol_name == "lowercase"

    # -------------------------------------------------------------
    # Step 4: Deleted Files are Reconciled and Removed via Cascade
    # -------------------------------------------------------------
    f3 = repo_dir / "old_feature.py"
    f3.unlink()

    plan_4 = planner.plan_repository_scan("dyn-repo", repo_dir)
    assert len(plan_4.deleted) == 1
    assert plan_4.deleted[0].relative_path == "old_feature.py"
    assert len(plan_4.unchanged) == 2

    # Reconcile deletions
    with db_mgr.connection() as conn:
        for d in plan_4.deleted:
            conn.execute(
                "DELETE FROM source_files WHERE repository_id = ? AND relative_path = ?;",
                ("dyn-repo", d.relative_path),
            )
        conn.commit()

    planner.finalize_scan_run(plan_4.scan_run_id, status="completed", files_seen=2, files_deleted=1, files_skipped=2)

    # Verify legacy_code brick was cascade deleted
    with db_mgr.connection() as conn:
        count_bricks_4 = conn.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
        legacy_found = conn.execute("SELECT COUNT(*) FROM code_bricks WHERE symbol_name = 'legacy_code';").fetchone()[0]
    assert count_bricks_4 == 3
    assert legacy_found == 0

    # Verify FTS index also updated
    hits_legacy = search_svc.search(CatalogQuery(query="legacy_code"))
    assert len(hits_legacy) == 0
