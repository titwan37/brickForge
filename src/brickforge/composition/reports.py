"""Dependency and license compatibility report generator for composed bricks."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from brickforge.storage.database import DatabaseManager

# Known standard package licenses mapping for common Python dependencies
KNOWN_PACKAGE_LICENSES: Dict[str, str] = {
    "requests": "Apache-2.0",
    "pyjwt": "MIT",
    "pydantic": "MIT",
    "fastapi": "MIT",
    "numpy": "BSD-3-Clause",
    "tree-sitter": "MIT",
    "click": "BSD-3-Clause",
    "pytest": "MIT",
    "cryptography": "Apache-2.0",
    "anyio": "MIT",
    "sqlalchemy": "MIT",
}

PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense"}


@dataclass(frozen=True)
class PackageLicenseInfo:
    """License and version metadata for an external package requirement."""

    ecosystem: str
    package_name: str
    version_constraint: Optional[str] = None
    license: str = "Unknown"
    is_permissive: bool = True


@dataclass(frozen=True)
class SourceOriginInfo:
    """Provenance and origin repository information for a code brick."""

    brick_id: str
    symbol_name: str
    repository_id: str
    relative_path: str
    repo_name: Optional[str] = None


@dataclass
class CompositionDependencyReport:
    """Audit report detailing external packages, licensing, origins, and dependency warnings."""

    report_id: str
    created_at: str
    selected_brick_ids: List[str]
    external_packages: List[PackageLicenseInfo] = field(default_factory=list)
    source_origins: List[SourceOriginInfo] = field(default_factory=list)
    unresolved_warnings: List[str] = field(default_factory=list)
    license_summary: Dict[str, int] = field(default_factory=dict)
    is_compatible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary format."""
        return {
            "report_id": self.report_id,
            "created_at": self.created_at,
            "selected_brick_ids": list(self.selected_brick_ids),
            "external_packages": [asdict(p) for p in self.external_packages],
            "source_origins": [asdict(s) for s in self.source_origins],
            "unresolved_warnings": list(self.unresolved_warnings),
            "license_summary": dict(self.license_summary),
            "is_compatible": self.is_compatible,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class CompositionReportGenerator:
    """Generates license compatibility and dependency reports for code composition."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.db = db

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    def generate_report(
        self,
        brick_ids: Sequence[Union[str, int]],
        allowed_licenses: Optional[Sequence[str]] = None,
    ) -> CompositionDependencyReport:
        """Inspect selected bricks and construct license and provenance audit report."""
        report_id = f"rep_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        allowed_set = set(allowed_licenses) if allowed_licenses else None

        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            external_packages: List[PackageLicenseInfo] = []
            source_origins: List[SourceOriginInfo] = []
            unresolved_warnings: List[str] = []
            seen_pkgs: Set[Tuple[str, str]] = set()

            for b_id in brick_ids:
                cursor.execute(
                    """
                    SELECT cb.row_id, cb.id, cb.symbol_name, sf.relative_path, sf.repository_id, r.name as repo_name
                    FROM code_bricks cb
                    JOIN source_files sf ON sf.row_id = cb.file_id
                    JOIN repositories r ON r.id = sf.repository_id
                    WHERE cb.id = ? OR cb.row_id = ?;
                    """,
                    (str(b_id), int(b_id) if str(b_id).isdigit() else -1),
                )
                brick_row = cursor.fetchone()
                if not brick_row:
                    unresolved_warnings.append(f"Brick ID '{b_id}' not found in catalog.")
                    continue

                row_id = brick_row["row_id"]
                source_origins.append(
                    SourceOriginInfo(
                        brick_id=brick_row["id"],
                        symbol_name=brick_row["symbol_name"],
                        repository_id=brick_row["repository_id"],
                        relative_path=brick_row["relative_path"],
                        repo_name=brick_row["repo_name"],
                    )
                )

                # Query external packages
                cursor.execute(
                    "SELECT ecosystem, package_name, version_constraint FROM external_packages WHERE brick_row_id = ?;",
                    (row_id,),
                )
                for prow in cursor.fetchall():
                    eco = prow["ecosystem"]
                    pkg_name = prow["package_name"].lower()
                    pkg_key = (eco, pkg_name)
                    if pkg_key not in seen_pkgs:
                        seen_pkgs.add(pkg_key)
                        lic = KNOWN_PACKAGE_LICENSES.get(pkg_name, "Unknown")
                        external_packages.append(
                            PackageLicenseInfo(
                                ecosystem=eco,
                                package_name=pkg_name,
                                version_constraint=prow["version_constraint"],
                                license=lic,
                                is_permissive=(lic in PERMISSIVE_LICENSES),
                            )
                        )

                # Query unresolved dependencies
                cursor.execute(
                    """
                    SELECT unresolved_symbol, dependency_type
                    FROM brick_dependencies
                    WHERE source_row_id = ? AND resolution_status = 'unresolved';
                    """,
                    (row_id,),
                )
                for drow in cursor.fetchall():
                    unresolved_warnings.append(
                        f"Unresolved {drow['dependency_type']} dependency: '{drow['unresolved_symbol']}' (from brick {brick_row['symbol_name']})"
                    )

            # Summarize licenses
            license_summary: Dict[str, int] = {}
            is_compatible = True

            for p in external_packages:
                license_summary[p.license] = license_summary.get(p.license, 0) + 1
                if allowed_set and p.license not in allowed_set:
                    is_compatible = False

            return CompositionDependencyReport(
                report_id=report_id,
                created_at=now_iso,
                selected_brick_ids=[str(b) for b in brick_ids],
                external_packages=external_packages,
                source_origins=source_origins,
                unresolved_warnings=unresolved_warnings,
                license_summary=license_summary,
                is_compatible=is_compatible,
            )
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

