"""Isolated unit-test harness for executing tests on extracted code bundles."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class BundleTestExecutionResult:
    """Outcome of running test suites against an extracted bundle."""

    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    command: List[str]


class BundleTestHarness:
    """Safely executes caller-supplied unit tests on extracted bundles in an isolated workspace."""

    def __init__(self, default_timeout_seconds: float = 20.0):
        self.default_timeout_seconds = default_timeout_seconds

    def execute_tests(
        self,
        files: Dict[str, str],
        test_command: Optional[Sequence[str]] = None,
        allow_execution: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> BundleTestExecutionResult:
        """Run tests in isolated temporary workspace with mandatory explicit execution opt-in."""
        # 1. Enforce explicit opt-in requirement
        if not allow_execution:
            raise PermissionError(
                "Execution of bundle tests requires explicit opt-in (allow_execution=True)."
            )

        timeout = timeout_seconds or self.default_timeout_seconds

        with tempfile.TemporaryDirectory(prefix="brickforge_test_") as tmp_dir:
            workspace = Path(tmp_dir)

            # Write files into workspace
            for rel_path, content in files.items():
                target = workspace / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            # Determine test command
            if test_command:
                cmd = list(test_command)
            else:
                # Default to Python built-in unittest discovery
                cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(workspace), "-p", "test_*.py"]

            # Prepare isolated environment
            env = dict(os.environ)
            env["PYTHONPATH"] = str(workspace)
            # Disable implicit network access
            env["PIP_NO_INDEX"] = "1"

            start_time = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(workspace),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return BundleTestExecutionResult(
                    passed=(proc.returncode == 0),
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    duration_ms=round(elapsed_ms, 2),
                    command=cmd,
                )
            except subprocess.TimeoutExpired as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return BundleTestExecutionResult(
                    passed=False,
                    exit_code=-1,
                    stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
                    stderr=f"Test run timed out after {timeout} seconds.",
                    duration_ms=round(elapsed_ms, 2),
                    command=cmd,
                )
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return BundleTestExecutionResult(
                    passed=False,
                    exit_code=-2,
                    stdout="",
                    stderr=str(e),
                    duration_ms=round(elapsed_ms, 2),
                    command=cmd,
                )
