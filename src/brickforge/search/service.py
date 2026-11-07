"""Filtered catalog search API for finding reusable bricks across repositories."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from brickforge.search.fts import sanitize_fts_query
from brickforge.storage.database import DatabaseManager


@dataclass
class CatalogQuery:
    """Filter parameters for querying the brick catalog."""

    query: Optional[str] = None
    repository_id: Optional[str] = None
    language: Optional[str] = None
    kind: Optional[str] = None
    path_pattern: Optional[str] = None
    package_dependency: Optional[str] = None
    min_portability: Optional[float] = None
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class CatalogSearchHit:
    """Concise search hit metadata representing a discovered brick."""

    brick_id: str
    symbol_name: str
    qualified_name: str
    kind: str
    language: str
    signature: str
    docstring: Optional[str]
    relative_path: str
    repository_id: str
    portability_score: float
    tags: List[str] = field(default_factory=list)
    score: Optional[float] = None


class CatalogSearchService:
    """Orchestrates multi-attribute filtered catalog searches over code bricks."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.db = db

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    def search(self, query_params: CatalogQuery) -> List[CatalogSearchHit]:
        """Execute structured catalog search combining FTS5 lexical ranking and metadata filters."""
        where_clauses: List[str] = []
        params: List[Any] = []
        joins: List[str] = ["JOIN source_files sf ON sf.row_id = cb.file_id"]

        # 1. Lexical FTS5 filter
        if query_params.query and query_params.query.strip():
            safe_q = sanitize_fts_query(query_params.query)
            if safe_q and safe_q != '""':
                joins.append("JOIN bricks_fts fts ON fts.rowid = cb.row_id")
                where_clauses.append("bricks_fts MATCH ?")
                params.append(safe_q)

        # 2. Repository filter
        if query_params.repository_id:
            where_clauses.append("sf.repository_id = ?")
            params.append(query_params.repository_id)

        # 3. Language filter
        if query_params.language:
            where_clauses.append("cb.language = ?")
            params.append(query_params.language)

        # 4. Symbol kind filter
        if query_params.kind:
            where_clauses.append("cb.kind = ?")
            params.append(query_params.kind)

        # 5. Path pattern (LIKE matching)
        if query_params.path_pattern:
            where_clauses.append("sf.relative_path LIKE ?")
            params.append(query_params.path_pattern)

        # 6. Minimum portability score
        if query_params.min_portability is not None:
            where_clauses.append("cb.portability_score >= ?")
            params.append(query_params.min_portability)

        # 7. Package dependency filter
        if query_params.package_dependency:
            where_clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM external_packages ep
                    WHERE ep.brick_row_id = cb.row_id
                      AND ep.package_name LIKE ?
                )
                """
            )
            params.append(f"%{query_params.package_dependency}%")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        joins_sql = " ".join(joins)

        order_by = "fts.rank ASC" if "bricks_fts" in joins_sql else "cb.portability_score DESC, cb.row_id ASC"

        sql = f"""
            SELECT
                cb.id as brick_id,
                cb.symbol_name,
                cb.qualified_name,
                cb.kind,
                cb.language,
                cb.signature,
                cb.docstring,
                cb.portability_score,
                cb.tags,
                sf.relative_path,
                sf.repository_id
            FROM code_bricks cb
            {joins_sql}
            {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?;
        """
        params.extend([query_params.limit, query_params.offset])

        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            results: List[CatalogSearchHit] = []
            for row in rows:
                raw_tags = row["tags"]
                try:
                    tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags or [])
                except Exception:
                    tags = []

                results.append(
                    CatalogSearchHit(
                        brick_id=row["brick_id"],
                        symbol_name=row["symbol_name"],
                        qualified_name=row["qualified_name"],
                        kind=row["kind"],
                        language=row["language"],
                        signature=row["signature"],
                        docstring=row["docstring"],
                        relative_path=row["relative_path"],
                        repository_id=row["repository_id"],
                        portability_score=float(row["portability_score"]),
                        tags=tags,
                    )
                )
            return results
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

