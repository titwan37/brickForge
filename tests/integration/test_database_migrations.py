"""Integration tests for SQLite connection and migration manager."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from brickforge.storage.database import DatabaseManager


class TestDatabaseManager:
    """Tests for DatabaseManager connection and migration handling."""

    def test_connection_pragmas(self, tmp_path: Path):
        db_file = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_file, wal_mode=True, busy_timeout_ms=3000)

        with manager.connection() as conn:
            # Check foreign keys
            fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            assert fk == 1

            # Check busy timeout
            timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            assert timeout == 3000

            # Check journal mode (WAL for disk-based databases)
            journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert journal.lower() == "wal"

    def test_foreign_key_enforcement(self, tmp_path: Path):
        db_file = tmp_path / "fk_test.db"
        manager = DatabaseManager(db_path=db_file)

        with manager.connection() as conn:
            conn.execute(
                """
                CREATE TABLE parents (id INTEGER PRIMARY KEY);
                """
            )
            conn.execute(
                """
                CREATE TABLE children (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER REFERENCES parents(id)
                );
                """
            )

            # Valid insertion
            conn.execute("INSERT INTO parents (id) VALUES (1);")
            conn.execute("INSERT INTO children (id, parent_id) VALUES (10, 1);")

            # Invalid insertion violates foreign key
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO children (id, parent_id) VALUES (20, 999);")

    def test_migration_discovery_and_ordering(self, tmp_path: Path):
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "0002_second.sql").write_text("CREATE TABLE t2 (id INT);", encoding="utf-8")
        (migrations_dir / "0001_first.sql").write_text("CREATE TABLE t1 (id INT);", encoding="utf-8")
        (migrations_dir / "README.txt").write_text("ignored non-sql", encoding="utf-8")

        manager = DatabaseManager(db_path=tmp_path / "test.db", migrations_dir=migrations_dir)
        available = manager.get_available_migrations()

        assert len(available) == 2
        assert available[0][0] == "0001"
        assert available[0][1] == "first"
        assert available[1][0] == "0002"
        assert available[1][1] == "second"

    def test_apply_migrations_idempotency(self, tmp_path: Path):
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "0001_initial.sql").write_text(
            """
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            """,
            encoding="utf-8",
        )
        (migrations_dir / "0002_add_index.sql").write_text(
            """
            CREATE INDEX idx_items_name ON items(name);
            """,
            encoding="utf-8",
        )

        manager = DatabaseManager(db_path=tmp_path / "catalog.db", migrations_dir=migrations_dir)

        # First application
        applied = manager.apply_migrations()
        assert applied == ["0001", "0002"]

        # Verify tables and index exist
        with manager.connection() as conn:
            applied_recorded = manager.get_applied_migrations(conn)
            assert applied_recorded == ["0001", "0002"]

            # Test inserting into migrated table
            conn.execute("INSERT INTO items (name) VALUES ('brick-1');")
            item = conn.execute("SELECT name FROM items WHERE id = 1;").fetchone()
            assert item[0] == "brick-1"

        # Re-applying should be a no-op
        reapplied = manager.apply_migrations()
        assert reapplied == []

    def test_migration_rollback_on_failure(self, tmp_path: Path):
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "0001_good.sql").write_text(
            "CREATE TABLE good_table (id INT PRIMARY KEY);", encoding="utf-8"
        )
        (migrations_dir / "0002_bad.sql").write_text(
            "SYNTAX ERROR INVALID SQL STATEMENTS;", encoding="utf-8"
        )

        manager = DatabaseManager(db_path=tmp_path / "fail.db", migrations_dir=migrations_dir)

        with pytest.raises(RuntimeError, match="Migration 0002"):
            manager.apply_migrations()

        # 0001 succeeded, but 0002 failed and was not recorded
        with manager.connection() as conn:
            applied = manager.get_applied_migrations(conn)
            assert applied == ["0001"]

    def test_vector_extension_graceful_failure(self, tmp_path: Path):
        manager = DatabaseManager(db_path=tmp_path / "vec.db")
        with manager.connection() as conn:
            # When path is missing or non-existent, it should return False without crashing
            assert manager.load_vector_extension(conn, extension_path=None) is False
            assert manager.load_vector_extension(conn, extension_path="/non/existent/vec0.dll") is False

