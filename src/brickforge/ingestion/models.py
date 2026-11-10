from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import List, Optional

class SourceKind(str, Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    TEXT = "text"

class SourceRoot(BaseModel):
    id: str
    root_path: str
    include_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)
    source_kind: SourceKind = Field(default=SourceKind.CODE)

    @field_validator('root_path')
    def validate_root_path(cls, v):
        if not v.startswith('/'):
            raise ValueError("Root path must be an absolute path")
        return v

    @field_validator('include_patterns', 'exclude_patterns')
    def validate_patterns(cls, v):
        for pattern in v:
            if not pattern.startswith('/'):
                raise ValueError("Patterns must be absolute paths")
        return v

class ProjectWorkspace(BaseModel):
    id: str
    name: str
    source_roots: List[SourceRoot]
    indexing_state: str = Field(default="not_indexed")
    content_fingerprint: Optional[str] = None

    @field_validator('name')
    def validate_name(cls, v):
        if not v:
            raise ValueError("Workspace name cannot be empty")
        return v

    @field_validator('source_roots')
    def validate_source_roots(cls, v):
        if not v:
            raise ValueError("At least one source root is required")
        return v
