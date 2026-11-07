"""Integration tests for parser error handling, partial-file recovery, and diagnostics."""

import json
from pathlib import Path
import pytest

from brickforge.ingestion.pipeline import IngestionPipeline, RecoverablePythonParser
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def pipeline_env(tmp_path: Path):
    """Sets up a temporary database and IngestionPipeline."""
    db_file = tmp_path / "test_pipeline.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO repositories (id, name, root_path)
            VALUES ('test-repo', 'Test Repo', '/tmp/test_repo');
            """
        )
        conn.commit()

    repo = BrickRepository(db_mgr)
    pipeline = IngestionPipeline(repository_id="test-repo", brick_repository=repo)
    return db_mgr, repo, pipeline


def test_clean_file_parsing(pipeline_env):
    db_mgr, repo, pipeline = pipeline_env

    clean_code = """
def add(a: int, b: int) -> int:
    '''Add two integers.'''
    return a + b

class Calculator:
    def multiply(self, x: int, y: int) -> int:
        return x * y
"""
    file_id, report, brick_ids = pipeline.process_file_content(
        relative_path="src/calc.py",
        content=clean_code,
    )

    assert report.parse_status == "ok"
    assert not report.has_errors
    assert len(brick_ids) >= 2

    sf = repo.get_source_file_by_path("test-repo", "src/calc.py")
    assert sf is not None
    assert sf["parse_status"] == "ok"

    bricks = repo.list_bricks_for_file(file_id)
    brick_names = {b["symbol_name"] for b in bricks}
    assert "add" in brick_names
    assert "Calculator" in brick_names


def test_partially_malformed_file_recovery(pipeline_env):
    db_mgr, repo, pipeline = pipeline_env

    partially_broken_code = """
def clean_function():
    return "intact"

def broken_syntax(
    invalid syntax here !@#$%^&*

class CleanClass:
    def good_method(self):
        return True
"""
    file_id, report, brick_ids = pipeline.process_file_content(
        relative_path="src/corrupted.py",
        content=partially_broken_code,
    )

    # Must be marked as partial with recorded diagnostics
    assert report.parse_status == "partial"
    assert report.has_errors
    assert report.error_count > 0
    assert len(brick_ids) >= 2

    # Verify source_files table records 'partial' status and serialized diagnostics
    sf = repo.get_source_file_by_path("test-repo", "src/corrupted.py")
    assert sf is not None
    assert sf["parse_status"] == "partial"
    diag_data = json.loads(sf["parse_diagnostics"])
    assert diag_data["parse_status"] == "partial"
    assert len(diag_data["diagnostics"]) > 0

    # Verify valid symbols were successfully recovered and persisted
    bricks = repo.list_bricks_for_file(file_id)
    names = {b["symbol_name"] for b in bricks}
    assert "clean_function" in names
    assert "CleanClass" in names


def test_completely_malformed_file_fails_cleanly(pipeline_env):
    db_mgr, repo, pipeline = pipeline_env

    garbage_code = """@@@!!! $$$$$$ %%%%%%%% ++++ ===="""
    file_id, report, brick_ids = pipeline.process_file_content(
        relative_path="src/garbage.py",
        content=garbage_code,
    )

    assert report.parse_status == "failed"
    assert report.has_errors
    assert len(brick_ids) == 0

    sf = repo.get_source_file_by_path("test-repo", "src/garbage.py")
    assert sf is not None
    assert sf["parse_status"] == "failed"

    bricks = repo.list_bricks_for_file(file_id)
    assert len(bricks) == 0


def test_unsupported_file_extension(pipeline_env):
    db_mgr, repo, pipeline = pipeline_env

    file_id, report, brick_ids = pipeline.process_file_content(
        relative_path="docs/notes.md",
        content="# Just a markdown file\nContent...",
    )

    assert report.parse_status == "unsupported"
    assert len(brick_ids) == 0

    sf = repo.get_source_file_by_path("test-repo", "docs/notes.md")
    assert sf is not None
    assert sf["parse_status"] == "unsupported"

