"""Security and filesystem boundary tests for BrickForge.

Covers:
- Path traversal rejection
- Symlink escape prevention
- Ignored directory and sensitive file filtering (.git, .env, .venv, etc.)
- Oversized file chunking and boundary checks
- Malformed source code resilience without fatal crash
- Unsafe proposal export destination and artifact traversal rejection
- Static AST parsing guarantee: code is never executed during discovery or indexing
"""

import os
from pathlib import Path
import pytest

from brickforge.composition.approval import ProposalApprovalWorkflow
from brickforge.composition.models import CompositionProposal, ProposalArtifact
from brickforge.ingestion.discovery import get_language_hint, walk_registered_roots
from brickforge.ingestion.fingerprints import compute_content_hash, generate_fingerprint
from brickforge.ingestion.ignore_rules import IgnoreRules
from brickforge.ingestion.paths import safe_path_canonicalization
from brickforge.ingestion.pipeline import IngestionPipeline
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


# ---------------------------------------------------------------------------
# 1. Path Traversal & Symlink Escape Tests
# ---------------------------------------------------------------------------

def test_safe_path_canonicalization_blocks_parent_traversal(tmp_path: Path):
    root = tmp_path / "safe_root"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("classified", encoding="utf-8")

    traversal_path = str(root / ".." / "secret.txt")

    with pytest.raises(ValueError, match="Path traversal detected or unsafe root accessed"):
        safe_path_canonicalization(traversal_path, allowed_roots=[root])


def test_safe_path_canonicalization_allows_legitimate_subpaths(tmp_path: Path):
    root = tmp_path / "safe_root"
    sub = root / "subdir"
    sub.mkdir(parents=True)
    target = sub / "module.py"
    target.write_text("x = 1\n", encoding="utf-8")

    canonical = safe_path_canonicalization(target, allowed_roots=[root])
    assert canonical == target.resolve()


def test_symlink_escape_rejected_by_canonicalization(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    outside_file = outside / "leak.py"
    outside_file.write_text("leak = True\n", encoding="utf-8")

    symlink_file = root / "escaped_link.py"
    try:
        symlink_file.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this OS environment")

    # Canonicalization resolves target outside root and raises ValueError
    with pytest.raises(ValueError, match="Path traversal detected or unsafe root accessed"):
        safe_path_canonicalization(symlink_file, allowed_roots=[root])


def test_walk_registered_roots_does_not_follow_symlink_dirs(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "hidden.py").write_text("val = 1\n", encoding="utf-8")

    symlink_dir = root / "linked_dir"
    try:
        symlink_dir.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this OS environment")

    discovered = list(walk_registered_roots([str(root)]))
    discovered_relpaths = [d["relative_path"] for d in discovered]

    # followlinks=False prevents walking into outside_dir
    assert not any("hidden.py" in p for p in discovered_relpaths)


# ---------------------------------------------------------------------------
# 2. Ignored Directories and Sensitive Files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ignored_path",
    [
        ".git/config",
        ".git/objects/00/abc",
        ".env",
        ".env.local",
        ".env.production",
        ".venv/lib/python3.11/site.py",
        "venv/bin/activate",
        "__pycache__/mod.cpython-312.pyc",
        "dist/bundle.js",
        "build/lib/brick.py",
        "node_modules/package/index.js",
        ".pytest_cache/v/cache/lastfailed",
    ],
)
def test_ignore_rules_blocks_sensitive_and_ephemeral_paths(ignored_path: str):
    rules = IgnoreRules()
    assert rules.is_ignored(ignored_path) is True


def test_ignore_rules_permits_standard_source_code():
    rules = IgnoreRules()
    assert rules.is_ignored("src/brickforge/main.py") is False
    assert rules.is_ignored("tests/unit/test_app.py") is False
    assert rules.is_ignored("utils/env_helper.py") is False


# ---------------------------------------------------------------------------
# 3. Oversized File Handling and Chunking
# ---------------------------------------------------------------------------

def test_streaming_hash_chunks_large_file(tmp_path: Path):
    big_file = tmp_path / "big_data.py"
    # Write 256 KB of repetitive dummy source
    chunk = b"# comment line with some arbitrary padding text here\n" * 1024
    with open(big_file, "wb") as f:
        for _ in range(4):
            f.write(chunk)

    assert big_file.stat().st_size > 100 * 1024

    # Stream with small 16KB chunk size
    h1 = compute_content_hash(big_file, chunk_size=16 * 1024)
    h2 = compute_content_hash(big_file, chunk_size=64 * 1024)
    assert h1 == h2
    assert len(h1) == 64


# ---------------------------------------------------------------------------
# 4. Malformed Source Code Handling
# ---------------------------------------------------------------------------

def test_pipeline_handles_malformed_syntax_gracefully(tmp_path: Path):
    db_file = tmp_path / "test_sec.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    repo_dir = tmp_path / "malformed_repo"
    repo_dir.mkdir()

    with db_mgr.connection() as conn:
        conn.execute(
            "INSERT INTO repositories (id, name, root_path) VALUES ('sec-repo', 'Sec Repo', ?);",
            (str(repo_dir),),
        )
        conn.commit()

    brick_repo = BrickRepository(db_mgr)
    pipeline = IngestionPipeline("sec-repo", brick_repo, root_path=repo_dir)

    # Completely broken syntax: unclosed parenthesis and garbage tokens
    malformed_file = repo_dir / "broken.py"
    malformed_file.write_text("def broken_func(\n  !!! ??? @@@\n", encoding="utf-8")

    # Ingestion must not crash or raise uncaught syntax error
    sf_id, report, _ = pipeline.process_file_on_disk("broken.py")
    assert sf_id is not None
    assert report.parse_status in ("failed", "partial")

    with db_mgr.connection() as conn:
        row = conn.execute(
            "SELECT parse_status, parse_diagnostics FROM source_files WHERE row_id = ?;",
            (sf_id,),
        ).fetchone()

    assert row is not None
    parse_status, diagnostics = row[0], row[1]
    assert parse_status in ("failed", "partial")
    assert diagnostics is not None
    assert "SyntaxError" in diagnostics or "error" in diagnostics.lower()


# ---------------------------------------------------------------------------
# 5. Unsafe Export Paths and Traversal in Proposals
# ---------------------------------------------------------------------------

def test_export_rejects_destination_outside_allowlist(tmp_path: Path):
    allowed_dir = tmp_path / "allowed_export"
    allowed_dir.mkdir()
    disallowed_dir = tmp_path / "system_dir"
    disallowed_dir.mkdir()

    workflow = ProposalApprovalWorkflow(allowed_export_destinations=[allowed_dir])
    proposal = CompositionProposal(
        proposal_id="prop-1",
        request_id="req-1",
        adapted_code="def safe(): pass\n",
        source_brick_ids=["b1"],
        status="accepted",
        artifacts=[ProposalArtifact.create(file_path="safe.py", content="def safe(): pass\n")],
    )

    with pytest.raises(PermissionError, match="Export destination .* is not permitted"):
        workflow.export(proposal, destination_dir=disallowed_dir)


def test_export_rejects_artifact_directory_traversal(tmp_path: Path):
    allowed_dir = tmp_path / "allowed_export"
    allowed_dir.mkdir()

    workflow = ProposalApprovalWorkflow(allowed_export_destinations=[allowed_dir])
    proposal = CompositionProposal(
        proposal_id="prop-2",
        request_id="req-2",
        adapted_code="malicious = 1\n",
        source_brick_ids=["b1"],
        status="accepted",
        artifacts=[
            # Artifact attempting to break out of destination_dir
            ProposalArtifact.create(file_path="../../etc/evil.py", content="evil = 1\n")
        ],
    )

    with pytest.raises(ValueError, match="Artifact path traversal attempted"):
        workflow.export(proposal, destination_dir=allowed_dir)


# ---------------------------------------------------------------------------
# 6. Critical Security Invariant: Scanned Code is Never Executed
# ---------------------------------------------------------------------------

def test_indexing_does_not_execute_code_side_effects(tmp_path: Path):
    """Verify that importing or scanning a file with destructive side effects

    does NOT execute arbitrary code (uses static AST analysis).
    """
    db_file = tmp_path / "test_sec_exec.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    repo_dir = tmp_path / "exploit_repo"
    repo_dir.mkdir()

    canary_file = tmp_path / "pwned_canary.txt"
    if canary_file.exists():
        canary_file.unlink()

    # File containing aggressive side-effects if executed via import/exec
    evil_code = f"""
import os
import sys

# If this code were executed, it would create the canary file and raise an error
with open(r"{canary_file}", "w") as f:
    f.write("COMPROMISED")

def innocuous_function(x: int) -> int:
    return x * 2
"""
    evil_py = repo_dir / "exploit.py"
    evil_py.write_text(evil_code, encoding="utf-8")

    with db_mgr.connection() as conn:
        conn.execute(
            "INSERT INTO repositories (id, name, root_path) VALUES ('exp-repo', 'Exploit Repo', ?);",
            (str(repo_dir),),
        )
        conn.commit()

    brick_repo = BrickRepository(db_mgr)
    pipeline = IngestionPipeline("exp-repo", brick_repo, root_path=repo_dir)

    # Process and index file
    pipeline.process_file_on_disk("exploit.py")

    # Invariant: canary file MUST NOT exist!
    assert not canary_file.exists(), "SECURITY VIOLATION: Source code was executed during indexing!"

    # Invariant: innocuous_function was extracted statically as an AST symbol
    with db_mgr.connection() as conn:
        brick = conn.execute(
            "SELECT symbol_name FROM code_bricks WHERE symbol_name = 'innocuous_function';"
        ).fetchone()

    assert brick is not None
    assert brick[0] == "innocuous_function"
