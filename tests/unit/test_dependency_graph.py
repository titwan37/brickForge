"""Unit tests for dependency graph traversal, cycle detection, and budget limits."""

import hashlib
from pathlib import Path
import pytest

from brickforge.analysis.graph import DependencyGraphTraverser
from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def graph_db(tmp_path: Path):
    db_file = tmp_path / "test_graph.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/tmp/r1');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    file_id = repo.upsert_source_file("r1", "src/mod.py", "h1", "python")

    def _add_brick(name: str) -> int:
        sym = ExtractedSymbol(
            symbol_name=name,
            qualified_name=f"mod.{name}",
            kind="function",
            language="python",
            signature=f"def {name}():",
            signature_hash=f"sig_{name}",
            docstring=None,
            source_code=f"def {name}(): pass",
            source_hash=f"src_{name}",
            start_byte=0,
            end_byte=20,
            start_line=1,
            end_line=2,
        )
        return repo.upsert_brick(file_id, sym)

    traverser = DependencyGraphTraverser(db_mgr)
    return db_mgr, repo, _add_brick, traverser


def test_outgoing_traversal_depth(graph_db):
    db_mgr, repo, add_brick, traverser = graph_db

    b1 = add_brick("A")
    b2 = add_brick("B")
    b3 = add_brick("C")
    b4 = add_brick("D")

    # A -> B -> C -> D
    repo.insert_dependency(b1, "calls", target_row_id=b2)
    repo.insert_dependency(b2, "calls", target_row_id=b3)
    repo.insert_dependency(b3, "calls", target_row_id=b4)

    # Max depth = 1: should only visit A and B
    res_d1 = traverser.traverse(start_row_id=b1, max_depth=1)
    assert len(res_d1.nodes) == 2
    assert str(b1) in res_d1.nodes
    assert str(b2) in res_d1.nodes
    assert str(b3) not in res_d1.nodes

    # Max depth = 3: visits A, B, C, D
    res_d3 = traverser.traverse(start_row_id=b1, max_depth=3)
    assert len(res_d3.nodes) == 4
    assert len(res_d3.edges) == 3


def test_incoming_traversal(graph_db):
    db_mgr, repo, add_brick, traverser = graph_db

    b1 = add_brick("Caller1")
    b2 = add_brick("Caller2")
    b3 = add_brick("TargetService")

    # Caller1 -> TargetService, Caller2 -> TargetService
    repo.insert_dependency(b1, "calls", target_row_id=b3)
    repo.insert_dependency(b2, "calls", target_row_id=b3)

    res = traverser.traverse(start_row_id=b3, direction="incoming", max_depth=1)
    assert len(res.nodes) == 3
    assert str(b3) in res.nodes
    assert str(b1) in res.nodes
    assert str(b2) in res.nodes


def test_unresolved_and_external_edges(graph_db):
    db_mgr, repo, add_brick, traverser = graph_db

    b1 = add_brick("RootService")
    repo.insert_dependency(
        source_row_id=b1,
        dependency_type="calls",
        unresolved_symbol="external_lib.fetch",
        resolution_status="external",
    )
    repo.insert_dependency(
        source_row_id=b1,
        dependency_type="calls",
        unresolved_symbol="missing_helper",
        resolution_status="unresolved",
    )

    res = traverser.traverse(start_row_id=b1, max_depth=1)
    assert res.external_count == 1
    assert res.unresolved_count == 1
    assert len(res.edges) == 2


def test_cycle_detection(graph_db):
    db_mgr, repo, add_brick, traverser = graph_db

    b1 = add_brick("CycleA")
    b2 = add_brick("CycleB")

    # Cycle: A -> B -> A
    repo.insert_dependency(b1, "calls", target_row_id=b2)
    repo.insert_dependency(b2, "calls", target_row_id=b1)

    res = traverser.traverse(start_row_id=b1, max_depth=5)
    assert len(res.cycles) > 0
    cycle = res.cycles[0]
    assert str(b1) in cycle
    assert str(b2) in cycle


def test_budget_limits(graph_db):
    db_mgr, repo, add_brick, traverser = graph_db

    b1 = add_brick("Root")
    for i in range(10):
        child = add_brick(f"Child_{i}")
        repo.insert_dependency(b1, "calls", target_row_id=child)

    res = traverser.traverse(start_row_id=b1, max_nodes=4)
    assert res.budget_exceeded
    assert len(res.nodes) <= 5

