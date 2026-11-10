from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    assistant_id = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ChatRepository:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_message(self, user_id: int, assistant_id: int, message: str):
        session = self.Session()
        try:
            new_message = ChatMessage(user_id=user_id, assistant_id=assistant_id, message=message)
            session.add(new_message)
            session.commit()
        finally:
            session.close()

    def get_messages(self, user_id: int) -> List[Dict[str, any]]:
        session = self.Session()
        try:
            messages = session.query(ChatMessage).filter_by(user_id=user_id).order_by(ChatMessage.timestamp).all()
            return [{'id': msg.id, 'user_id': msg.user_id, 'assistant_id': msg.assistant_id, 'message': msg.message, 'timestamp': msg.timestamp} for msg in messages]
        finally:
            session.close()
