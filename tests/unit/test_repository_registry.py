import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from brickforge.repositories.registry import RepositoryRegistry


class TestRepositoryRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.registry = RepositoryRegistry(self.db_path)

    def tearDown(self):
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_db_creates_table(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='repository_registry'")
            result = cursor.fetchone()
            self.assertIsNotNone(result)

    def test_register_repository_success(self):
        test_dir = os.path.join(self.temp_dir, 'test_repo')
        os.makedirs(test_dir)
        repo_id = self.registry.register_repository(test_dir)
        self.assertIsInstance(repo_id, int)
        self.assertGreater(repo_id, 0)

    def test_register_repository_invalid_path(self):
        with self.assertRaises(ValueError):
            self.registry.register_repository('/non/existent/path')

    def test_register_repository_duplicate(self):
        test_dir = os.path.join(self.temp_dir, 'test_repo')
        os.makedirs(test_dir)
        self.registry.register_repository(test_dir)
        with self.assertRaises(ValueError):
            self.registry.register_repository(test_dir)

    def test_list_repositories_empty(self):
        result = self.registry.list_repositories()
        self.assertEqual(result, [])

    def test_list_repositories_with_data(self):
        test_dir1 = os.path.join(self.temp_dir, 'repo1')
        test_dir2 = os.path.join(self.temp_dir, 'repo2')
        os.makedirs(test_dir1)
        os.makedirs(test_dir2)
        
        id1 = self.registry.register_repository(test_dir1)
        id2 = self.registry.register_repository(test_dir2)
        
        result = self.registry.list_repositories()
        self.assertEqual(len(result), 2)
        
        repo1 = [r for r in result if r[0] == id1][0]
        repo2 = [r for r in result if r[0] == id2][0]
        
        self.assertEqual(repo1[1], test_dir1)
        self.assertEqual(repo1[2], 1)
        
        self.assertEqual(repo2[1], test_dir2)
        self.assertEqual(repo2[2], 1)

    def test_lookup_repository_success(self):
        test_dir = os.path.join(self.temp_dir, 'test_repo')
        os.makedirs(test_dir)
        repo_id = self.registry.register_repository(test_dir)
        
        result = self.registry.lookup_repository(repo_id)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], repo_id)
        self.assertEqual(result[1], test_dir)
        self.assertEqual(result[2], 1)

    def test_lookup_repository_not_found(self):
        result = self.registry.lookup_repository(99999)
        self.assertIsNone(result)

    def test_update_repository_root_path(self):
        test_dir1 = os.path.join(self.temp_dir, 'repo1')
        test_dir2 = os.path.join(self.temp_dir, 'repo2')
        os.makedirs(test_dir1)
        os.makedirs(test_dir2)
        
        repo_id = self.registry.register_repository(test_dir1)
        self.registry.update_repository(repo_id, root_path=test_dir2)
        
        result = self.registry.lookup_repository(repo_id)
        self.assertEqual(result[1], test_dir2)

    def test_update_repository_is_active(self):
        test_dir = os.path.join(self.temp_dir, 'test_repo')
        os.makedirs(test_dir)
        repo_id = self.registry.register_repository(test_dir)
        
        self.registry.update_repository(repo_id, is_active=False)
        
        result = self.registry.lookup_repository(repo_id)
        self.assertEqual(result[2], 0)

    def test_update_repository_no_updates(self):
        test_dir = os.path.join(self.temp_dir, 'test_repo')
        os.makedirs(test_dir)
        repo_id = self.registry.register_repository(test_dir)
        
        with self.assertRaises(ValueError):
            self.registry.update_repository(repo_id)

    def test_deactivate_repository(self):
        test_dir = os.path.join(self.temp_dir, 'test_repo')
        os.makedirs(test_dir)
        repo_id = self.registry.register_repository(test_dir)
        
        self.registry.deactivate_repository(repo_id)
        
        result = self.registry.lookup_repository(repo_id)
        self.assertEqual(result[2], 0)


if __name__ == '__main__':
    unittest.main()
