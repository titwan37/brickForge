"""Unit tests for dependency availability and version compatibility checks."""

import pytest

from brickforge.validation.dependencies import (
    DependencyAvailabilityChecker,
    check_version_satisfaction,
)


def test_version_satisfaction_logic():
    assert check_version_satisfaction("2.4.0", ">=2.0.0") is True
    assert check_version_satisfaction("1.9.5", ">=2.0.0") is False
    assert check_version_satisfaction("3.1.2", "==3.1.2") is True
    assert check_version_satisfaction("3.1.3", "==3.1.2") is False
    assert check_version_satisfaction("2.5.0", "^2.1.0") is True
    assert check_version_satisfaction("3.0.0", "^2.1.0") is False


def test_dependency_checker_distinguishes_statuses():
    env = {
        "pydantic": "2.5.1",
        "requests": "2.28.0",
        "old_lib": "0.9.0",
    }
    checker = DependencyAvailabilityChecker(environment_packages=env)

    reqs = [
        # 1. Satisfied
        {"package_name": "pydantic", "version_constraint": ">=2.0.0"},
        # 2. Incompatible
        {"package_name": "old_lib", "version_constraint": ">=1.0.0"},
        # 3. Missing
        {"package_name": "fastapi", "version_constraint": ">=0.100.0"},
        # 4. Unknown constraint
        {"package_name": "requests", "version_constraint": "invalid_spec"},
    ]

    report = checker.check_requirements(reqs)

    assert report.is_all_satisfied is False
    assert report.missing == ["fastapi"]
    assert report.incompatible == ["old_lib"]
    assert report.unknown == ["requests"]

    item_map = {i.package_name: i for i in report.items}
    assert item_map["pydantic"].status == "satisfied"
    assert item_map["pydantic"].installed_version == "2.5.1"


def test_checker_from_lockfile():
    lockfile_content = """
# Generated lockfile
pydantic==2.6.0
pyjwt==2.8.0
numpy==1.26.4
"""
    checker = DependencyAvailabilityChecker.from_lockfile_text(lockfile_content)

    report = checker.check_requirements(["pydantic>=2.0.0", "pyjwt==2.8.0", "missing_pkg"])
    assert report.missing == ["missing_pkg"]
    assert "pydantic" not in report.missing
    assert "pyjwt" not in report.missing

