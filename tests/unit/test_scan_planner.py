"""Unit tests for the incremental scan planner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from brickforge.ingestion.ignore_rules import IgnoreRules
from brickforge.ingestion.planner import PlannedFileAction, ScanPlan, ScanPlanner
from brickforge.storage.database import DatabaseManager


class TestScanPlanner:
    """Tests for ScanPlanner and ScanPlan."""

    @pytest.fixture
    def db_manager(self, tmp_path: Path) -> DatabaseManager:
        db_file = tmp_path / "test_planner.db"
        manager = DatabaseManager(db_path=db_file)
        manager.apply_migrations()
        # Seed test repository
        with manager.connection() as conn:
            conn.execute(
                "INSERT INTO repositories (id, name, root_path) VALUES ('repo-1', 'Test Repo', '/dummy');"
            )
            conn.commit()
        return manager

    def test_plan_fresh_repository_all_added(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
        (repo_dir / "util.py").write_text("def helper(): pass", encoding="utf-8")

        planner = ScanPlanner(db_manager)
        plan = planner.plan_repository_scan("repo-1", repo_dir)

        assert len(plan.added) == 2
        assert len(plan.changed) == 0
        assert len(plan.unchanged) == 0
        assert len(plan.deleted) == 0
        assert plan.files_seen == 2
        assert plan.files_changed == 2
        assert plan.files_skipped == 0
        assert plan.files_deleted == 0

        # Verify scan_runs record was created
        with db_manager.connection() as conn:
            run = conn.execute("SELECT status, files_seen, files_changed FROM scan_runs WHERE id = ?;", (plan.scan_run_id,)).fetchone()
            assert run is not None
            assert run[0] == "running"
            assert run[1] == 2
            assert run[2] == 2

    def test_plan_incremental_scan_unchanged(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        file_path = repo_dir / "main.py"
        file_path.write_text("print('hello')", encoding="utf-8")

        planner = ScanPlanner(db_manager)
        first_plan = planner.plan_repository_scan("repo-1", repo_dir)
        action = first_plan.added[0]

        # Simulate storing the file after first scan
        with db_manager.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_files (id, repository_id, relative_path, language, file_hash, byte_size, modified_ns)
                VALUES (?, 'repo-1', ?, ?, ?, ?, ?);
                """,
                (action.file_id, action.relative_path, action.language, action.fingerprint.file_hash, action.fingerprint.byte_size, action.fingerprint.modified_ns),
            )
            conn.commit()

        # Second scan: file is unchanged
        second_plan = planner.plan_repository_scan("repo-1", repo_dir)
        assert len(second_plan.added) == 0
        assert len(second_plan.changed) == 0
        assert len(second_plan.unchanged) == 1
        assert second_plan.unchanged[0].relative_path == "main.py"
        assert second_plan.files_skipped == 1

    def test_plan_incremental_scan_modified_file(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        file_path = repo_dir / "main.py"
        file_path.write_text("print('version 1')", encoding="utf-8")

        planner = ScanPlanner(db_manager)
        first_plan = planner.plan_repository_scan("repo-1", repo_dir)
        action = first_plan.added[0]

        # Seed database with version 1
        with db_manager.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_files (id, repository_id, relative_path, language, file_hash, byte_size, modified_ns)
                VALUES (?, 'repo-1', ?, ?, ?, ?, ?);
                """,
                (action.file_id, action.relative_path, action.language, action.fingerprint.file_hash, action.fingerprint.byte_size, action.fingerprint.modified_ns),
            )
            conn.commit()

        # Modify file content on disk
        file_path.write_text("print('version 2 - updated content')", encoding="utf-8")

        second_plan = planner.plan_repository_scan("repo-1", repo_dir)
        assert len(second_plan.added) == 0
        assert len(second_plan.changed) == 1
        assert len(second_plan.unchanged) == 0
        assert second_plan.changed[0].action_type == "update"
        assert second_plan.changed[0].previous_hash == action.fingerprint.file_hash
        assert second_plan.changed[0].fingerprint.file_hash != action.fingerprint.file_hash

    def test_plan_force_full_scan(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        file_path = repo_dir / "main.py"
        file_path.write_text("print('stable')", encoding="utf-8")

        planner = ScanPlanner(db_manager)
        plan1 = planner.plan_repository_scan("repo-1", repo_dir)
        act = plan1.added[0]

        with db_manager.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_files (id, repository_id, relative_path, language, file_hash, byte_size, modified_ns)
                VALUES (?, 'repo-1', ?, ?, ?, ?, ?);
                """,
                (act.file_id, act.relative_path, act.language, act.fingerprint.file_hash, act.fingerprint.byte_size, act.fingerprint.modified_ns),
            )
            conn.commit()

        # Force full scan marks identical file as changed/update
        force_plan = planner.plan_repository_scan("repo-1", repo_dir, force_full_scan=True)
        assert len(force_plan.changed) == 1
        assert len(force_plan.unchanged) == 0

    def test_plan_deleted_file_detection_and_reconciliation(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()

        planner = ScanPlanner(db_manager)

        # Seed database with a file that no longer exists on disk
        with db_manager.connection() as conn:
            conn.execute(
                """
                INSERT INTO source_files (id, repository_id, relative_path, language, file_hash, byte_size, modified_ns)
                VALUES ('f_old', 'repo-1', 'deleted_file.py', 'python', 'old_hash', 100, 1000);
                """,
            )
            conn.commit()

        plan = planner.plan_repository_scan("repo-1", repo_dir)
        assert len(plan.deleted) == 1
        assert plan.deleted[0].action_type == "delete"
        assert plan.deleted[0].relative_path == "deleted_file.py"
        assert plan.deleted[0].file_id == "f_old"

        # Reconcile deletions
        removed_count = planner.reconcile_deleted_files("repo-1", plan)
        assert removed_count == 1

        with db_manager.connection() as conn:
            remaining = conn.execute("SELECT COUNT(*) FROM source_files WHERE id = 'f_old';").fetchone()[0]
            assert remaining == 0

    def test_dry_run_does_not_mutate_scan_runs(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        (repo_dir / "foo.py").write_text("x = 1", encoding="utf-8")

        planner = ScanPlanner(db_manager)
        plan = planner.plan_repository_scan("repo-1", repo_dir, dry_run=True)

        assert plan.is_dry_run is True
        assert len(plan.added) == 1

        with db_manager.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM scan_runs WHERE id = ?;", (plan.scan_run_id,)).fetchone()[0]
            assert count == 0

    def test_finalize_scan_run(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        (repo_dir / "foo.py").write_text("x = 1", encoding="utf-8")

        planner = ScanPlanner(db_manager)
        plan = planner.plan_repository_scan("repo-1", repo_dir, dry_run=False)

        planner.finalize_scan_run(
            scan_run_id=plan.scan_run_id,
            status="completed",
            symbols_indexed=5,
            errors_count=0,
        )

        with db_manager.connection() as conn:
            run = conn.execute("SELECT status, finished_at, symbols_indexed FROM scan_runs WHERE id = ?;", (plan.scan_run_id,)).fetchone()
            assert run[0] == "completed"
            assert run[1] is not None
            assert run[2] == 5

    def test_ignore_rules_filtering(self, db_manager: DatabaseManager, tmp_path: Path):
        repo_dir = tmp_path / "repo_root"
        repo_dir.mkdir()
        (repo_dir / "normal.py").write_text("print(1)", encoding="utf-8")
        (repo_dir / "temp.log").write_text("log data", encoding="utf-8")

        # Create custom ignore rules ignoring *.log
        ignore = IgnoreRules()
        ignore.ignore_patterns.append("*.log")

        planner = ScanPlanner(db_manager)
        plan = planner.plan_repository_scan("repo-1", repo_dir, ignore_rules=ignore)

        assert len(plan.added) == 1
        assert plan.added[0].relative_path == "normal.py"

