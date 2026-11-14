from __future__ import annotations

from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pydantic import BaseModel
from typing import List, Optional, Dict
from brickforge.web.app import create_app
from brickforge.web.session_service import SessionService
from brickforge.web.session_models import Session, RetentionState, SessionCreate, SessionExport
from brickforge.search.project_retrieval import ProjectRetrievalService
from brickforge.search.document_search import DocumentSearchService
from brickforge.search.service import CatalogSearchHit, CatalogQuery, CatalogSearchService
from brickforge.storage.database import DatabaseManager

class MockSessionService(SessionService):
    def __init__(self):
        self.sessions = {}

    def create_session(self, session: Session) -> int:
        session_id = len(self.sessions) + 1
        self.sessions[session_id] = session
        return session_id

    def list_sessions(self, user_id: int, retention_state: Optional[RetentionState] = None) -> list[Session]:
        return [session for session in self.sessions.values() if session.user_id == user_id]

    def reopen_session(self, session_id: int) -> Optional[Session]:
        return self.sessions.get(session_id)

    def archive_session(self, session_id: int) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]

    def export_session(self, session_id: int) -> Optional[dict]:
        return self.sessions.get(session_id).dict()

    def restore_session(self, session_data: dict) -> int:
        session_id = len(self.sessions) + 1
        self.sessions[session_id] = Session(**session_data)
        return session_id

class MockProjectRetrievalService(ProjectRetrievalService):
    def __init__(self):
        self.evidence = []

    def search(self, query_params: CatalogQuery) -> List[ProjectEvidence]:
        return self.evidence

class MockCatalogSearchService(CatalogSearchService):
    def __init__(self, db: DatabaseManager):
        super().__init__(db)

    def search(self, query_params: CatalogQuery) -> List[CatalogSearchHit]:
        return []

class MockDocumentSearchService(DocumentSearchService):
    def __init__(self, db: DatabaseManager):
        super().__init__(db)

    def search(self, query: str) -> List[CatalogSearchHit]:
        return []

class ProjectEvidence(BaseModel):
    source_type: str
    repository_id: str
    path: str
    line_range: str
    excerpt: str
    stable_citation_id: str

class CatalogQuery(BaseModel):
    query: Optional[str] = None

app = create_app()
client = TestClient(app)

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_create_session(mock_project_retrieval_service, mock_session_service):
    response = client.post("/brickforge/api/sessions/", json={"user_id": 1, "name": "Test Session", "chat_history": []})
    assert response.status_code == 200
    assert response.json() == 1

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_list_sessions(mock_project_retrieval_service, mock_session_service):
    response = client.get("/brickforge/api/sessions/?user_id=1")
    assert response.status_code == 200
    assert response.json() == []

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_reopen_session(mock_project_retrieval_service, mock_session_service):
    response = client.post("/brickforge/api/sessions/1/reopen")
    assert response.status_code == 404

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_archive_session(mock_project_retrieval_service, mock_session_service):
    response = client.post("/brickforge/api/sessions/1/archive")
    assert response.status_code == 200

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_export_session(mock_project_retrieval_service, mock_session_service):
    response = client.get("/brickforge/api/sessions/1/export")
    assert response.status_code == 404

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_restore_session(mock_project_retrieval_service, mock_session_service):
    response = client.post("/brickforge/api/sessions/restore", json={"user_id": 1, "name": "Restored Session", "chat_history": []})
    assert response.status_code == 200
    assert response.json() == 1

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_retrieve_evidence(mock_project_retrieval_service, mock_session_service):
    response = client.get("/brickforge/api/sessions/evidence/?query=test&user_id=1")
    assert response.status_code == 200
    assert response.json() == []

@patch('src.brickforge.web.session_routes.get_session_service', return_value=MockSessionService())
@patch('src.brickforge.web.session_routes.get_project_retrieval_service', return_value=MockProjectRetrievalService())
def test_read_chat_history(mock_project_retrieval_service, mock_session_service):
    response = client.get("/brickforge/api/sessions/chat_history/1")
    assert response.status_code == 404
