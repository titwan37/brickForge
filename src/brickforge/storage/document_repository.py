from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.brickforge.storage.database import DatabaseManager
from src.brickforge.storage.document_models import DocumentSource, DocumentChunk

class DocumentRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def add_document_source(self, document_source: DocumentSource) -> None:
        with self.db_manager.connection() as conn:
            conn.execute(
                "INSERT INTO document_sources (id, project_id, path, heading_hierarchy, line_ranges, content_hash, citations) VALUES (?, ?, ?, ?, ?, ?, ?);",
                (
                    document_source.id,
                    document_source.project_id,
                    document_source.path,
                    document_source.heading_hierarchy,
                    document_source.line_ranges,
                    document_source.content_hash,
                    document_source.citations,
                ),
            )

    def add_document_chunk(self, document_chunk: DocumentChunk) -> None:
        with self.db_manager.connection() as conn:
            conn.execute(
                "INSERT INTO document_chunks (id, document_source_id, heading, line_ranges, content_hash, citations) VALUES (?, ?, ?, ?, ?, ?);",
                (
                    document_chunk.id,
                    document_chunk.document_source_id,
                    document_chunk.heading,
                    document_chunk.line_ranges,
                    document_chunk.content_hash,
                    document_chunk.citations,
                ),
            )

    def get_document_source(self, document_source_id: str) -> Optional[DocumentSource]:
        with self.db_manager.connection() as conn:
            cursor = conn.execute(
                "SELECT id, project_id, path, heading_hierarchy, line_ranges, content_hash, citations FROM document_sources WHERE id = ?;",
                (document_source_id,),
            )
            row = cursor.fetchone()
            if row:
                return DocumentSource(
                    id=row[0],
                    project_id=row[1],
                    path=row[2],
                    heading_hierarchy=row[3],
                    line_ranges=row[4],
                    content_hash=row[5],
                    citations=row[6],
                )
            return None

    def get_document_chunk(self, document_chunk_id: str) -> Optional[DocumentChunk]:
        with self.db_manager.connection() as conn:
            cursor = conn.execute(
                "SELECT id, document_source_id, heading, line_ranges, content_hash, citations FROM document_chunks WHERE id = ?;",
                (document_chunk_id,),
            )
            row = cursor.fetchone()
            if row:
                return DocumentChunk(
                    id=row[0],
                    document_source_id=row[1],
                    heading=row[2],
                    line_ranges=row[3],
                    content_hash=row[4],
                    citations=row[5],
                )
            return None
