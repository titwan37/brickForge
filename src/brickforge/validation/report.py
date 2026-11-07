"""Structured validation report model capturing verification checks, diagnostics, and environment metadata."""

from __future__ import annotations

import json
import platform
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class ValidationCheckEntry:
    """Individual check result within a validation report."""

    check_name: str
    status: str  # 'passed', 'failed', 'timed_out', 'error'
    duration_ms: float
    message: Optional[str] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Structured report aggregating all checks, statuses, diagnostics, and environment metadata."""

    report_id: str
    bundle_hash: str
    created_at: str
    status: str  # 'passed', 'failed', 'warnings'
    checks: List[ValidationCheckEntry] = field(default_factory=list)
    environment_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == "passed")

    @property
    def failed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status != "passed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation report to dictionary format."""
        return {
            "report_id": self.report_id,
            "bundle_hash": self.bundle_hash,
            "created_at": self.created_at,
            "status": self.status,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "checks": [asdict(c) for c in self.checks],
            "environment_metadata": dict(self.environment_metadata),
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationReport:
        """Construct ValidationReport from dictionary."""
        checks = [
            ValidationCheckEntry(
                check_name=c.get("check_name", ""),
                status=c.get("status", "error"),
                duration_ms=float(c.get("duration_ms", 0.0)),
                message=c.get("message"),
                diagnostics=list(c.get("diagnostics", [])),
            )
            for c in data.get("checks", [])
        ]
        return cls(
            report_id=data.get("report_id", ""),
            bundle_hash=data.get("bundle_hash", ""),
            created_at=data.get("created_at", ""),
            status=data.get("status", "failed"),
            checks=checks,
            environment_metadata=data.get("environment_metadata", {}),
        )

    @classmethod
    def create(
        cls,
        bundle_hash: str,
        checks: Sequence[ValidationCheckEntry],
        extra_env: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        """Convenience factory creating a report with system environment metadata."""
        report_id = f"val_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        all_passed = all(c.status == "passed" for c in checks)
        status = "passed" if all_passed else "failed"

        env_meta = {
            "python_version": sys.version.split()[0],
            "os": platform.system(),
            "platform": platform.platform(),
        }
        if extra_env:
            env_meta.update(extra_env)

        return cls(
            report_id=report_id,
            bundle_hash=bundle_hash,
            created_at=now_iso,
            status=status,
            checks=list(checks),
            environment_metadata=env_meta,
        )

