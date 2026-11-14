import os
from unittest.mock import patch, MagicMock
from brickforge.ingestion.discovery import walk_registered_roots
from brickforge.ingestion.ignore_rules import IgnoreRules

def test_document_discovery():
    # Create a mock directory structure
    with patch('os.walk') as mock_walk:
        mock_walk.return_value = [
            ('/root', ['dir1', 'dir2'], ['file1.md', 'file2.rst', 'file3.txt', 'file4.bin']),
            ('/root/dir1', [], ['file5.md']),
            ('/root/dir2', [], ['file6.rst']),
        ]

        # Create a mock IgnoreRules instance
        mock_ignore_rules = MagicMock(spec=IgnoreRules)
        mock_ignore_rules.is_dir_ignored.return_value = False
        mock_ignore_rules.is_ignored.return_value = False

        # Call the function
        results = list(walk_registered_roots(['/root'], ignore_rules=mock_ignore_rules))

        # Verify the results
        expected_results = [
            {'relative_path': 'file1.md', 'language_hint': 'markdown', 'file_size': 0, 'modification_time': '2023-10-01T00:00:00'},
            {'relative_path': 'file2.rst', 'language_hint': 'restructuredtext', 'file_size': 0, 'modification_time': '2023-10-01T00:00:00'},
            {'relative_path': 'file3.txt', 'language_hint': 'plaintext', 'file_size': 0, 'modification_time': '2023-10-01T00:00:00'},
            {'relative_path': 'dir1/file5.md', 'language_hint': 'markdown', 'file_size': 0, 'modification_time': '2023-10-01T00:00:00'},
            {'relative_path': 'dir2/file6.rst', 'language_hint': 'restructuredtext', 'file_size': 0, 'modification_time': '2023-10-01T00:00:00'},
        ]

        for result in results:
            result['modification_time'] = '2023-10-01T00:00:00'  # Mock modification time

        assert results == expected_results
