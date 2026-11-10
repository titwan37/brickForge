import unittest
from unittest.mock import patch, MagicMock
from src.brickforge.web.chat import BrickForgeChatEngine
from src.brickforge.search.project_retrieval import ProjectRetrievalService
from src.brickforge.storage.database import DatabaseManager
from src.brickforge.web.session_service import SessionService
from src.brickforge.storage.session_repository import SessionRepository

class TestSessionChatStream(unittest.TestCase):
    @patch.object(BrickForgeChatEngine, 'get_db_connection', return_value=MagicMock())
    @patch.object(ProjectRetrievalService, 'search', return_value=[])
    @patch.object(SessionService, 'reopen_session', return_value=None)
    def test_chat_stream_with_session_and_turn(self, mock_reopen_session, mock_search, mock_get_db_connection):
        db_path = "test.db"
        ollama_endpoint = "http://test-ollama"
        chat_engine = BrickForgeChatEngine(db_path, ollama_endpoint)

        messages = [{"role": "user", "content": "Hello"}]
        session_id = 1
        turn_id = 1

        with patch.object(httpx.Client, 'stream', return_value=MagicMock()) as mock_stream:
            mock_stream.return_value.__enter__.return_value.iter_lines.return_value = [
                b'{"message": {"content": "Hello!"}}',
                b'{"done": true}'
            ]

            stream = chat_engine.chat_stream(messages, session_id=session_id, turn_id=turn_id)
            result = list(stream)

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0], {"type": "token", "content": "Hello!"})
            self.assertIn("citations", result[1])
            self.assertIn("perf", result[1])
            self.assertIn("bricks", result[1])
            self.assertIn("model_used", result[1])
            self.assertIn("online", result[1])

            mock_reopen_session.assert_called_once_with(session_id)

    @patch.object(BrickForgeChatEngine, 'get_db_connection', return_value=MagicMock())
    @patch.object(ProjectRetrievalService, 'search', return_value=[])
    def test_chat_stream_fallback(self, mock_search, mock_get_db_connection):
        db_path = "test.db"
        ollama_endpoint = "http://test-ollama"
        chat_engine = BrickForgeChatEngine(db_path, ollama_endpoint)

        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(httpx.Client, 'stream', side_effect=httpx.RequestError("Failed to connect")):
            stream = chat_engine.chat_stream(messages)
            result = list(stream)

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["type"], "token")
            self.assertEqual(result[1]["type"], "done")
            self.assertIn("citations", result[1])
            self.assertIn("perf", result[1])
            self.assertIn("bricks", result[1])
            self.assertIn("model_used", result[1])
            self.assertIn("online", result[1])
            self.assertFalse(result[1]["online"])

if __name__ == '__main__':
    unittest.main()
