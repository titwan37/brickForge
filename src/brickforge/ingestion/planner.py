"""Incremental scan planner for BrickForge.

Compares discovered filesystem files and fingerprints against stored database state
to classify files into added, changed, unchanged, and deleted actions, maintaining
accurate scan-run counters and supporting dry-run planning.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from brickforge.ingestion.discovery import get_language_hint, walk_registered_roots
from brickforge.ingestion.fingerprints import FileFingerprint, generate_fingerprint
from brickforge.ingestion.ignore_rules import IgnoreRules
from brickforge.storage.database import DatabaseManager


@dataclass
class PlannedFileAction:
    """Action planned for an individual source file."""

    action_type: str  # 'add', 'update', 'skip', 'delete'
    relative_path: str
    file_id: str
    fingerprint: Optional[FileFingerprint] = None
    language: Optional[str] = None
    previous_hash: Optional[str] = None


@dataclass
class ScanPlan:
    """Complete execution plan and counters for an incremental scan."""

    repository_id: str
    scan_run_id: str
    added: List[PlannedFileAction] = field(default_factory=list)
    changed: List[PlannedFileAction] = field(default_factory=list)
    unchanged: List[PlannedFileAction] = field(default_factory=list)
    deleted: List[PlannedFileAction] = field(default_factory=list)
    is_dry_run: bool = False

    @property
    def files_seen(self) -> int:
        return len(self.added) + len(self.changed) + len(self.unchanged)

    @property
    def files_changed(self) -> int:
        return len(self.added) + len(self.changed)

    @property
    def files_skipped(self) -> int:
        return len(self.unchanged)

    @property
    def files_deleted(self) -> int:
        return len(self.deleted)


class ScanPlanner:
    """Plans incremental repository scans by comparing filesystem fingerprints with database state."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_stored_files(self, conn: sqlite3.Connection, repository_id: str) -> Dict[str, Dict[str, Union[str, int]]]:
        """Retrieve stored file records for a repository, keyed by normalized relative path."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, relative_path, file_hash, byte_size, modified_ns, language
            FROM source_files
            WHERE repository_id = ?;
            """,
            (repository_id,),
        )
        stored: Dict[str, Dict[str, Union[str, int]]] = {}
        for row in cursor.fetchall():
            stored[row[1]] = {
                "id": row[0],
                "relative_path": row[1],
                "file_hash": row[2],
                "byte_size": row[3],
                "modified_ns": row[4],
                "language": row[5],
            }
        return stored

    def plan_repository_scan(
        self,
        repository_id: str,
        root_path: Union[str, Path],
        ignore_rules: Optional[IgnoreRules] = None,
        force_full_scan: bool = False,
        dry_run: bool = False,
        scan_run_id: Optional[str] = None,
    ) -> ScanPlan:
        """Create a ScanPlan classifying files as added, changed, unchanged, or deleted."""
        run_id = scan_run_id or f"scan_{uuid.uuid4().hex[:16]}"
        plan = ScanPlan(repository_id=repository_id, scan_run_id=run_id, is_dry_run=dry_run)

        root = Path(root_path).resolve()
        active_ignore = ignore_rules or IgnoreRules()

        with self.db_manager.connection() as conn:
            stored_files = self.get_stored_files(conn, repository_id)

            seen_relative_paths = set()

            for item in walk_registered_roots([str(root)]):
                rel_path = item["relative_path"]

                if active_ignore.is_ignored(rel_path):
                    continue

                seen_relative_paths.add(rel_path)
                file_abs_path = root / rel_path

                try:
                    fingerprint = generate_fingerprint(
                        file_path=file_abs_path,
                        repo_id=repository_id,
                        relative_path=rel_path,
                    )
                except OSError:
                    continue

                lang = item.get("language_hint") or get_language_hint(rel_path)

                if rel_path not in stored_files:
                    # New file
                    plan.added.append(
                        PlannedFileAction(
                            action_type="add",
                            relative_path=rel_path,
                            file_id=fingerprint.file_id,
                            fingerprint=fingerprint,
                            language=lang,
                        )
                    )
                else:
                    stored = stored_files[rel_path]
                    prev_hash = str(stored["file_hash"])

                    if force_full_scan or fingerprint.file_hash.lower() != prev_hash.lower():
                        # File modified or re-scan forced
                        plan.changed.append(
                            PlannedFileAction(
                                action_type="update",
                                relative_path=rel_path,
                                file_id=fingerprint.file_id,
                                fingerprint=fingerprint,
                                language=lang,
                                previous_hash=prev_hash,
                            )
                        )
                    else:
                        # File unchanged
                        plan.unchanged.append(
                            PlannedFileAction(
                                action_type="skip",
                                relative_path=rel_path,
                                file_id=fingerprint.file_id,
                                fingerprint=fingerprint,
                                language=lang,
                                previous_hash=prev_hash,
                            )
                        )

            # Classify deleted files (stored in database but no longer on disk)
            for rel_path, stored in stored_files.items():
                if rel_path not in seen_relative_paths:
                    plan.deleted.append(
                        PlannedFileAction(
                            action_type="delete",
                            relative_path=rel_path,
                            file_id=str(stored["id"]),
                            previous_hash=str(stored["file_hash"]),
                        )
                    )

            if not dry_run:
                self.record_scan_start(conn, plan)

        return plan

    def record_scan_start(self, conn: sqlite3.Connection, plan: ScanPlan) -> None:
        """Record the initial scan_runs entry in the database."""
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO scan_runs (
                id, repository_id, status, started_at,
                files_seen, files_changed, files_skipped, files_deleted
            ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?);
            """,
            (
                plan.scan_run_id,
                plan.repository_id,
                now,
                plan.files_seen,
                plan.files_changed,
                plan.files_skipped,
                plan.files_deleted,
            ),
        )
        conn.commit()

    def finalize_scan_run(
        self,
        scan_run_id: str,
        status: str = "completed",
        symbols_indexed: int = 0,
        errors_count: int = 0,
        error_summary: Optional[str] = None,
    ) -> None:
        """Finalize a scan run with final status, timestamp, and symbol counters."""
        now = datetime.now(timezone.utc).isoformat()
        with self.db_manager.connection() as conn:
            conn.execute(
                """
                UPDATE scan_runs
                SET status = ?, finished_at = ?, symbols_indexed = ?, errors_count = ?, error_summary = ?
                WHERE id = ?;
                """,
                (status, now, symbols_indexed, errors_count, error_summary, scan_run_id),
            )
            conn.commit()

    def reconcile_deleted_files(self, repository_id: str, plan: ScanPlan) -> int:
        """Remove source files and associated symbols/vectors marked as deleted.

        Returns:
            Number of file rows deleted.
        """
        if not plan.deleted:
            return 0

        deleted_ids = [action.file_id for action in plan.deleted]
        with self.db_manager.connection() as conn:
            placeholders = ",".join("?" for _ in deleted_ids)
            cursor = conn.cursor()
            cursor.execute(
                f"""
                DELETE FROM source_files
                WHERE repository_id = ? AND id IN ({placeholders});
                """,
                [repository_id, *deleted_ids],
            )
            count = cursor.rowcount
            conn.commit()
            return count

