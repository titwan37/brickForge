from pydantic import BaseModel, Field, field_validator
from enum import Enum, auto
from datetime import datetime
from typing import List, Optional

class SourceKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class ProviderKind(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"

class RetentionState(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class SessionSource(BaseModel):
    id: int = Field(default_factory=int, alias="source_id")
    kind: SourceKind
    uri: str
    fingerprint: Optional[str] = None

    @field_validator('fingerprint')
    @classmethod
    def validate_fingerprint(cls, v):
        if v and not isinstance(v, str):
            raise ValueError('Fingerprint must be a string')
        return v

class Snapshot(BaseModel):
    id: int = Field(default_factory=int, alias="snapshot_id")
    session_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data: dict

class Event(BaseModel):
    id: int = Field(default_factory=int, alias="event_id")
    session_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    type: str
    details: dict

class Session(BaseModel):
    id: int = Field(default_factory=int, alias="session_id")
    user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sources: List[SessionSource] = []
    snapshots: List[Snapshot] = []
    events: List[Event] = []
    provider: ProviderKind
    model: str
    retrieval_settings: dict
    retention_state: RetentionState = RetentionState.ACTIVE

    @field_validator('retrieval_settings')
    @classmethod
    def validate_retrieval_settings(cls, v):
        if not isinstance(v, dict):
            raise ValueError('Retrieval settings must be a dictionary')
        return v
