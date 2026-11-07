"""Python compile and syntax validation runner using compileall and py_compile."""

from __future__ import annotations

import compileall
import os
import py_compile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass(frozen=True)
class PythonDiagnostic:
    """Compilation or syntax error diagnostic."""

    file_path: str
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    error_type: str = "CompileError"


@dataclass
class PythonValidationReport:
    """Complete report of compileall and syntax validation across a bundle."""

    is_valid: bool
    files_checked: int
    diagnostics: List[PythonDiagnostic] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def error_count(self) -> int:
        return len(self.diagnostics)


class PythonBundleValidator:
    """Runs isolated py_compile and compileall validation against extracted Python bundles."""

    def validate_code_string(self, source_code: str, filename: str = "bundle.py") -> PythonValidationReport:
        """Validate a single source code string by compiling in an isolated temporary workspace."""
        return self.validate_files({filename: source_code})

    def validate_files(self, file_map: Dict[str, str]) -> PythonValidationReport:
        """Write bundle files to an isolated temporary directory and execute compile checks."""
        start_time = time.perf_counter()
        diagnostics: List[PythonDiagnostic] = []

        with tempfile.TemporaryDirectory(prefix="brickforge_py_val_") as tmp_dir:
            workspace = Path(tmp_dir)

            # 1. Write bundle files
            written_files: List[Path] = []
            for rel_path, content in file_map.items():
                target = workspace / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                written_files.append(target)

            # 2. Run py_compile per file to capture exact line and syntax diagnostics
            for fpath in written_files:
                try:
                    py_compile.compile(str(fpath), doraise=True)
                except py_compile.PyCompileError as e:
                    rel_name = str(fpath.relative_to(workspace)).replace("\\", "/")
                    # Extract line from exception if available
                    line_no = None
                    if hasattr(e, "lineno") and e.lineno:
                        line_no = e.lineno
                    diagnostics.append(
                        PythonDiagnostic(
                            file_path=rel_name,
                            message=e.msg,
                            line_number=line_no,
                            error_type="SyntaxError" if "SyntaxError" in str(e) else "CompileError",
                        )
                    )

            # 3. Also run compileall on the directory as a whole
            compile_success = compileall.compile_dir(
                dir=str(workspace),
                force=True,
                quiet=1,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        is_valid = (len(diagnostics) == 0) and bool(compile_success)

        return PythonValidationReport(
            is_valid=is_valid,
            files_checked=len(file_map),
            diagnostics=diagnostics,
            duration_ms=round(elapsed_ms, 2),
        )

