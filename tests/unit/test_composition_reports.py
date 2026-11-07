"""Unit tests for composition dependency and license compatibility reports."""

import json
from pathlib import Path
import pytest

from brickforge.composition.reports import CompositionReportGenerator
from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def report_env(tmp_path: Path):
    db_file = tmp_path / "test_reports.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('repo-1', 'MainRepo', '/tmp/repo1');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    file_id = repo.upsert_source_file("repo-1", "src/client.py", "hash1", "python")

    sym = ExtractedSymbol(
        symbol_name="api_client",
        qualified_name="client.api_client",
        kind="function",
        language="python",
        signature="def api_client():",
        signature_hash="sig_c",
        docstring="Client wrapper.",
        source_code="def api_client(): pass",
        source_hash="src_c",
        start_byte=0,
        end_byte=30,
        start_line=1,
        end_line=2,
    )
    b_id = repo.upsert_brick(file_id, sym, brick_id="brick_client_1")

    # Add external packages: pyjwt (MIT) and requests (Apache-2.0)
    repo.insert_external_package(b_id, "pip", "pyjwt", "import jwt")
    repo.insert_external_package(b_id, "pip", "requests", "import requests")

    # Add unresolved dependency
    repo.insert_dependency(
        b_id,
        "calls",
        unresolved_symbol="missing_audit_log",
        resolution_status="unresolved",
    )

    generator = CompositionReportGenerator(db_mgr)
    return db_mgr, b_id, generator


def test_dependency_and_license_report_generation(report_env):
    db_mgr, brick_id, generator = report_env

    report = generator.generate_report(brick_ids=["brick_client_1"])

    assert len(report.source_origins) == 1
    assert report.source_origins[0].repository_id == "repo-1"
    assert report.source_origins[0].relative_path == "src/client.py"

    pkg_names = {p.package_name for p in report.external_packages}
    assert "pyjwt" in pkg_names
    assert "requests" in pkg_names

    # Verify licenses
    licenses = {p.package_name: p.license for p in report.external_packages}
    assert licenses["pyjwt"] == "MIT"
    assert licenses["requests"] == "Apache-2.0"

    # Verify license summary
    assert report.license_summary["MIT"] == 1
    assert report.license_summary["Apache-2.0"] == 1

    # Verify unresolved warnings
    assert len(report.unresolved_warnings) >= 1
    assert any("missing_audit_log" in w for w in report.unresolved_warnings)


def test_license_compatibility_enforcement(report_env):
    db_mgr, brick_id, generator = report_env

    # 1. Compatible when both MIT and Apache-2.0 are allowed
    rep_compat = generator.generate_report(
        brick_ids=["brick_client_1"],
        allowed_licenses=["MIT", "Apache-2.0"],
    )
    assert rep_compat.is_compatible is True

    # 2. Incompatible when only MIT is allowed (requests is Apache-2.0)
    rep_incompat = generator.generate_report(
        brick_ids=["brick_client_1"],
        allowed_licenses=["MIT"],
    )
    assert rep_incompat.is_compatible is False


def test_report_json_serialization(report_env):
    db_mgr, brick_id, generator = report_env
    report = generator.generate_report(brick_ids=["brick_client_1"])
    json_str = report.to_json()
    assert "report_id" in json_str
    assert "pyjwt" in json_str

