from typing import List, Optional
from pydantic import BaseModel, Field


class Repository(BaseModel):
    """Domain model representing a registered repository or scan root."""

    id: str = Field(..., description="Unique identifier for the repository")
    name: str = Field(..., description="Name of the repository")
    url: Optional[str] = Field(None, description="URL or VCS remote of the repository")
    root_path: Optional[str] = Field(None, description="Canonical root directory path")
    source_kind: str = Field(default="directory", description="Source kind: directory, git_worktree, nas_share, archive")
    enabled: bool = Field(default=True, description="Whether the repository is enabled for scanning")
    include_globs: List[str] = Field(default_factory=list, description="Inclusion glob rules")
    exclude_globs: List[str] = Field(default_factory=list, description="Exclusion glob rules")
    follow_symlinks: bool = Field(default=False, description="Whether to follow symlinks")
    last_scan_id: Optional[str] = Field(None, description="ID of the last scan run")
    last_scan_at: Optional[str] = Field(None, description="Timestamp of the last scan")

