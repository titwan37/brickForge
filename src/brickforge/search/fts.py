"""SQLite FTS5 lexical and exact search engine for code bricks."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

from brickforge.storage.database import DatabaseManager


def sanitize_fts_query(query: str) -> str:
    """Sanitize user search queries for safe execution in SQLite FTS5.

    Escapes syntax characters (quotes, hyphens, parentheses, boolean operators)
    to prevent syntax errors while supporting multi-token matching.
    """
    cleaned = query.strip()
    if not cleaned:
        return '""'

    # Check if user wrapped query in exact quotes e.g. "AES-GCM"
    if cleaned.startswith('"') and cleaned.endswith('"') and len(cleaned) > 2:
        inner = cleaned[1:-1].replace('"', '""')
        return f'"{inner}"'

    # Extract alphanumeric words and hyphenated tokens
    tokens = re.findall(r"[\w]+(?:-[\w]+)*", cleaned)
    if not tokens:
        return '""'

    # Wrap each token in double quotes to avoid FTS5 column/operator syntax ambiguity
    safe_terms = [f'"{token}"' for token in tokens]
    return " ".join(safe_terms)


@dataclass(frozen=True)
class FtsSearchResult:
    """Result item returned from an FTS5 search query."""

    row_id: int
    brick_id: str
    symbol_name: str
    qualified_name: str
    kind: str
    language: str
    signature: str
    docstring: Optional[str]
    rank: float
    snippet: Optional[str] = None


class FtsSearchEngine:
    """Provides full-text lexical search and exact symbol lookups backed by SQLite FTS5."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.db = db

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[FtsSearchResult]:
        """Execute a ranked full-text lexical search across code bricks.

        Searches symbol_name, qualified_name, signature, docstring, ai_summary, and tags.
        """
        safe_query = sanitize_fts_query(query)
        if not safe_query or safe_query == '""':
            return []

        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Order by bm25 score (smaller is better match in sqlite FTS5 bm25, or rank)
            cursor.execute(
                """
                SELECT
                    cb.row_id,
                    cb.id as brick_id,
                    cb.symbol_name,
                    cb.qualified_name,
                    cb.kind,
                    cb.language,
                    cb.signature,
                    cb.docstring,
                    fts.rank as score,
                    snippet(bricks_fts, 3, '<b>', '</b>', '...', 10) as match_snippet
                FROM bricks_fts fts
                JOIN code_bricks cb ON cb.row_id = fts.rowid
                WHERE bricks_fts MATCH ?
                ORDER BY fts.rank ASC
                LIMIT ? OFFSET ?;
                """,
                (safe_query, limit, offset),
            )
            rows = cursor.fetchall()
            return [
                FtsSearchResult(
                    row_id=row["row_id"],
                    brick_id=row["brick_id"],
                    symbol_name=row["symbol_name"],
                    qualified_name=row["qualified_name"],
                    kind=row["kind"],
                    language=row["language"],
                    signature=row["signature"],
                    docstring=row["docstring"],
                    rank=float(row["score"]),
                    snippet=row["match_snippet"],
                )
                for row in rows
            ]
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def search_exact_symbol(
        self,
        symbol_name: str,
        kind: Optional[str] = None,
        limit: int = 20,
    ) -> List[FtsSearchResult]:
        """Perform exact symbol name match."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if kind:
                cursor.execute(
                    """
                    SELECT
                        row_id, id as brick_id, symbol_name, qualified_name,
                        kind, language, signature, docstring
                    FROM code_bricks
                    WHERE symbol_name = ? AND kind = ?
                    ORDER BY row_id ASC LIMIT ?;
                    """,
                    (symbol_name, kind, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        row_id, id as brick_id, symbol_name, qualified_name,
                        kind, language, signature, docstring
                    FROM code_bricks
                    WHERE symbol_name = ?
                    ORDER BY row_id ASC LIMIT ?;
                    """,
                    (symbol_name, limit),
                )
            rows = cursor.fetchall()
            return [
                FtsSearchResult(
                    row_id=row["row_id"],
                    brick_id=row["brick_id"],
                    symbol_name=row["symbol_name"],
                    qualified_name=row["qualified_name"],
                    kind=row["kind"],
                    language=row["language"],
                    signature=row["signature"],
                    docstring=row["docstring"],
                    rank=0.0,
                )
                for row in rows
            ]
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def rebuild_index(self) -> None:
        """Force a full rebuild and sync of the FTS5 index from code_bricks table."""
        conn = self._get_connection()
        try:
            conn.execute("INSERT INTO bricks_fts(bricks_fts) VALUES('rebuild');")
            conn.commit()
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def optimize_index(self) -> None:
        """Merge FTS5 b-tree segments for optimal search latency."""
        conn = self._get_connection()
        try:
            conn.execute("INSERT INTO bricks_fts(bricks_fts) VALUES('optimize');")
            conn.commit()
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

