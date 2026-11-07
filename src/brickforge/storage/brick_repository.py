"""Persistence repository for source files, code bricks, and their dependency edges."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from brickforge.analysis.dependencies import ExtractedDependency
from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.database import DatabaseManager


class BrickRepository:
    """Manages CRUD persistence for source files, code bricks, dependencies, and packages."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.db = db

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    # -------------------------------------------------------------------------
    # Source Files
    # -------------------------------------------------------------------------

    def upsert_source_file(
        self,
        repository_id: str,
        relative_path: str,
        file_hash: str,
        language: str,
        byte_size: int = 0,
        loc: int = 0,
        modified_ns: Optional[int] = None,
        parser_name: Optional[str] = None,
        parser_version: Optional[str] = None,
        parse_status: str = "ok",
        parse_diagnostics: Optional[str] = None,
        file_id: Optional[str] = None,
    ) -> int:
        """Insert or update a source file record. Returns the database row_id."""
        norm_path = relative_path.replace("\\", "/").strip().lstrip("/")
        if not file_id:
            file_id = f"{repository_id}:{norm_path}"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO source_files (
                    id, repository_id, relative_path, language, file_hash,
                    byte_size, loc, modified_ns, parser_name, parser_version,
                    parse_status, parse_diagnostics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repository_id, relative_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    language = excluded.language,
                    byte_size = excluded.byte_size,
                    loc = excluded.loc,
                    modified_ns = excluded.modified_ns,
                    parser_name = excluded.parser_name,
                    parser_version = excluded.parser_version,
                    parse_status = excluded.parse_status,
                    parse_diagnostics = excluded.parse_diagnostics,
                    indexed_at = CURRENT_TIMESTAMP
                RETURNING row_id;
                """,
                (
                    file_id,
                    repository_id,
                    norm_path,
                    language,
                    file_hash,
                    byte_size,
                    loc,
                    modified_ns,
                    parser_name,
                    parser_version,
                    parse_status,
                    parse_diagnostics,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0])
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def get_source_file_by_path(self, repository_id: str, relative_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve source file record by repository and relative path."""
        norm_path = relative_path.replace("\\", "/").strip().lstrip("/")
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM source_files
                WHERE repository_id = ? AND relative_path = ?;
                """,
                (repository_id, norm_path),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    # -------------------------------------------------------------------------
    # Code Bricks
    # -------------------------------------------------------------------------

    def upsert_brick(
        self,
        file_row_id: int,
        symbol: ExtractedSymbol,
        brick_id: Optional[str] = None,
        parent_row_id: Optional[int] = None,
        cyclomatic_complexity: int = 1,
        portability_score: float = 0.5,
        portability_factors: Optional[Dict[str, Any]] = None,
        ai_summary: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Insert or update a code brick extracted from a source file."""
        if not brick_id:
            # Deterministic brick identity: file_row_id:qualified_name:kind:signature_hash[:16]
            brick_id = f"{file_row_id}:{symbol.qualified_name}:{symbol.kind}:{symbol.signature_hash[:16]}"

        tags_json = json.dumps(tags or [])
        factors_json = json.dumps(portability_factors or {})

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO code_bricks (
                    id, file_id, parent_row_id, symbol_name, qualified_name,
                    kind, language, visibility, signature, signature_hash,
                    docstring, source_code, source_hash, start_byte, end_byte,
                    start_line, end_line, is_async, cyclomatic_complexity,
                    portability_score, portability_factors, ai_summary, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, qualified_name, kind, signature_hash) DO UPDATE SET
                    parent_row_id = excluded.parent_row_id,
                    symbol_name = excluded.symbol_name,
                    visibility = excluded.visibility,
                    signature = excluded.signature,
                    docstring = excluded.docstring,
                    source_code = excluded.source_code,
                    source_hash = excluded.source_hash,
                    start_byte = excluded.start_byte,
                    end_byte = excluded.end_byte,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    is_async = excluded.is_async,
                    cyclomatic_complexity = excluded.cyclomatic_complexity,
                    portability_score = excluded.portability_score,
                    portability_factors = excluded.portability_factors,
                    ai_summary = excluded.ai_summary,
                    tags = excluded.tags,
                    indexed_at = CURRENT_TIMESTAMP
                RETURNING row_id;
                """,
                (
                    brick_id,
                    file_row_id,
                    parent_row_id,
                    symbol.symbol_name,
                    symbol.qualified_name,
                    symbol.kind,
                    symbol.language,
                    symbol.visibility,
                    symbol.signature,
                    symbol.signature_hash,
                    symbol.docstring,
                    symbol.source_code,
                    symbol.source_hash,
                    symbol.start_byte,
                    symbol.end_byte,
                    symbol.start_line,
                    symbol.end_line,
                    1 if symbol.is_async else 0,
                    cyclomatic_complexity,
                    portability_score,
                    factors_json,
                    ai_summary,
                    tags_json,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0])
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def get_brick_by_id(self, brick_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a code brick by its unique text ID."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM code_bricks WHERE id = ?;", (brick_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def get_brick_by_row_id(self, row_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a code brick by internal row_id."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM code_bricks WHERE row_id = ?;", (row_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def list_bricks_for_file(self, file_row_id: int) -> List[Dict[str, Any]]:
        """List all bricks belonging to a source file."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM code_bricks WHERE file_id = ? ORDER BY start_line ASC;",
                (file_row_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    # -------------------------------------------------------------------------
    # Dependencies
    # -------------------------------------------------------------------------

    def insert_dependency(
        self,
        source_row_id: int,
        dependency_type: str,
        confidence: float = 0.5,
        resolution_status: str = "unresolved",
        target_row_id: Optional[int] = None,
        unresolved_symbol: Optional[str] = None,
    ) -> int:
        """Insert or replace a dependency edge between bricks."""
        # Enforce check constraint:
        # (target_row_id IS NOT NULL AND unresolved_symbol IS NULL AND resolution_status = 'resolved')
        # OR (target_row_id IS NULL AND unresolved_symbol IS NOT NULL AND resolution_status IN ('unresolved', 'external'))
        if target_row_id is not None:
            resolution_status = "resolved"
            unresolved_symbol = None
        else:
            if resolution_status not in ("unresolved", "external"):
                resolution_status = "unresolved"
            if not unresolved_symbol:
                unresolved_symbol = "unknown"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if target_row_id is not None:
                cursor.execute(
                    """
                    INSERT INTO brick_dependencies (
                        source_row_id, target_row_id, unresolved_symbol,
                        dependency_type, resolution_status, confidence
                    ) VALUES (?, ?, NULL, ?, 'resolved', ?)
                    ON CONFLICT(source_row_id, target_row_id, dependency_type) WHERE target_row_id IS NOT NULL DO UPDATE SET
                        confidence = excluded.confidence
                    RETURNING dependency_id;
                    """,
                    (source_row_id, target_row_id, dependency_type, confidence),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO brick_dependencies (
                        source_row_id, target_row_id, unresolved_symbol,
                        dependency_type, resolution_status, confidence
                    ) VALUES (?, NULL, ?, ?, ?, ?)
                    ON CONFLICT(source_row_id, unresolved_symbol, dependency_type) WHERE target_row_id IS NULL DO UPDATE SET
                        resolution_status = excluded.resolution_status,
                        confidence = excluded.confidence
                    RETURNING dependency_id;
                    """,
                    (
                        source_row_id,
                        unresolved_symbol,
                        dependency_type,
                        resolution_status,
                        confidence,
                    ),
                )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0])
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def list_dependencies_for_brick(self, source_row_id: int) -> List[Dict[str, Any]]:
        """List all dependencies originating from a code brick."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM brick_dependencies WHERE source_row_id = ? ORDER BY dependency_id ASC;",
                (source_row_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    # -------------------------------------------------------------------------
    # External Packages
    # -------------------------------------------------------------------------

    def insert_external_package(
        self,
        brick_row_id: int,
        ecosystem: str,
        package_name: str,
        import_statement: str = "",
        version_constraint: Optional[str] = None,
    ) -> int:
        """Record an external package dependency for a brick."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO external_packages (
                    brick_row_id, ecosystem, package_name, version_constraint, import_statement
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(brick_row_id, ecosystem, package_name, import_statement) DO UPDATE SET
                    version_constraint = excluded.version_constraint
                RETURNING package_id;
                """,
                (brick_row_id, ecosystem, package_name, version_constraint, import_statement),
            )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0])
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def list_external_packages_for_brick(self, brick_row_id: int) -> List[Dict[str, Any]]:
        """List all external packages referenced by a brick."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM external_packages WHERE brick_row_id = ? ORDER BY package_id ASC;",
                (brick_row_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()
