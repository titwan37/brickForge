from __future__ import annotations

import pytest
from src.brickforge.storage.chat_repository import ChatRepository
from src.brickforge.web.chat_history import ChatHistoryService

@pytest.fixture
def chat_repo():
    repo = ChatRepository('sqlite:///:memory:')
    yield repo
    repo.engine.dispose()

@pytest.fixture
def chat_service(chat_repo):
    return ChatHistoryService(chat_repo)

def test_add_and_get_message(chat_service):
    chat_service.add_message(1, 2, "Hello, how are you?")
    chat_service.add_message(1, 2, "I'm good, thanks!")
    history = chat_service.get_chat_history(1)
    assert len(history) == 2
    assert history[0]['message'] == "Hello, how are you?"
    assert history[1]['message'] == "I'm good, thanks!"
