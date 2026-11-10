from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

class SourceKind(str, Enum):
    DOCUMENT = "document"
    CHUNK = "chunk"

class Citation(BaseModel):
    source_id: str
    page_number: Optional[int] = None
    line_number: Optional[int] = None

class DocumentSource(BaseModel):
    id: str
    project_id: str
    path: str
    heading_hierarchy: Optional[str] = None
    line_ranges: Optional[str] = None
    content_hash: str
    citations: Optional[list[Citation]] = None

class DocumentChunk(BaseModel):
    id: str
    document_source_id: str
    heading: Optional[str] = None
    line_ranges: Optional[str] = None
    content_hash: str
    citations: Optional[list[Citation]] = None

    @model_validator(mode='before')
    def ensure_citations(cls, values):
        if 'citations' in values and not all(isinstance(c, Citation) for c in values['citations']):
            raise ValueError("All citations must be instances of Citation")
        return values
