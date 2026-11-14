import unittest
from unittest.mock import MagicMock, patch
try:
    from brickforge.ingestion.discovery import get_language_hint, walk_registered_roots
except ImportError:
    from brickforge.ingestion.discovery import get_language_hint, walk_registered_roots


class TestDiscovery(unittest.TestCase):
    @patch('os.path.isfile', return_value=True)
    @patch('os.walk', return_value=[('root', ['subdir'], ['root/subdir/file1.py', 'root/subdir/file2.txt']), ('subdir', [], [])])
    @patch('os.path.getsize', side_effect=[1024, 512])
    @patch('os.path.getmtime', side_effect=[1696275200, 1696275200])
    @patch('brickforge.ingestion.discovery.datetime')
    def test_walk_registered_roots(self, mock_dt_cls, mock_getmtime, mock_getsize, mock_os_walk, mock_isfile):
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = '2023-10-01T12:00:00'
        mock_dt_cls.fromtimestamp.return_value = mock_dt

        roots = ['root']
        expected_output = [
            {'relative_path': 'subdir/file1.py', 'language_hint': 'python', 'file_size': 1024, 'modification_time': '2023-10-01T12:00:00'},
            {'relative_path': 'subdir/file2.txt', 'language_hint': 'unknown', 'file_size': 512, 'modification_time': '2023-10-01T12:00:00'}
        ]
        result = list(walk_registered_roots(roots))
        self.assertEqual(result, expected_output)

    def test_get_language_hint(self):
        self.assertEqual(get_language_hint("main.py"), "python")
        self.assertEqual(get_language_hint("index.ts"), "typescript")
        self.assertEqual(get_language_hint("lib.rs"), "rust")
        self.assertEqual(get_language_hint("unknown.xyz"), "unknown")


if __name__ == '__main__':
    unittest.main()

