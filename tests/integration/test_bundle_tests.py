"""Integration tests for bundle unit-test harness execution."""

import sys
import pytest

from brickforge.validation.tests import BundleTestHarness


def test_execution_requires_explicit_opt_in():
    harness = BundleTestHarness()
    files = {"calc.py": "def add(a, b): return a + b\n"}

    # Must raise PermissionError when allow_execution is False
    with pytest.raises(PermissionError, match="explicit opt-in"):
        harness.execute_tests(files, allow_execution=False)


def test_bundle_tests_passing_execution():
    harness = BundleTestHarness()
    files = {
        "calculator.py": """
def multiply(x: int, y: int) -> int:
    return x * y
""",
        "test_calculator.py": """
import unittest
from calculator import multiply

class TestCalculator(unittest.TestCase):
    def test_multiply(self):
        self.assertEqual(multiply(3, 4), 12)
""",
    }

    result = harness.execute_tests(files, allow_execution=True)
    assert result.passed is True
    assert result.exit_code == 0
    assert "OK" in result.stderr or result.exit_code == 0


def test_bundle_tests_failing_execution():
    harness = BundleTestHarness()
    files = {
        "calculator.py": """
def multiply(x: int, y: int) -> int:
    return x + y  # Buggy implementation
""",
        "test_calculator.py": """
import unittest
from calculator import multiply

class TestCalculator(unittest.TestCase):
    def test_multiply(self):
        self.assertEqual(multiply(3, 4), 12)
""",
    }

    result = harness.execute_tests(files, allow_execution=True)
    assert result.passed is False
    assert result.exit_code != 0
    assert "FAIL" in result.stderr or "AssertionError" in result.stderr

