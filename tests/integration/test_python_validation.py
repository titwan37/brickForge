"""Integration tests for Python syntax and compileall validation."""

import pytest

from brickforge.validation.python_checks import PythonBundleValidator


def test_validate_clean_bundle():
    validator = PythonBundleValidator()
    clean_code = """
import math

def calculate_hypotenuse(a: float, b: float) -> float:
    return math.sqrt(a ** 2 + b ** 2)

class Vector:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
"""
    report = validator.validate_code_string(clean_code)
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.files_checked == 1


def test_validate_bundle_syntax_error():
    validator = PythonBundleValidator()
    broken_code = """
def broken_fn():
    if True
        missing_colon = 1
"""
    report = validator.validate_code_string(broken_code, filename="broken.py")
    assert report.is_valid is False
    assert report.error_count == 1
    diag = report.diagnostics[0]
    assert diag.file_path == "broken.py"
    assert "SyntaxError" in diag.error_type or "CompileError" in diag.error_type


def test_validate_multi_file_bundle():
    validator = PythonBundleValidator()
    files = {
        "core/base.py": "class BaseService:\n    def start(self): pass\n",
        "services/auth.py": "from core.base import BaseService\nclass AuthService(BaseService): pass\n",
        "broken/calc.py": "def calc() -> int return 42\n",  # syntax error (missing colon)
    }

    report = validator.validate_files(files)
    assert report.is_valid is False
    assert report.files_checked == 3
    assert report.error_count == 1
    assert report.diagnostics[0].file_path == "broken/calc.py"

