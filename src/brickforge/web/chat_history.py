from __future__ import annotations

from typing import List, Dict

from brickforge.storage.chat_repository import ChatRepository

class ChatHistoryService:
    def __init__(self, repo: ChatRepository):
        self.repo = repo

    def add_message(self, user_id: int, assistant_id: int, message: str):
        self.repo.add_message(user_id, assistant_id, message)

    def get_chat_history(self, user_id: int) -> List[Dict[str, any]]:
        return self.repo.get_messages(user_id)
