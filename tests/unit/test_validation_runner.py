"""Unit tests for isolated validation runner and Python compile checks."""

from pathlib import Path
import pytest

from brickforge.validation.runner import (
    BaseValidationCheck,
    CheckResult,
    IsolatedValidationRunner,
    PythonCompileCheck,
)


def test_python_compile_check_success():
    runner = IsolatedValidationRunner()
    valid_code = "def add(x: int, y: int) -> int:\n    return x + y\n"

    results = runner.run_checks(valid_code)
    assert len(results) == 1
    res = results[0]
    assert res.check_name == "python_compile"
    assert res.status == "passed"
    assert res.passed is True
    assert res.exit_code == 0


def test_python_compile_check_syntax_error():
    runner = IsolatedValidationRunner()
    broken_code = "def broken(\n    missing closing paren and invalid syntax !@#\n"

    results = runner.run_checks(broken_code)
    assert len(results) == 1
    res = results[0]
    assert res.check_name == "python_compile"
    assert res.status == "failed"
    assert res.passed is False
    assert "Syntax or compile error" in res.message


def test_multi_file_workspace_validation():
    runner = IsolatedValidationRunner()
    files = {
        "utils/helpers.py": "def helper(): return 1\n",
        "app/main.py": "from utils.helpers import helper\ndef run(): return helper()\n",
    }

    results = runner.run_checks(files)
    assert len(results) == 1
    assert results[0].passed is True


def test_custom_validation_check():
    class FileSizeCheck(BaseValidationCheck):
        @property
        def name(self) -> str:
            return "file_size_check"

        def execute(self, workspace_path: Path, target_filename: str) -> CheckResult:
            target = workspace_path / target_filename
            size = target.stat().st_size
            if size < 500:
                return CheckResult(self.name, "passed", 1.0, f"Size {size} within limit.")
            return CheckResult(self.name, "failed", 1.0, f"Size {size} exceeds limit.")

    runner = IsolatedValidationRunner(default_checks=[FileSizeCheck()])
    results = runner.run_checks("print('hello')\n")
    assert len(results) == 1
    assert results[0].check_name == "file_size_check"
    assert results[0].passed is True

