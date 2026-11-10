from __future__ import annotations

import re
from typing import List, Tuple

from pydantic import BaseModel, Field

from src.brickforge.storage.document_models import DocumentChunk, DocumentSource

class DocumentChunker(BaseModel):
    max_chunk_size: int = Field(default=1000, description="Maximum size of a chunk in characters")
    overlap_size: int = Field(default=200, description="Overlap size between chunks in characters")

    def chunk_document(self, document_source: DocumentSource) -> List[DocumentChunk]:
        content = document_source.content
        headings = self._parse_headings(content)
        chunks = self._create_chunks(content, headings)
        return chunks

    def _parse_headings(self, content: str) -> List[Tuple[int, str]]:
        heading_pattern = re.compile(r'^(#+)\s+(.*)$', re.MULTILINE)
        headings = [(match.start(), match.group(2)) for match in heading_pattern.finditer(content)]
        return headings

    def _create_chunks(self, content: str, headings: List[Tuple[int, str]]) -> List[DocumentChunk]:
        chunks = []
        start = 0
        for i, (heading_start, heading) in enumerate(headings):
            if i + 1 < len(headings):
                end = headings[i + 1][0]
            else:
                end = len(content)
            chunk_content = content[start:end]
            if len(chunk_content) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk_content, start, heading)
                chunks.extend(sub_chunks)
            else:
                chunks.append(self._create_chunk(chunk_content, start, heading))
            start = end
        if start < len(content):
            chunks.append(self._create_chunk(content[start:], start, None))
        return chunks

    def _split_large_chunk(self, chunk_content: str, start: int, heading: str) -> List[DocumentChunk]:
        sub_chunks = []
        for i in range(0, len(chunk_content), self.max_chunk_size - self.overlap_size):
            sub_chunk_content = chunk_content[i:i + self.max_chunk_size]
            if i > 0:
                sub_chunk_content = chunk_content[i - self.overlap_size:i + self.max_chunk_size]
            sub_chunks.append(self._create_chunk(sub_chunk_content, start + i, heading))
        return sub_chunks

    def _create_chunk(self, content: str, start: int, heading: str) -> DocumentChunk:
        return DocumentChunk(
            id=f"{self.document_source.id}_{start}",
            document_source_id=self.document_source.id,
            heading=heading,
            line_ranges=self._calculate_line_ranges(content, start),
            content_hash=self._calculate_content_hash(content),
            citations=self.document_source.citations
        )

    def _calculate_line_ranges(self, content: str, start: int) -> str:
        lines = content.splitlines()
        start_line = content[:start].count('\n') + 1
        end_line = start_line + len(lines) - 1
        return f"{start_line}-{end_line}"

    def _calculate_content_hash(self, content: str) -> str:
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
