import os
import sqlite3
from pathlib import Path

class RepositoryRegistry:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS repository_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_path TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    def register_repository(self, root_path):
        if not os.path.isdir(root_path):
            raise ValueError("Root path must be a directory")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO repository_registry (root_path) VALUES (?)
                ''', (root_path,))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError("Repository root already registered")
        finally:
            conn.close()

    def list_repositories(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, root_path, is_active FROM repository_registry
            ''')
            return cursor.fetchall()
        finally:
            conn.close()

    def lookup_repository(self, repo_id):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, root_path, is_active FROM repository_registry WHERE id = ?
            ''', (repo_id,))
            return cursor.fetchone()
        finally:
            conn.close()

    def update_repository(self, repo_id, root_path=None, is_active=None):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            updates = []
            params = []
            if root_path is not None:
                updates.append("root_path = ?")
                params.append(root_path)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)
            if not updates:
                raise ValueError("No valid updates provided")
            params.append(repo_id)
            cursor.execute(f'''
                UPDATE repository_registry SET {', '.join(updates)} WHERE id = ?
            ''', params)
            conn.commit()
        finally:
            conn.close()

    def deactivate_repository(self, repo_id):
        self.update_repository(repo_id, is_active=False)
