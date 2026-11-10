from __future__ import annotations

from src.brickforge.storage.session_repository import SessionRepository
from src.brickforge.web.session_models import Session, RetentionState

class SessionService:
    def __init__(self, repo: SessionRepository):
        self.repo = repo

    def create_session(self, session: Session) -> int:
        return self.repo.create_session(session)

    def list_sessions(self, user_id: int, retention_state: Optional[RetentionState] = None) -> list[Session]:
        return self.repo.list_sessions(user_id, retention_state)

    def reopen_session(self, session_id: int) -> Optional[Session]:
        return self.repo.reopen_session(session_id)

    def archive_session(self, session_id: int) -> None:
        self.repo.archive_session(session_id)

    def export_session(self, session_id: int) -> Optional[dict]:
        return self.repo.export_session(session_id)

    def restore_session(self, session_data: dict) -> int:
        return self.repo.restore_session(session_data)
