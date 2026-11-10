from unittest.mock import patch
from pathlib import Path
from datetime import datetime

from src.brickforge.storage.session_repository import SessionRepository
from src.brickforge.web.session_service import SessionService
from src.brickforge.web.session_models import Session, SessionSource, Snapshot, Event, RetentionState, SourceKind, ProviderKind

def test_create_session():
    repo = SessionRepository(db_path=Path("data/test_brickforge.db"))
    service = SessionService(repo)
    session = Session(
        user_id=1,
        provider=ProviderKind.OPENAI,
        model="gpt-4",
        retrieval_settings={"key": "value"},
        sources=[SessionSource(kind=SourceKind.TEXT, uri="http://example.com")],
        snapshots=[Snapshot(created_at=datetime.utcnow(), data={"data": "value"})],
        events=[Event(timestamp=datetime.utcnow(), type="event_type", details={"detail": "value"})],
    )
    session_id = service.create_session(session)
    assert session_id > 0

def test_list_sessions():
    repo = SessionRepository(db_path=Path("data/test_brickforge.db"))
    service = SessionService(repo)
    sessions = service.list_sessions(user_id=1)
    assert isinstance(sessions, list)

def test_reopen_session():
    repo = SessionRepository(db_path=Path("data/test_brickforge.db"))
    service = SessionService(repo)
    session = Session(
        user_id=1,
        provider=ProviderKind.OPENAI,
        model="gpt-4",
        retrieval_settings={"key": "value"},
        sources=[SessionSource(kind=SourceKind.TEXT, uri="http://example.com")],
        snapshots=[Snapshot(created_at=datetime.utcnow(), data={"data": "value"})],
        events=[Event(timestamp=datetime.utcnow(), type="event_type", details={"detail": "value"})],
    )
    session_id = service.create_session(session)
    reopened_session = service.reopen_session(session_id)
    assert reopened_session.id == session_id

def test_archive_session():
    repo = SessionRepository(db_path=Path("data/test_brickforge.db"))
    service = SessionService(repo)
    session = Session(
        user_id=1,
        provider=ProviderKind.OPENAI,
        model="gpt-4",
        retrieval_settings={"key": "value"},
        sources=[SessionSource(kind=SourceKind.TEXT, uri="http://example.com")],
        snapshots=[Snapshot(created_at=datetime.utcnow(), data={"data": "value"})],
        events=[Event(timestamp=datetime.utcnow(), type="event_type", details={"detail": "value"})],
    )
    session_id = service.create_session(session)
    service.archive_session(session_id)
    archived_session = service.reopen_session(session_id)
    assert archived_session.retention_state == RetentionState.ARCHIVED

def test_export_session():
    repo = SessionRepository(db_path=Path("data/test_brickforge.db"))
    service = SessionService(repo)
    session = Session(
        user_id=1,
        provider=ProviderKind.OPENAI,
        model="gpt-4",
        retrieval_settings={"key": "value"},
        sources=[SessionSource(kind=SourceKind.TEXT, uri="http://example.com")],
        snapshots=[Snapshot(created_at=datetime.utcnow(), data={"data": "value"})],
        events=[Event(timestamp=datetime.utcnow(), type="event_type", details={"detail": "value"})],
    )
    session_id = service.create_session(session)
    exported_session = service.export_session(session_id)
    assert exported_session is not None

def test_restore_session():
    repo = SessionRepository(db_path=Path("data/test_brickforge.db"))
    service = SessionService(repo)
    session = Session(
        user_id=1,
        provider=ProviderKind.OPENAI,
        model="gpt-4",
        retrieval_settings={"key": "value"},
        sources=[SessionSource(kind=SourceKind.TEXT, uri="http://example.com")],
        snapshots=[Snapshot(created_at=datetime.utcnow(), data={"data": "value"})],
        events=[Event(timestamp=datetime.utcnow(), type="event_type", details={"detail": "value"})],
    )
    session_id = service.create_session(session)
    exported_session = service.export_session(session_id)
    restored_session_id = service.restore_session(exported_session)
    assert restored_session_id > 0
