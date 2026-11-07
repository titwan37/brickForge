from typing import List, Optional
from pydantic import BaseModel, Field

class ScanRun(BaseModel):
    id: str = Field(..., description="Unique identifier for the scan run")
    repository_id: str = Field(..., description="ID of the repository being scanned")
    start_time: str = Field(..., description="Start time of the scan")
    end_time: Optional[str] = Field(None, description="End time of the scan")
    status: str = Field(..., description="Status of the scan (e.g., 'completed', 'failed', 'running')")

class ScanStatus(BaseModel):
    id: str = Field(..., description="Unique identifier for the scan status")
    scan_id: str = Field(..., description="ID of the scan run")
    message: str = Field(..., description="Status message")
    timestamp: str = Field(..., description="Timestamp of the status update")

class SourceFileMetadata(BaseModel):
    id: str = Field(..., description="Unique identifier for the source file")
    scan_id: str = Field(..., description="ID of the scan run")
    file_path: str = Field(..., description="Path of the source file")
    file_hash: str = Field(..., description="Hash of the source file")
    file_size: int = Field(..., description="Size of the source file in bytes")

class Exclusion(BaseModel):
    id: str = Field(..., description="Unique identifier for the exclusion")
    repository_id: str = Field(..., description="ID of the repository")
    pattern: str = Field(..., description="Pattern to match files to exclude")

class ScanError(BaseModel):
    id: str = Field(..., description="Unique identifier for the scan error")
    scan_id: str = Field(..., description="ID of the scan run")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    timestamp: str = Field(..., description="Timestamp of the error")
