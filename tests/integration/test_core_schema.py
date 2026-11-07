"""Integration tests for BrickForge core relational schema and FTS5 triggers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from brickforge.storage.database import DatabaseManager


class TestCoreSchema:
    """Tests verifying the 0001_core.sql schema tables, constraints, and triggers."""

    @pytest.fixture
    def db_manager(self, tmp_path: Path) -> DatabaseManager:
        db_file = tmp_path / "catalog.db"
        manager = DatabaseManager(db_path=db_file)
        applied = manager.apply_migrations()
        assert "0001" in applied
        return manager

    def test_core_tables_created(self, db_manager: DatabaseManager):
        expected_tables = {
            "schema_migrations",
            "repositories",
            "scan_runs",
            "source_files",
            "code_bricks",
            "brick_dependencies",
            "external_packages",
            "brick_embedding_state",
            "bricks_fts",
        }
        with db_manager.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow');")
            actual_tables = {row[0] for row in cursor.fetchall()}
            assert expected_tables.issubset(actual_tables)

    def test_repository_lifecycle_and_constraints(self, db_manager: DatabaseManager):
        with db_manager.connection() as conn:
            # Valid insert
            conn.execute(
                """
                INSERT INTO repositories (id, name, root_path, source_kind)
                VALUES ('repo-1', 'Main Repo', '/repos/main', 'directory');
                """
            )
            conn.commit()

            repo = conn.execute("SELECT name, source_kind FROM repositories WHERE id = 'repo-1';").fetchone()
            assert repo == ("Main Repo", "directory")

            # Duplicate root_path raises error
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO repositories (id, name, root_path)
                    VALUES ('repo-2', 'Clone Repo', '/repos/main');
                    """
                )

            # Invalid source_kind raises CHECK constraint violation
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO repositories (id, name, root_path, source_kind)
                    VALUES ('repo-3', 'Bad Repo', '/repos/bad', 'invalid_kind');
                    """
                )

    def test_source_file_and_scan_run_foreign_keys(self, db_manager: DatabaseManager):
        with db_manager.connection() as conn:
            conn.execute(
                "INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/r1');"
            )
            conn.execute(
                "INSERT INTO scan_runs (id, repository_id, status) VALUES ('s1', 'r1', 'completed');"
            )
            conn.execute(
                """
                INSERT INTO source_files (
                    id, repository_id, relative_path, language, file_hash, byte_size, loc, last_seen_run_id
                ) VALUES ('f1', 'r1', 'src/app.py', 'python', 'hash123', 500, 20, 's1');
                """
            )
            conn.commit()

            file_row = conn.execute("SELECT relative_path, language FROM source_files WHERE id = 'f1';").fetchone()
            assert file_row == ("src/app.py", "python")

    def test_fts5_triggers_insert_search_delete(self, db_manager: DatabaseManager):
        with db_manager.connection() as conn:
            # Seed repo and file
            conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/r1');")
            conn.execute(
                """
                INSERT INTO source_files (row_id, id, repository_id, relative_path, language, file_hash)
                VALUES (1, 'f1', 'r1', 'src/crypto.py', 'python', 'h1');
                """
            )

            # Insert code brick
            conn.execute(
                """
                INSERT INTO code_bricks (
                    row_id, id, file_id, symbol_name, qualified_name, kind, language,
                    signature, signature_hash, docstring, source_code, source_hash,
                    start_line, end_line, ai_summary, tags
                ) VALUES (
                    100, 'b_crypto_1', 1, 'encrypt_token', 'crypto::encrypt_token', 'function', 'python',
                    'def encrypt_token(payload: bytes) -> str', 'sig_hash_1',
                    'Encrypts an authentication payload using AES-GCM.',
                    'def encrypt_token(payload: bytes) -> str:\n    return cipher.encrypt(payload)',
                    'src_hash_1', 10, 15,
                    'AES-GCM encryption routine for auth tokens', '["crypto", "auth", "aes"]'
                );
                """
            )
            conn.commit()

            # FTS5 search query
            fts_hits = conn.execute(
                """
                SELECT rowid, symbol_name, signature
                FROM bricks_fts
                WHERE bricks_fts MATCH '"AES-GCM" OR encrypt_token';
                """
            ).fetchall()


            assert len(fts_hits) == 1
            assert fts_hits[0][0] == 100
            assert fts_hits[0][1] == "encrypt_token"

            # Update brick and test FTS synchronization
            conn.execute(
                """
                UPDATE code_bricks
                SET docstring = 'Updated documentation for token encryption'
                WHERE row_id = 100;
                """
            )
            conn.commit()

            updated_hits = conn.execute(
                "SELECT rowid FROM bricks_fts WHERE bricks_fts MATCH 'Updated';"
            ).fetchall()
            assert len(updated_hits) == 1

            # Delete brick and test FTS synchronization
            conn.execute("DELETE FROM code_bricks WHERE row_id = 100;")
            conn.commit()

            deleted_hits = conn.execute(
                "SELECT rowid FROM bricks_fts WHERE bricks_fts MATCH 'encrypt_token';"
            ).fetchall()
            assert len(deleted_hits) == 0

    def test_brick_dependencies_check_constraints(self, db_manager: DatabaseManager):
        with db_manager.connection() as conn:
            conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/r1');")
            conn.execute(
                "INSERT INTO source_files (row_id, id, repository_id, relative_path, language, file_hash) "
                "VALUES (1, 'f1', 'r1', 'src/a.py', 'python', 'h1');"
            )
            conn.execute(
                """
                INSERT INTO code_bricks (
                    row_id, id, file_id, symbol_name, qualified_name, kind, language,
                    signature_hash, source_code, source_hash, start_line, end_line
                ) VALUES
                (1, 'b1', 1, 'caller', 'caller', 'function', 'python', 's1', 'code1', 'c1', 1, 5),
                (2, 'b2', 1, 'callee', 'callee', 'function', 'python', 's2', 'code2', 'c2', 6, 10);
                """
            )
            conn.commit()

            # 1. Valid resolved dependency
            conn.execute(
                """
                INSERT INTO brick_dependencies (
                    source_row_id, target_row_id, unresolved_symbol, dependency_type, resolution_status, confidence
                ) VALUES (1, 2, NULL, 'calls', 'resolved', 1.0);
                """
            )
            conn.commit()

            # 2. Valid unresolved dependency
            conn.execute(
                """
                INSERT INTO brick_dependencies (
                    source_row_id, target_row_id, unresolved_symbol, dependency_type, resolution_status, confidence
                ) VALUES (1, NULL, 'external_lib.helper', 'imports', 'unresolved', 0.5);
                """
            )
            conn.commit()

            # 3. Invalid dependency: both target and unresolved symbol set (violates CHECK)
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO brick_dependencies (
                        source_row_id, target_row_id, unresolved_symbol, dependency_type, resolution_status
                    ) VALUES (1, 2, 'external_lib.helper', 'calls', 'resolved');
                    """
                )

    def test_cascading_deletions(self, db_manager: DatabaseManager):
        with db_manager.connection() as conn:
            conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/r1');")
            conn.execute(
                "INSERT INTO source_files (row_id, id, repository_id, relative_path, language, file_hash) "
                "VALUES (1, 'f1', 'r1', 'src/a.py', 'python', 'h1');"
            )
            conn.execute(
                """
                INSERT INTO code_bricks (
                    row_id, id, file_id, symbol_name, qualified_name, kind, language,
                    signature_hash, source_code, source_hash, start_line, end_line
                ) VALUES (1, 'b1', 1, 'fn', 'fn', 'function', 'python', 's1', 'code', 'c1', 1, 5);
                """
            )
            conn.execute(
                """
                INSERT INTO external_packages (brick_row_id, ecosystem, package_name, import_statement)
                VALUES (1, 'pypi', 'pydantic', 'import pydantic');
                """
            )
            conn.commit()

            # Deleting the repository should cascade-delete source files, code bricks, and external packages
            conn.execute("DELETE FROM repositories WHERE id = 'r1';")
            conn.commit()

            assert conn.execute("SELECT COUNT(*) FROM source_files;").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM external_packages;").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM bricks_fts;").fetchone()[0] == 0
