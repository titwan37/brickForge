import unittest
from unittest.mock import patch
from src.brickforge.ingestion.ignore_rules import IgnoreRules

class TestIgnoreRules(unittest.TestCase):
    @patch.object(IgnoreRules, '__init__', return_value=None)
    def test_load_ignore_patterns(self, mock_init):
        mock_init.return_value = None
        ignore_rules = IgnoreRules('test_config.txt')
        ignore_rules.ignore_patterns = ['*.pyc', '__pycache__']
        self.assertEqual(ignore_rules.ignore_patterns, ['*.pyc', '__pycache__'])

    @patch.object(IgnoreRules, '__init__', return_value=None)
    def test_is_ignored(self, mock_init):
        mock_init.return_value = None
        ignore_rules = IgnoreRules('test_config.txt')
        ignore_rules.ignore_patterns = ['*.pyc', '__pycache__']
        self.assertTrue(ignore_rules.is_ignored('example.pyc'))
        self.assertTrue(ignore_rules.is_ignored('example/__pycache__/example.cpython-38.pyc'))
        self.assertFalse(ignore_rules.is_ignored('example.py'))

if __name__ == '__main__':
    unittest.main()
