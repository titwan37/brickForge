"""Parser diagnostics and error report modeling for source code parsing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from brickforge.parsers.base import ParseDiagnostic


@dataclass
class DiagnosticReport:
    """Consolidated diagnostic report for a parsed source file."""

    file_path: str
    parse_status: str  # 'ok', 'partial', 'failed', 'unsupported'
    diagnostics: List[ParseDiagnostic] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "error")

    def to_json(self) -> str:
        """Serialize diagnostic report to JSON string for database storage."""
        data = {
            "file_path": self.file_path,
            "parse_status": self.parse_status,
            "diagnostics": [
                {
                    "severity": d.severity,
                    "message": d.message,
                    "line": d.line,
                    "column": d.column,
                }
                for d in self.diagnostics
            ],
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> DiagnosticReport:
        """Deserialize diagnostic report from JSON string."""
        if not json_str or not json_str.strip():
            return cls(file_path="", parse_status="ok", diagnostics=[])

        try:
            data = json.loads(json_str)
            diagnostics = [
                ParseDiagnostic(
                    severity=d.get("severity", "error"),
                    message=d.get("message", "Unknown error"),
                    line=d.get("line"),
                    column=d.get("column"),
                )
                for d in data.get("diagnostics", [])
            ]
            return cls(
                file_path=data.get("file_path", ""),
                parse_status=data.get("parse_status", "ok"),
                diagnostics=diagnostics,
            )
        except Exception:
            return cls(
                file_path="",
                parse_status="failed",
                diagnostics=[ParseDiagnostic(severity="error", message=json_str)],
            )


class DiagnosticCollector:
    """Collects and organizes diagnostics encountered during source ingestion."""

    def __init__(self, file_path: str = "") -> None:
        self.file_path = file_path
        self.diagnostics: List[ParseDiagnostic] = []

    def add_error(self, message: str, line: Optional[int] = None, column: Optional[int] = None) -> None:
        self.diagnostics.append(ParseDiagnostic(severity="error", message=message, line=line, column=column))

    def add_warning(self, message: str, line: Optional[int] = None, column: Optional[int] = None) -> None:
        self.diagnostics.append(ParseDiagnostic(severity="warning", message=message, line=line, column=column))

    def add_info(self, message: str, line: Optional[int] = None, column: Optional[int] = None) -> None:
        self.diagnostics.append(ParseDiagnostic(severity="info", message=message, line=line, column=column))

    def create_report(self, parse_status: str) -> DiagnosticReport:
        return DiagnosticReport(
            file_path=self.file_path,
            parse_status=parse_status,
            diagnostics=list(self.diagnostics),
        )

