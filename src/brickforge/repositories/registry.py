import os
import sqlite3
from pathlib import Path
from typing import Any, List, Optional, Tuple


class RepositoryRegistry:
    """Registry for managing registered repository scan roots."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS repository_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_path TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
                """
            )
            conn.commit()

    def register_repository(self, root_path: str | Path) -> int:
        """Register a new repository root path."""
        norm_path = str(root_path)
        if not os.path.isdir(norm_path):
            raise ValueError("Root path must be an existing directory")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO repository_registry (root_path) VALUES (?)
                    """,
                    (norm_path,),
                )
                conn.commit()
                return int(cursor.lastrowid)
            except sqlite3.IntegrityError as err:
                raise ValueError("Repository root already registered") from err

    def list_repositories(self) -> List[Tuple[int, str, int]]:
        """List all registered repositories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, root_path, is_active FROM repository_registry
                """
            )
            return cursor.fetchall()

    def lookup_repository(self, repo_id: int) -> Optional[Tuple[int, str, int]]:
        """Look up a repository by its identifier."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, root_path, is_active FROM repository_registry WHERE id = ?
                """,
                (repo_id,),
            )
            return cursor.fetchone()

    def update_repository(
        self,
        repo_id: int,
        root_path: Optional[str | Path] = None,
        is_active: Optional[bool] = None,
    ) -> None:
        """Update repository attributes."""
        updates: List[str] = []
        params: List[Any] = []
        if root_path is not None:
            updates.append("root_path = ?")
            params.append(str(root_path))
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if not updates:
            raise ValueError("No valid updates provided")

        params.append(repo_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE repository_registry SET {', '.join(updates)} WHERE id = ?
                """,
                params,
            )
            conn.commit()

    def deactivate_repository(self, repo_id: int) -> None:
        """Deactivate a repository by marking it inactive."""
        self.update_repository(repo_id, is_active=False)

