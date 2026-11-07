"""SQLite connection and migration manager for BrickForge.

Provides transactional migration execution, foreign key enforcement, WAL mode configuration,
and safe schema version tracking.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_BUSY_TIMEOUT_MS = 5000
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class DatabaseManager:
    """Manages SQLite connections, pragma configuration, and migrations."""

    def __init__(
        self,
        db_path: Union[str, Path] = "data/brickforge.db",
        migrations_dir: Optional[Union[str, Path]] = None,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        wal_mode: bool = True,
    ):
        self.db_path = str(db_path)
        self.migrations_dir = Path(migrations_dir) if migrations_dir else MIGRATIONS_DIR
        self.busy_timeout_ms = busy_timeout_ms
        self.wal_mode = wal_mode

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def create_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection with required pragmas."""
        conn = sqlite3.connect(self.db_path, timeout=self.busy_timeout_ms / 1000.0)

        # Enforce foreign key constraints on every connection
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")

        # Enable WAL journal mode for persistent databases
        if self.wal_mode and self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")

        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding an open connection and safely closing it."""
        conn = self.create_connection()
        try:
            yield conn
        finally:
            conn.close()

    def init_migration_table(self, conn: sqlite3.Connection) -> None:
        """Ensure the schema_migrations tracking table exists."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    def get_applied_migrations(self, conn: sqlite3.Connection) -> List[str]:
        """Return a sorted list of applied migration versions."""
        self.init_migration_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
        return [row[0] for row in cursor.fetchall()]

    def get_available_migrations(self) -> List[Tuple[str, str, Path]]:
        """Discover available migration files sorted by version."""
        if not self.migrations_dir.exists():
            return []

        migrations: List[Tuple[str, str, Path]] = []
        for file in sorted(self.migrations_dir.glob("*.sql")):
            # Match pattern: 0001_name.sql
            match = re.match(r"^(\d+)[-_](.*)\.sql$", file.name)
            if match:
                version = match.group(1)
                name = match.group(2)
            else:
                version = file.stem
                name = file.stem

            migrations.append((version, name, file))

        migrations.sort(key=lambda m: m[0])
        return migrations

    def get_pending_migrations(self, conn: sqlite3.Connection) -> List[Tuple[str, str, Path]]:
        """Return migrations that have not yet been applied."""
        applied = set(self.get_applied_migrations(conn))
        available = self.get_available_migrations()
        return [m for m in available if m[0] not in applied]

    def apply_migrations(self) -> List[str]:
        """Apply all pending migrations in order inside individual transactions.

        Returns:
            List of newly applied migration versions.
        """
        applied_versions: List[str] = []

        with self.connection() as conn:
            self.init_migration_table(conn)
            pending = self.get_pending_migrations(conn)

            for version, name, file_path in pending:
                logger.info("Applying migration %s: %s", version, name)
                sql_content = file_path.read_text(encoding="utf-8")

                try:
                    conn.execute("BEGIN TRANSACTION;")
                    conn.executescript(sql_content)
                    applied_at = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                        (version, name, applied_at),
                    )
                    conn.commit()
                    applied_versions.append(version)
                except Exception as e:
                    conn.rollback()
                    logger.error("Failed to apply migration %s (%s): %s", version, name, e)
                    raise RuntimeError(f"Migration {version} ({name}) failed: {e}") from e

        return applied_versions

    def load_vector_extension(
        self,
        conn: sqlite3.Connection,
        extension_path: Optional[str] = None,
    ) -> bool:
        """Attempt to load the optional sqlite-vec extension.

        Returns:
            True if extension was successfully loaded, False otherwise.
        """
        path = extension_path or os.environ.get("SQLITE_VEC_PATH")
        if not path:
            return False

        try:
            conn.enable_load_extension(True)
            conn.load_extension(path)
            return True
        except Exception as e:
            logger.warning("Could not load vector extension from %s: %s", path, e)
            return False
        finally:
            try:
                conn.enable_load_extension(False)
            except Exception:
                pass

