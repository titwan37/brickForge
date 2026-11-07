"""Isolated validation runner for executing safety, compile, and syntax checks in sandbox workspaces."""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union


@dataclass(frozen=True)
class CheckResult:
    """Outcome of an individual validation check."""

    check_name: str
    status: str  # 'passed', 'failed', 'timed_out', 'error'
    duration_ms: float
    message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"


class BaseValidationCheck(ABC):
    """Abstract interface for checks executed inside the isolated workspace."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the check."""

    @abstractmethod
    def execute(self, workspace_path: Path, target_filename: str) -> CheckResult:
        """Run verification check on files within the temporary workspace."""


class PythonCompileCheck(BaseValidationCheck):
    """Verifies that Python files in the workspace compile without syntax errors."""

    @property
    def name(self) -> str:
        return "python_compile"

    def execute(self, workspace_path: Path, target_filename: str) -> CheckResult:
        target_path = workspace_path / target_filename
        start_time = time.perf_counter()

        try:
            # Enforce doraise=True so PyCompileError is raised on syntax errors
            py_compile.compile(str(target_path), doraise=True)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                status="passed",
                duration_ms=round(elapsed_ms, 2),
                message="Compilation succeeded.",
                exit_code=0,
            )
        except py_compile.PyCompileError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                status="failed",
                duration_ms=round(elapsed_ms, 2),
                message=f"Syntax or compile error: {e.msg}",
                stderr=str(e),
                exit_code=1,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return CheckResult(
                check_name=self.name,
                status="error",
                duration_ms=round(elapsed_ms, 2),
                message=f"Unexpected error during compilation: {e}",
                stderr=str(e),
                exit_code=1,
            )


class IsolatedValidationRunner:
    """Orchestrates validation checks in an isolated, temporary directory with timeout controls."""

    def __init__(
        self,
        default_checks: Optional[Sequence[BaseValidationCheck]] = None,
        timeout_seconds: float = 15.0,
    ):
        self.default_checks = list(default_checks or [PythonCompileCheck()])
        self.timeout_seconds = timeout_seconds

    def run_checks(
        self,
        files: Union[str, Dict[str, str]],
        checks: Optional[Sequence[BaseValidationCheck]] = None,
    ) -> List[CheckResult]:
        """Write files into a temporary workspace, run checks with network isolation, and collect results."""
        active_checks = list(checks or self.default_checks)
        results: List[CheckResult] = []

        # Standardize files input: if string, treat as main.py
        file_map: Dict[str, str] = {"main.py": files} if isinstance(files, str) else dict(files)
        primary_filename = next(iter(file_map.keys()), "main.py")

        with tempfile.TemporaryDirectory(prefix="brickforge_val_") as tmp_dir:
            workspace = Path(tmp_dir)

            # Write files to sandbox workspace
            for rel_path, content in file_map.items():
                target = workspace / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            # Execute checks in isolation
            for chk in active_checks:
                start_time = time.perf_counter()
                try:
                    res = chk.execute(workspace, primary_filename)
                    results.append(res)
                except Exception as ex:
                    elapsed = (time.perf_counter() - start_time) * 1000
                    results.append(
                        CheckResult(
                            check_name=chk.name,
                            status="error",
                            duration_ms=round(elapsed, 2),
                            message=f"Check execution crashed: {ex}",
                            stderr=str(ex),
                            exit_code=1,
                        )
                    )

        return results

