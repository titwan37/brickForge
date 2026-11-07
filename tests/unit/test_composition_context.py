"""Unit tests for deterministic composition context builder."""

from pathlib import Path
import pytest

from brickforge.composition.context import CompositionContextBuilder
from brickforge.composition.models import (
    CompositionConstraints,
    CompositionRequest,
    TargetEnvironment,
)
from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def context_db_fixture(tmp_path: Path):
    db_file = tmp_path / "test_context.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/tmp/r1');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    file_id = repo.upsert_source_file("r1", "src/crypto.py", "hash1", "python")

    sym1 = ExtractedSymbol(
        symbol_name="encrypt_aes",
        qualified_name="crypto.encrypt_aes",
        kind="function",
        language="python",
        signature="def encrypt_aes(key: bytes, data: bytes) -> bytes:",
        signature_hash="sig_1",
        docstring="Encrypts data using AES-GCM.",
        source_code="def encrypt_aes(key: bytes, data: bytes) -> bytes:\n    return data\n",
        source_hash="src_1",
        start_byte=0,
        end_byte=60,
        start_line=1,
        end_line=3,
    )
    b1_id = repo.upsert_brick(file_id, sym1, brick_id="brick_aes_01")
    repo.insert_external_package(b1_id, "pip", "cryptography", "from cryptography import hazmat")

    sym2 = ExtractedSymbol(
        symbol_name="decrypt_aes",
        qualified_name="crypto.decrypt_aes",
        kind="function",
        language="python",
        signature="def decrypt_aes(key: bytes, data: bytes) -> bytes:",
        signature_hash="sig_2",
        docstring="Decrypts data using AES-GCM.",
        source_code="def decrypt_aes(key: bytes, data: bytes) -> bytes:\n    return data\n",
        source_hash="src_2",
        start_byte=70,
        end_byte=130,
        start_line=5,
        end_line=7,
    )
    repo.upsert_brick(file_id, sym2, brick_id="brick_aes_02")

    builder = CompositionContextBuilder(db_mgr)
    return db_mgr, builder


def test_build_composition_context(context_db_fixture):
    db_mgr, builder = context_db_fixture

    req = CompositionRequest(
        request_id="req_compose_1",
        target_environment=TargetEnvironment(language="python", framework="fastapi"),
        selected_brick_ids=["brick_aes_01"],
        adaptation_instructions="Expose encryption as an async HTTP endpoint.",
        constraints=CompositionConstraints(disallow_eval_exec=True),
    )

    ctx = builder.build_context(req)

    assert ctx.request_id == "req_compose_1"
    assert ctx.target_environment.framework == "fastapi"
    assert len(ctx.contracts) == 1
    assert ctx.contracts[0]["symbol_name"] == "encrypt_aes"
    assert len(ctx.source_bundles) == 1
    assert "def encrypt_aes" in ctx.source_bundles[0]["source_code"]
    assert len(ctx.manifests) == 1
    assert not ctx.is_truncated

    # Verify prompt-ready rendering
    prompt = ctx.to_prompt_context()
    assert "# Composition Context" in prompt
    assert "Expose encryption as an async HTTP endpoint." in prompt
    assert "def encrypt_aes" in prompt


def test_context_budget_truncation(context_db_fixture):
    db_mgr, builder = context_db_fixture

    req = CompositionRequest(
        request_id="req_compose_2",
        target_environment=TargetEnvironment(language="python"),
        selected_brick_ids=["brick_aes_01", "brick_aes_02"],
        adaptation_instructions="Adapt both functions.",
    )

    # Force a very tight token budget of 10 tokens (~40 chars)
    ctx = builder.build_context(req, max_tokens=10)
    assert ctx.is_truncated
    assert len(ctx.contracts) == 0  # Truncated because first item exceeded budget

