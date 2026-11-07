"""Integration tests for dependency-aware source code bundling and extraction."""

from pathlib import Path
import pytest

from brickforge.extraction.bundler import SourceBundler
from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def bundle_fixture(tmp_path: Path):
    db_file = tmp_path / "test_bundler.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/tmp/r1');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    file_id = repo.upsert_source_file("r1", "src/services.py", "hash1", "python")

    # Helper 1: clean_string
    h_sym = ExtractedSymbol(
        symbol_name="clean_string",
        qualified_name="services.clean_string",
        kind="function",
        language="python",
        signature="def clean_string(s: str) -> str:",
        signature_hash="sig_clean",
        docstring="Sanitizes string.",
        source_code="def clean_string(s: str) -> str:\n    return s.strip()",
        source_hash="src_clean",
        start_byte=0,
        end_byte=50,
        start_line=1,
        end_line=2,
    )
    h_id = repo.upsert_brick(file_id, h_sym)

    # Target: process_input (calls clean_string, calls external jwt, calls missing_logger)
    t_sym = ExtractedSymbol(
        symbol_name="process_input",
        qualified_name="services.process_input",
        kind="function",
        language="python",
        signature="def process_input(raw: str) -> dict:",
        signature_hash="sig_proc",
        docstring="Process and authenticate raw payload.",
        source_code="def process_input(raw: str) -> dict:\n    sanitized = clean_string(raw)\n    return {'data': sanitized}",
        source_hash="src_proc",
        start_byte=100,
        end_byte=200,
        start_line=10,
        end_line=15,
    )
    t_id = repo.upsert_brick(file_id, t_sym)

    # Dependency: process_input -> clean_string (resolved internal)
    repo.insert_dependency(t_id, "calls", target_row_id=h_id)

    # Dependency: process_input -> jwt.decode (external package)
    repo.insert_dependency(
        t_id,
        "calls",
        unresolved_symbol="jwt.decode",
        resolution_status="external",
    )
    repo.insert_external_package(t_id, "pip", "pyjwt", "import jwt")

    # Dependency: process_input -> missing_func (unresolved)
    repo.insert_dependency(
        t_id,
        "calls",
        unresolved_symbol="missing_func",
        resolution_status="unresolved",
    )

    bundler = SourceBundler(db_mgr)
    return db_mgr, t_id, h_id, bundler


def test_bundle_target_with_helpers_and_imports(bundle_fixture):
    db_mgr, target_id, helper_id, bundler = bundle_fixture

    bundle = bundler.bundle_brick(brick_row_id=target_id, include_helpers=True)

    assert bundle.target_symbol_name == "process_input"
    assert len(bundle.included_brick_ids) == 2

    # Check that import headers were added
    assert "import jwt" in bundle.import_headers
    assert "import jwt" in bundle.bundled_source

    # Check that helper code is in bundled source and appears before target
    assert "def clean_string" in bundle.bundled_source
    assert "def process_input" in bundle.bundled_source
    helper_pos = bundle.bundled_source.index("def clean_string")
    target_pos = bundle.bundled_source.index("def process_input")
    assert helper_pos < target_pos

    # Check external packages and unresolved
    assert "pyjwt" in bundle.external_packages
    assert "missing_func" in bundle.unresolved_dependencies


def test_bundle_standalone_without_helpers(bundle_fixture):
    db_mgr, target_id, helper_id, bundler = bundle_fixture

    bundle = bundler.bundle_brick(brick_row_id=target_id, include_helpers=False)
    assert len(bundle.included_brick_ids) == 1
    assert "def clean_string" not in bundle.bundled_source
    assert "def process_input" in bundle.bundled_source

