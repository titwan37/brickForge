import unittest
from unittest.mock import patch
from brickforge.web.chat import BrickForgeChatEngine

class TestPrivateKnowledgeChat(unittest.TestCase):
    @patch.object(BrickForgeChatEngine, '__init__', return_value=None)
    def test_chat_with_local_model(self, mock_init):
        chat_engine = BrickForgeChatEngine("data/brickforge.db")
        response = chat_engine.chat([{"role": "user", "content": "Hello"}])
        self.assertIn("reply" in response, True)
        self.assertIn("bricks" in response, True)
        self.assertIn("model_used" in response, True)
        self.assertIn("online" in response, True)
        self.assertIn("perf" in response, True)

if __name__ == '__main__':
    unittest.main()
