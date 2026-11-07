import os
import unittest
from unittest.mock import patch
from src.brickforge.ingestion.discovery import walk_registered_roots

class TestDiscovery(unittest.TestCase):
    @patch('os.walk', return_value=[('root', ['subdir'], ['root/subdir/file1.py', 'root/subdir/file2.txt']), ('subdir', [], [])])
    @patch('os.path.getsize', side_effect=[1024, 512])
    @patch('os.path.getmtime', side_effect=[1696275200, 1696275200])
    def test_walk_registered_roots(self, mock_getmtime, mock_getsize, mock_os_walk):
        roots = ['root']
        expected_output = [
            {'relative_path': 'subdir/file1.py', 'language_hint': 'python', 'file_size': 1024, 'modification_time': '2023-10-01T12:00:00'},
            {'relative_path': 'subdir/file2.txt', 'language_hint': 'unknown', 'file_size': 512, 'modification_time': '2023-10-01T12:00:00'}
        ]
        result = list(walk_registered_roots(roots))
        self.assertEqual(result, expected_output)

if __name__ == '__main__':
    unittest.main()
