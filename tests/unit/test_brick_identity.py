"""Unit tests for deterministic brick identity, provenance tracking, and deduplication rules."""

import pytest

from brickforge.identity import (
    BrickIdentity,
    are_exact_duplicates,
    are_semantic_duplicates,
    compute_brick_id,
    compute_semantic_hash,
    detect_renamed_bricks,
    group_duplicate_bricks,
    is_same_provenance,
    normalize_code_for_semantic_hash,
)


def test_compute_brick_id_determinism():
    id1 = compute_brick_id("repo-A", "src/calc.py", "add", "function")
    id2 = compute_brick_id("repo-A", "src/calc.py", "add", "function")
    assert id1 == id2
    assert id1.startswith("brick_")

    # Path normalization produces identical ID
    id_norm = compute_brick_id("repo-A", "src\\calc.py", "add", "function")
    assert id_norm == id1

    # Different repo produces different ID
    id_other_repo = compute_brick_id("repo-B", "src/calc.py", "add", "function")
    assert id_other_repo != id1

    # Different symbol produces different ID
    id_other_sym = compute_brick_id("repo-A", "src/calc.py", "multiply", "function")
    assert id_other_sym != id1


def test_provenance_preservation():
    b1 = BrickIdentity.from_symbol_and_provenance(
        repository_id="repo-1",
        relative_path="src/a.py",
        qualified_name="Foo",
        kind="class",
        source_code="class Foo: pass",
    )
    b2 = BrickIdentity.from_symbol_and_provenance(
        repository_id="repo-1",
        relative_path="src/a.py",
        qualified_name="Foo",
        kind="class",
        source_code="class Foo:\n    pass",
    )
    b3 = BrickIdentity.from_symbol_and_provenance(
        repository_id="repo-2",
        relative_path="src/a.py",
        qualified_name="Foo",
        kind="class",
        source_code="class Foo: pass",
    )

    assert is_same_provenance(b1, b2)
    assert not is_same_provenance(b1, b3)  # different repository provenance
    assert b1.brick_id != b3.brick_id


def test_semantic_hash_and_duplicates():
    code_raw = """
def calculate(a, b):
    # This is a comment
    result = a + b
    return result
"""
    code_formatted = """
def calculate(a, b):
    result = a + b
    return result
"""

    b1 = BrickIdentity.from_symbol_and_provenance("repo-1", "f1.py", "calculate", "function", code_raw)
    b2 = BrickIdentity.from_symbol_and_provenance("repo-2", "f2.py", "calculate", "function", code_formatted)

    # Exact content hashes differ due to comment
    assert not are_exact_duplicates(b1, b2)

    # Semantic hashes match because logic and tokens are identical
    assert are_semantic_duplicates(b1, b2)


def test_group_duplicate_bricks_across_repositories():
    code = "def shared_util(): return True"

    b_repo1 = BrickIdentity.from_symbol_and_provenance("repo-1", "pkg/util.py", "shared_util", "function", code)
    b_repo2 = BrickIdentity.from_symbol_and_provenance("repo-2", "lib/common.py", "shared_util", "function", code)
    b_unique = BrickIdentity.from_symbol_and_provenance("repo-1", "pkg/other.py", "other_fn", "function", "def other_fn(): return 42")

    groups = group_duplicate_bricks([b_repo1, b_repo2, b_unique], semantic=True)

    # Should find one duplicate cluster
    assert len(groups) == 1
    cluster = next(iter(groups.values()))
    assert len(cluster) == 2
    assert {b.repository_id for b in cluster} == {"repo-1", "repo-2"}


def test_detect_renamed_bricks():
    code = "def algorithm(x):\n    return x * 2 + 1"

    old_b = BrickIdentity.from_symbol_and_provenance("repo-1", "old/algo.py", "algo_v1", "function", code)
    new_b = BrickIdentity.from_symbol_and_provenance("repo-1", "new/core_algo.py", "core_algorithm", "function", code)

    renamed = detect_renamed_bricks([old_b], [new_b])
    assert len(renamed) == 1
    src, dst = renamed[0]
    assert src.qualified_name == "algo_v1"
    assert dst.qualified_name == "core_algorithm"
    assert dst.relative_path == "new/core_algo.py"

