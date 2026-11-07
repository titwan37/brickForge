"""Unit tests for filtered catalog search service."""

import hashlib
from pathlib import Path
import pytest

from brickforge.parsers.base import ExtractedSymbol
from brickforge.search.service import CatalogQuery, CatalogSearchService
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def search_service_fixture(tmp_path: Path):
    db_file = tmp_path / "test_search_svc.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    # Create two repositories
    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('repo-A', 'Repo A', '/path/a');")
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('repo-B', 'Repo B', '/path/b');")
        conn.commit()

    repo = BrickRepository(db_mgr)

    # File 1 in Repo A: Auth module
    f1 = repo.upsert_source_file("repo-A", "src/auth/jwt.py", "hash1", "python")
    b1_sym = ExtractedSymbol(
        symbol_name="verify_jwt",
        qualified_name="auth.jwt.verify_jwt",
        kind="function",
        language="python",
        signature="def verify_jwt(token: str) -> bool:",
        signature_hash="h1",
        docstring="Verifies JWT signature and claims.",
        source_code="def verify_jwt(): pass",
        source_hash="s1",
        start_byte=0,
        end_byte=50,
        start_line=1,
        end_line=5,
    )
    b1_id = repo.upsert_brick(f1, b1_sym, portability_score=0.9, tags=["auth", "jwt"])
    repo.insert_external_package(b1_id, "pip", "pyjwt", "import jwt")

    # File 2 in Repo A: Class
    b2_sym = ExtractedSymbol(
        symbol_name="AuthService",
        qualified_name="auth.service.AuthService",
        kind="class",
        language="python",
        signature="class AuthService:",
        signature_hash="h2",
        docstring="Manages authentication flows.",
        source_code="class AuthService: pass",
        source_hash="s2",
        start_byte=0,
        end_byte=100,
        start_line=10,
        end_line=30,
    )
    repo.upsert_brick(f1, b2_sym, portability_score=0.6, tags=["auth"])

    # File 3 in Repo B: Math helper
    f2 = repo.upsert_source_file("repo-B", "src/math/calc.py", "hash2", "python")
    b3_sym = ExtractedSymbol(
        symbol_name="matrix_mult",
        qualified_name="math.calc.matrix_mult",
        kind="function",
        language="python",
        signature="def matrix_mult(a, b):",
        signature_hash="h3",
        docstring="Fast matrix multiplication with numpy.",
        source_code="def matrix_mult(): pass",
        source_hash="s3",
        start_byte=0,
        end_byte=60,
        start_line=1,
        end_line=10,
    )
    b3_id = repo.upsert_brick(f2, b3_sym, portability_score=0.4, tags=["math", "matrix"])
    repo.insert_external_package(b3_id, "pip", "numpy", "import numpy as np")

    svc = CatalogSearchService(db_mgr)
    return svc


def test_filter_by_repository(search_service_fixture):
    svc = search_service_fixture
    hits_a = svc.search(CatalogQuery(repository_id="repo-A"))
    assert len(hits_a) == 2
    assert all(h.repository_id == "repo-A" for h in hits_a)

    hits_b = svc.search(CatalogQuery(repository_id="repo-B"))
    assert len(hits_b) == 1
    assert hits_b[0].symbol_name == "matrix_mult"


def test_filter_by_kind_and_portability(search_service_fixture):
    svc = search_service_fixture

    # Only functions
    hits_func = svc.search(CatalogQuery(kind="function"))
    assert len(hits_func) == 2
    assert {h.symbol_name for h in hits_func} == {"verify_jwt", "matrix_mult"}

    # Only classes
    hits_cls = svc.search(CatalogQuery(kind="class"))
    assert len(hits_cls) == 1
    assert hits_cls[0].symbol_name == "AuthService"

    # Minimum portability 0.8
    hits_portable = svc.search(CatalogQuery(min_portability=0.8))
    assert len(hits_portable) == 1
    assert hits_portable[0].symbol_name == "verify_jwt"
    assert hits_portable[0].portability_score >= 0.8


def test_filter_by_package_dependency(search_service_fixture):
    svc = search_service_fixture

    hits_jwt = svc.search(CatalogQuery(package_dependency="jwt"))
    assert len(hits_jwt) == 1
    assert hits_jwt[0].symbol_name == "verify_jwt"

    hits_numpy = svc.search(CatalogQuery(package_dependency="numpy"))
    assert len(hits_numpy) == 1
    assert hits_numpy[0].symbol_name == "matrix_mult"


def test_combined_fts_and_filters(search_service_fixture):
    svc = search_service_fixture

    # FTS "signature" + kind="function"
    hits = svc.search(CatalogQuery(query="signature", kind="function"))
    assert len(hits) == 1
    assert hits[0].symbol_name == "verify_jwt"

    # FTS "matrix" in repo-A returns 0
    hits_empty = svc.search(CatalogQuery(query="matrix", repository_id="repo-A"))
    assert len(hits_empty) == 0

