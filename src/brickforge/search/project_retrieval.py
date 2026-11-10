from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from brickforge.search.fts import sanitize_fts_query
from brickforge.storage.database import DatabaseManager
from src.brickforge.search.document_search import DocumentSearchService
from src.brickforge.search.service import CatalogSearchHit, CatalogQuery, CatalogSearchService


@dataclass
class ProjectEvidence:
    """Unified evidence metadata representing a discovered brick or documentation chunk."""

    source_type: str
    repository_id: str
    path: str
    line_range: str
    excerpt: str
    stable_citation_id: str


class ProjectRetrievalService:
    """Orchestrates unified search over AST bricks and documentation chunks within a project scope."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.catalog_search_service = CatalogSearchService(db)
        self.document_search_service = DocumentSearchService(db)

    def search(self, query_params: CatalogQuery) -> List[ProjectEvidence]:
        """Execute unified search combining catalog and document searches."""
        catalog_results = self.catalog_search_service.search(query_params)
        document_results = self.document_search_service.search(query_params.query or "")

        evidence: List[ProjectEvidence] = []

        for result in catalog_results:
            evidence.append(
                ProjectEvidence(
                    source_type="brick",
                    repository_id=result.repository_id,
                    path=result.relative_path,
                    line_range="N/A",  # Assuming line range is not available for bricks
                    excerpt=result.signature,
                    stable_citation_id=result.brick_id,
                )
            )

        for result in document_results:
            evidence.append(
                ProjectEvidence(
                    source_type="document",
                    repository_id=result.document_source_id,
                    path="N/A",  # Assuming path is not available for document chunks
                    line_range=result.line_ranges,
                    excerpt=result.content_hash,
                    stable_citation_id=result.id,
                )
            )

        return evidence
