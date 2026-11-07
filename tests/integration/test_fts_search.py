"""Integration tests for SQLite FTS5 search indexing, synchronization, and safe query handling."""

import hashlib
from pathlib import Path
import pytest

from brickforge.parsers.base import ExtractedSymbol
from brickforge.search.fts import FtsSearchEngine, sanitize_fts_query
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def fts_db(tmp_path: Path):
    db_file = tmp_path / "test_fts.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'repo1', '/tmp/repo1');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    file_id = repo.upsert_source_file(
        repository_id="r1",
        relative_path="src/security/crypto.py",
        file_hash="hash_1",
        language="python",
    )

    searcher = FtsSearchEngine(db_mgr)
    return db_mgr, repo, file_id, searcher


def _make_symbol(name: str, doc: str, tags_list: list) -> ExtractedSymbol:
    code = f"def {name}():\n    '''{doc}'''\n    pass"
    return ExtractedSymbol(
        symbol_name=name,
        qualified_name=f"security.{name}",
        kind="function",
        language="python",
        signature=f"def {name}():",
        signature_hash=hashlib.sha256(name.encode()).hexdigest(),
        docstring=doc,
        source_code=code,
        source_hash=hashlib.sha256(code.encode()).hexdigest(),
        start_byte=0,
        end_byte=len(code),
        start_line=1,
        end_line=5,
    )


def test_sanitize_query():
    assert sanitize_fts_query("AES-GCM") == '"AES-GCM"'
    assert sanitize_fts_query("def foo(x: int):") == '"def" "foo" "x" "int"'
    assert sanitize_fts_query("") == '""'
    assert sanitize_fts_query('  "exact phrase"  ') == '"exact phrase"'


def test_fts_insert_search_and_snippet(fts_db):
    db_mgr, repo, file_id, searcher = fts_db

    sym = _make_symbol("encrypt_payload", "High performance AES-GCM payload encryption routine.", ["crypto", "aes"])
    repo.upsert_brick(file_id, sym, tags=["crypto", "aes"])

    # Search by term in docstring with hyphen
    results = searcher.search("AES-GCM")
    assert len(results) == 1
    hit = results[0]
    assert hit.symbol_name == "encrypt_payload"
    assert "encrypt_payload" in hit.qualified_name

    # Search by general keyword
    results_gen = searcher.search("performance encryption")
    assert len(results_gen) >= 1
    assert results_gen[0].symbol_name == "encrypt_payload"


def test_fts_update_and_delete_synchronization(fts_db):
    db_mgr, repo, file_id, searcher = fts_db

    sym1 = _make_symbol("token_validator", "Validates JWT tokens", ["jwt"])
    b_row = repo.upsert_brick(file_id, sym1)

    # Found initially
    assert len(searcher.search("JWT")) == 1

    # Update with new docstring
    sym_updated = _make_symbol("token_validator", "Validates OAuth2 bearer tokens", ["oauth"])
    repo.upsert_brick(file_id, sym_updated)

    # Old term not found, new term found
    assert len(searcher.search("JWT")) == 0
    assert len(searcher.search("OAuth2")) == 1

    # Delete brick
    with db_mgr.connection() as conn:
        conn.execute("DELETE FROM code_bricks WHERE row_id = ?;", (b_row,))
        conn.commit()

    # Search returns empty after deletion
    assert len(searcher.search("OAuth2")) == 0


def test_exact_symbol_lookup(fts_db):
    db_mgr, repo, file_id, searcher = fts_db

    sym = _make_symbol("authenticate", "Authenticate credentials", ["auth"])
    repo.upsert_brick(file_id, sym)

    exact_hits = searcher.search_exact_symbol("authenticate")
    assert len(exact_hits) == 1
    assert exact_hits[0].symbol_name == "authenticate"

    no_hits = searcher.search_exact_symbol("non_existent")
    assert len(no_hits) == 0

