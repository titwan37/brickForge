from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List, Optional

from src.brickforge.web.session_service import SessionService
from src.brickforge.web.session_models import Session, RetentionState, SessionCreate, SessionExport
from src.brickforge.storage.session_repository import SessionRepository
from src.brickforge.search.project_retrieval import ProjectRetrievalService
from src.brickforge.storage.database import DatabaseManager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Dependency to get the session service
def get_session_service() -> SessionService:
    repo = SessionRepository(DatabaseManager())
    return SessionService(repo)

# Dependency to get the project retrieval service
def get_project_retrieval_service() -> ProjectRetrievalService:
    db = DatabaseManager()
    return ProjectRetrievalService(db)

@router.post("/", response_model=int)
def create_session(session: SessionCreate, session_service: SessionService = Depends(get_session_service)) -> int:
    return session_service.create_session(Session(**session.dict()))

@router.get("/", response_model=List[Session])
def list_sessions(
    user_id: int = Query(..., description="ID of the user whose sessions are to be listed"),
    retention_state: Optional[RetentionState] = Query(None, description="Filter sessions by retention state"),
    session_service: SessionService = Depends(get_session_service)
) -> List[Session]:
    return session_service.list_sessions(user_id, retention_state)

@router.post("/{session_id}/reopen", response_model=Session)
def reopen_session(session_id: int = Path(..., description="ID of the session to reopen"), session_service: SessionService = Depends(get_session_service)) -> Session:
    session = session_service.reopen_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/archive")
def archive_session(session_id: int = Path(..., description="ID of the session to archive"), session_service: SessionService = Depends(get_session_service)) -> None:
    session_service.archive_session(session_id)

@router.get("/{session_id}/export", response_model=SessionExport)
def export_session(session_id: int = Path(..., description="ID of the session to export"), session_service: SessionService = Depends(get_session_service)) -> SessionExport:
    session_data = session_service.export_session(session_id)
    if session_data is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data

@router.post("/restore", response_model=int)
def restore_session(session_data: SessionExport, session_service: SessionService = Depends(get_session_service)) -> int:
    return session_service.restore_session(session_data.dict())

@router.get("/evidence", response_model=List[ProjectEvidence])
def retrieve_evidence(
    query: str = Query(..., description="Search query for evidence"),
    user_id: int = Query(..., description="ID of the user whose sessions are to be listed"),
    project_retrieval_service: ProjectRetrievalService = Depends(get_project_retrieval_service)
) -> List[ProjectEvidence]:
    query_params = CatalogQuery(query=query)
    return project_retrieval_service.search(query_params)

@router.get("/chat_history", response_model=List[Dict[str, str]])
def read_chat_history(
    session_id: int = Path(..., description="ID of the session to retrieve chat history"),
    session_service: SessionService = Depends(get_session_service)
) -> List[Dict[str, str]]:
    session = session_service.export_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.get("chat_history", [])
