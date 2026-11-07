"""Unit tests for validation report model and environment metadata serialization."""

import json
import pytest

from brickforge.validation.report import ValidationCheckEntry, ValidationReport


def test_validation_report_all_passed():
    checks = [
        ValidationCheckEntry(
            check_name="python_compile",
            status="passed",
            duration_ms=45.2,
            message="Compilation successful.",
        ),
        ValidationCheckEntry(
            check_name="dependency_availability",
            status="passed",
            duration_ms=12.0,
            message="All 3 packages installed.",
        ),
    ]

    report = ValidationReport.create(
        bundle_hash="hash_bundle_123",
        checks=checks,
        extra_env={"runner": "local_sandbox"},
    )

    assert report.passed is True
    assert report.status == "passed"
    assert report.total_checks == 2
    assert report.passed_checks == 2
    assert report.failed_checks == 0
    assert report.bundle_hash == "hash_bundle_123"
    assert "python_version" in report.environment_metadata
    assert report.environment_metadata["runner"] == "local_sandbox"


def test_validation_report_with_failure():
    checks = [
        ValidationCheckEntry(
            check_name="python_compile",
            status="failed",
            duration_ms=30.0,
            message="Syntax error at line 4.",
            diagnostics=[{"file": "mod.py", "line": 4, "error": "SyntaxError"}],
        )
    ]

    report = ValidationReport.create(
        bundle_hash="hash_broken",
        checks=checks,
    )

    assert report.passed is False
    assert report.status == "failed"
    assert report.failed_checks == 1
    assert len(report.checks[0].diagnostics) == 1


def test_validation_report_serialization_roundtrip():
    checks = [
        ValidationCheckEntry(
            check_name="check1",
            status="passed",
            duration_ms=10.5,
        )
    ]
    report = ValidationReport.create("hash_1", checks)

    json_str = report.to_json()
    assert "report_id" in json_str
    assert "hash_1" in json_str

    restored = ValidationReport.from_dict(json.loads(json_str))
    assert restored.report_id == report.report_id
    assert restored.bundle_hash == report.bundle_hash
    assert restored.status == report.status
    assert len(restored.checks) == 1
    assert restored.checks[0].check_name == "check1"
    assert restored.environment_metadata["os"] == report.environment_metadata["os"]

