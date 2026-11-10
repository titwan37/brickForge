from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.brickforge.web.session_models import Session, SessionSource, Snapshot, Event, RetentionState

class SessionRepository:
    def __init__(self, db_path: Path = Path("data/brickforge.db")):
        self.db_path = db_path

    @contextmanager
    def connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def create_session(self, session: Session) -> int:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (user_id, created_at, updated_at, provider, model, retrieval_settings, retention_state)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id;
                """,
                (
                    session.user_id,
                    session.created_at,
                    session.updated_at,
                    session.provider.value,
                    session.model,
                    session.retrieval_settings,
                    session.retention_state.value,
                ),
            )
            session_id = cursor.fetchone()[0]
            for source in session.sources:
                cursor.execute(
                    """
                    INSERT INTO session_sources (session_id, kind, uri, fingerprint)
                    VALUES (?, ?, ?, ?);
                    """,
                    (session_id, source.kind.value, source.uri, source.fingerprint),
                )
            for snapshot in session.snapshots:
                cursor.execute(
                    """
                    INSERT INTO snapshots (session_id, created_at, data)
                    VALUES (?, ?, ?);
                    """,
                    (session_id, snapshot.created_at, snapshot.data),
                )
            for event in session.events:
                cursor.execute(
                    """
                    INSERT INTO events (session_id, timestamp, type, details)
                    VALUES (?, ?, ?, ?);
                    """,
                    (session_id, event.timestamp, event.type, event.details),
                )
            conn.commit()
            return session_id

    def list_sessions(self, user_id: int, retention_state: Optional[RetentionState] = None) -> List[Session]:
        with self.connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, user_id, created_at, updated_at, provider, model, retrieval_settings, retention_state
                FROM sessions
                WHERE user_id = ?
            """
            params = [user_id]
            if retention_state:
                query += " AND retention_state = ?"
                params.append(retention_state.value)
            cursor.execute(query, params)
            sessions = []
            for row in cursor.fetchall():
                session = Session(
                    id=row[0],
                    user_id=row[1],
                    created_at=row[2],
                    updated_at=row[3],
                    provider=ProviderKind(row[4]),
                    model=row[5],
                    retrieval_settings=row[6],
                    retention_state=RetentionState(row[7]),
                )
                cursor.execute(
                    """
                    SELECT id, kind, uri, fingerprint
                    FROM session_sources
                    WHERE session_id = ?
                    """,
                    (session.id,),
                )
                session.sources = [
                    SessionSource(
                        id=row[0],
                        kind=SourceKind(row[1]),
                        uri=row[2],
                        fingerprint=row[3],
                    )
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT id, created_at, data
                    FROM snapshots
                    WHERE session_id = ?
                    """,
                    (session.id,),
                )
                session.snapshots = [
                    Snapshot(
                        id=row[0],
                        session_id=session.id,
                        created_at=row[1],
                        data=row[2],
                    )
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT id, timestamp, type, details
                    FROM events
                    WHERE session_id = ?
                    """,
                    (session.id,),
                )
                session.events = [
                    Event(
                        id=row[0],
                        session_id=session.id,
                        timestamp=row[1],
                        type=row[2],
                        details=row[3],
                    )
                    for row in cursor.fetchall()
                ]
                sessions.append(session)
            return sessions

    def reopen_session(self, session_id: int) -> Optional[Session]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, created_at, updated_at, provider, model, retrieval_settings, retention_state
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            session = Session(
                id=row[0],
                user_id=row[1],
                created_at=row[2],
                updated_at=row[3],
                provider=ProviderKind(row[4]),
                model=row[5],
                retrieval_settings=row[6],
                retention_state=RetentionState(row[7]),
            )
            cursor.execute(
                """
                SELECT id, kind, uri, fingerprint
                FROM session_sources
                WHERE session_id = ?
                """,
                (session.id,),
            )
            session.sources = [
                SessionSource(
                    id=row[0],
                    kind=SourceKind(row[1]),
                    uri=row[2],
                    fingerprint=row[3],
                )
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT id, created_at, data
                FROM snapshots
                WHERE session_id = ?
                """,
                (session.id,),
            )
            session.snapshots = [
                Snapshot(
                    id=row[0],
                    session_id=session.id,
                    created_at=row[1],
                    data=row[2],
                )
                for row in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT id, timestamp, type, details
                FROM events
                WHERE session_id = ?
                """,
                (session.id,),
            )
            session.events = [
                Event(
                    id=row[0],
                    session_id=session.id,
                    timestamp=row[1],
                    type=row[2],
                    details=row[3],
                )
                for row in cursor.fetchall()
            ]
            return session

    def archive_session(self, session_id: int) -> None:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET retention_state = ?
                WHERE id = ?
                """,
                (RetentionState.ARCHIVED.value, session_id),
            )
            conn.commit()

    def export_session(self, session_id: int) -> Optional[dict]:
        session = self.reopen_session(session_id)
        if not session:
            return None
        return session.model_dump()

    def restore_session(self, session_data: dict) -> int:
        session = Session(**session_data)
        return self.create_session(session)
