import unittest
from unittest.mock import patch
from pathlib import Path
from src.brickforge.ingestion.paths import safe_path_canonicalization

class TestSafePathCanonicalization(unittest.TestCase):
    @patch('src.brickforge.ingestion.paths.Path.resolve', return_value=Path("/safe/root1/subdir/file.txt"))
    def test_safe_path_canonicalization(self, mock_resolve):
        allowed_roots = [Path("/safe/root1"), Path("/safe/root2")]
        result = safe_path_canonicalization("/unsafe/path", allowed_roots)
        self.assertEqual(result, Path("/safe/root1/subdir/file.txt"))

    @patch('src.brickforge.ingestion.paths.Path.resolve', return_value=Path("/unsafe/root1/subdir/file.txt"))
    def test_safe_path_canonicalization_unsafe_root(self, mock_resolve):
        allowed_roots = [Path("/safe/root1"), Path("/safe/root2")]
        with self.assertRaises(ValueError):
            safe_path_canonicalization("/unsafe/path", allowed_roots)

if __name__ == '__main__':
    unittest.main()
