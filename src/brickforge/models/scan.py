from typing import List, Optional
from pydantic import BaseModel, Field


class ScanRun(BaseModel):
    """Domain model representing a repository scan execution."""

    id: str = Field(..., description="Unique identifier for the scan run")
    repository_id: str = Field(..., description="ID of the repository being scanned")
    start_time: str = Field(..., description="Start time of the scan")
    end_time: Optional[str] = Field(None, description="End time of the scan")
    status: str = Field(..., description="Status of the scan (e.g., 'completed', 'failed', 'running')")
    files_seen: int = Field(default=0, ge=0, description="Total files seen")
    files_changed: int = Field(default=0, ge=0, description="Files changed or parsed")
    files_skipped: int = Field(default=0, ge=0, description="Files skipped")
    files_deleted: int = Field(default=0, ge=0, description="Files deleted")
    symbols_indexed: int = Field(default=0, ge=0, description="Symbols indexed")
    errors_count: int = Field(default=0, ge=0, description="Number of errors")
    error_summary: Optional[str] = Field(None, description="Error summary")


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
    relative_path: Optional[str] = Field(None, description="Normalized relative path from root")
    language: Optional[str] = Field(None, description="Detected language")
    loc: int = Field(default=0, ge=0, description="Lines of code")
    parse_status: str = Field(default="pending", description="Parse status: pending, ok, partial, failed")


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

