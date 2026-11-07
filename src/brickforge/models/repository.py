from typing import List, Optional
from pydantic import BaseModel, Field

class Repository(BaseModel):
    id: str = Field(..., description="Unique identifier for the repository")
    name: str = Field(..., description="Name of the repository")
    url: str = Field(..., description="URL of the repository")
    last_scan_id: Optional[str] = Field(None, description="ID of the last scan run")
