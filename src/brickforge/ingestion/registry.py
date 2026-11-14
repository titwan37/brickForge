from typing import List, Optional
from pydantic import BaseModel, Field, validator
from brickforge.ingestion.models import SourceRoot

class ProjectRegistry(BaseModel):
    id: str
    user_id: str
    project_name: str
    source_roots: List[SourceRoot]
    documentation_roots: List[str] = Field(default_factory=list)
    indexing_state: str = Field(default="not_indexed")
    content_fingerprint: Optional[str] = None

    @validator('project_name')
    def validate_project_name(cls, v):
        if not v:
            raise ValueError("Project name cannot be empty")
        return v

    @validator('source_roots', 'documentation_roots')
    def validate_roots(cls, v):
        if not v:
            raise ValueError("At least one root is required")
        return v
