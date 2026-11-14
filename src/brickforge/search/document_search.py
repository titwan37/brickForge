from __future__ import annotations

import sqlite3
from typing import List, Optional

from brickforge.storage.database import DatabaseManager
from brickforge.storage.document_models import DocumentChunk

class DocumentSearchService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _get_connection(self) -> sqlite3.Connection:
        return self.db_manager.create_connection()

    def search(self, query: str) -> List[DocumentChunk]:
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, document_source_id, heading, line_ranges, content_hash, citations FROM document_chunks_fts WHERE document_chunks_fts MATCH ?;",
                (query,),
            )
            rows = cursor.fetchall()

            results: List[DocumentChunk] = []
            for row in rows:
                results.append(
                    DocumentChunk(
                        id=row["id"],
                        document_source_id=row["document_source_id"],
                        heading=row["heading"],
                        line_ranges=row["line_ranges"],
                        content_hash=row["content_hash"],
                        citations=row["citations"],
                    )
                )
            return results
        finally:
            conn.close()

    def upsert_chunk(self, chunk: DocumentChunk) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO document_chunks (id, document_source_id, heading, line_ranges, content_hash, citations)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                document_source_id = excluded.document_source_id,
                heading = excluded.heading,
                line_ranges = excluded.line_ranges,
                content_hash = excluded.content_hash,
                citations = excluded.citations;
                """,
                (
                    chunk.id,
                    chunk.document_source_id,
                    chunk.heading,
                    chunk.line_ranges,
                    chunk.content_hash,
                    chunk.citations,
                ),
            )
            conn.execute(
                """
                INSERT INTO document_chunks_fts (id, document_source_id, heading, line_ranges, content_hash, citations)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                document_source_id = excluded.document_source_id,
                heading = excluded.heading,
                line_ranges = excluded.line_ranges,
                content_hash = excluded.content_hash,
                citations = excluded.citations;
                """,
                (
                    chunk.id,
                    chunk.document_source_id,
                    chunk.heading,
                    chunk.line_ranges,
                    chunk.content_hash,
                    chunk.citations,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_chunk(self, chunk_id: str) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                "DELETE FROM document_chunks WHERE id = ?;",
                (chunk_id,),
            )
            conn.execute(
                "DELETE FROM document_chunks_fts WHERE id = ?;",
                (chunk_id,),
            )
            conn.commit()
        finally:
            conn.close()
