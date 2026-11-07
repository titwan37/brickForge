"""Integration tests for brick, source file, and dependency persistence."""

import hashlib
import sqlite3
from pathlib import Path
import pytest

from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def test_repo_and_db(tmp_path: Path):
    """Initializes a temporary database with migrated core schema and a test repository."""
    db_file = tmp_path / "test_bricks.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    # Insert a test repository record for foreign key integrity
    with db_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO repositories (id, name, root_path)
            VALUES ('repo-1', 'test_repo', '/tmp/test_repo');
            """
        )
        conn.commit()

    repo = BrickRepository(db_mgr)
    return db_mgr, repo


def _make_symbol(name: str, kind: str, code: str, start: int, end: int) -> ExtractedSymbol:
    return ExtractedSymbol(
        symbol_name=name,
        qualified_name=name,
        kind=kind,
        language="python",
        signature=f"{kind} {name}",
        signature_hash=hashlib.sha256(name.encode()).hexdigest(),
        docstring=f"Documentation for {name}",
        source_code=code,
        source_hash=hashlib.sha256(code.encode()).hexdigest(),
        start_byte=0,
        end_byte=len(code),
        start_line=start,
        end_line=end,
    )


def test_source_file_persistence(test_repo_and_db):
    db_mgr, repo = test_repo_and_db

    # Insert source file
    row_id = repo.upsert_source_file(
        repository_id="repo-1",
        relative_path="src/utils/calc.py",
        file_hash="hash_v1",
        language="python",
        byte_size=120,
        loc=15,
    )
    assert row_id > 0

    # Retrieve source file
    record = repo.get_source_file_by_path("repo-1", "src/utils/calc.py")
    assert record is not None
    assert record["row_id"] == row_id
    assert record["file_hash"] == "hash_v1"
    assert record["loc"] == 15

    # Upsert with new hash and loc (updates existing record)
    updated_row_id = repo.upsert_source_file(
        repository_id="repo-1",
        relative_path="src/utils/calc.py",
        file_hash="hash_v2",
        language="python",
        byte_size=150,
        loc=20,
    )
    assert updated_row_id == row_id

    record_updated = repo.get_source_file_by_path("repo-1", "src/utils/calc.py")
    assert record_updated["file_hash"] == "hash_v2"
    assert record_updated["loc"] == 20


def test_code_brick_persistence_and_fts(test_repo_and_db):
    db_mgr, repo = test_repo_and_db

    file_row_id = repo.upsert_source_file(
        repository_id="repo-1",
        relative_path="src/math/vector.py",
        file_hash="v_hash",
        language="python",
    )

    class_sym = _make_symbol("Vector3D", "class", "class Vector3D:\n    pass", 1, 10)
    brick_row_id = repo.upsert_brick(
        file_row_id=file_row_id,
        symbol=class_sym,
        tags=["geometry", "linalg"],
        portability_score=0.9,
    )
    assert brick_row_id > 0

    brick = repo.get_brick_by_row_id(brick_row_id)
    assert brick is not None
    assert brick["symbol_name"] == "Vector3D"
    assert brick["portability_score"] == 0.9

    # Verify FTS5 automatic indexing via triggers
    with db_mgr.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rowid, symbol_name FROM bricks_fts WHERE bricks_fts MATCH 'Vector3D';")
        match = cursor.fetchone()
        assert match is not None
        assert match[0] == brick_row_id
        assert match[1] == "Vector3D"


def test_dependency_and_package_persistence(test_repo_and_db):
    db_mgr, repo = test_repo_and_db

    file_row_id = repo.upsert_source_file(
        repository_id="repo-1",
        relative_path="src/service/worker.py",
        file_hash="w_hash",
        language="python",
    )

    b1_sym = _make_symbol("ServiceWorker", "class", "class ServiceWorker: pass", 1, 20)
    b2_sym = _make_symbol("run_task", "function", "def run_task(): pass", 22, 35)

    b1_id = repo.upsert_brick(file_row_id, b1_sym)
    b2_id = repo.upsert_brick(file_row_id, b2_sym)

    # 1. Resolved dependency between b1 and b2
    dep_id_1 = repo.insert_dependency(
        source_row_id=b1_id,
        dependency_type="calls",
        target_row_id=b2_id,
        confidence=0.95,
    )
    assert dep_id_1 > 0

    # 2. External dependency
    dep_id_2 = repo.insert_dependency(
        source_row_id=b1_id,
        dependency_type="uses_type",
        unresolved_symbol="pydantic.BaseModel",
        resolution_status="external",
        confidence=1.0,
    )
    assert dep_id_2 > 0

    deps = repo.list_dependencies_for_brick(b1_id)
    assert len(deps) == 2

    # 3. External package
    pkg_id = repo.insert_external_package(
        brick_row_id=b1_id,
        ecosystem="pip",
        package_name="pydantic",
        version_constraint=">=2.0.0",
        import_statement="from pydantic import BaseModel",
    )
    assert pkg_id > 0

    pkgs = repo.list_external_packages_for_brick(b1_id)
    assert len(pkgs) == 1
    assert pkgs[0]["package_name"] == "pydantic"
    assert pkgs[0]["version_constraint"] == ">=2.0.0"
