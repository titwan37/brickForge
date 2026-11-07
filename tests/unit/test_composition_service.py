"""Unit tests for composition service adaptation proposal workflow and diffing."""

from pathlib import Path
import pytest

from brickforge.composition.models import (
    CompositionConstraints,
    CompositionRequest,
    TargetEnvironment,
)
from brickforge.composition.provider import MockCompositionProvider
from brickforge.composition.service import CompositionService
from brickforge.parsers.base import ExtractedSymbol
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


@pytest.fixture
def service_env(tmp_path: Path):
    db_file = tmp_path / "test_comp_svc.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.apply_migrations()

    with db_mgr.connection() as conn:
        conn.execute("INSERT INTO repositories (id, name, root_path) VALUES ('r1', 'R1', '/tmp/r1');")
        conn.commit()

    repo = BrickRepository(db_mgr)
    file_id = repo.upsert_source_file("r1", "src/auth.py", "hash1", "python")

    sym = ExtractedSymbol(
        symbol_name="login_user",
        qualified_name="auth.login_user",
        kind="function",
        language="python",
        signature="def login_user(username, password):",
        signature_hash="sig_login",
        docstring="Authenticate user.",
        source_code="def login_user(username, password):\n    return True\n",
        source_hash="src_login",
        start_byte=0,
        end_byte=50,
        start_line=1,
        end_line=3,
    )
    b_id = repo.upsert_brick(file_id, sym, brick_id="brick_login_01")

    service = CompositionService(db_mgr)
    return db_mgr, b_id, service


def test_create_adaptation_proposal(service_env):
    db_mgr, brick_id, service = service_env

    req = CompositionRequest(
        request_id="req_adapt_1",
        target_environment=TargetEnvironment(language="python", framework="fastapi"),
        selected_brick_ids=["brick_login_01"],
        adaptation_instructions="Make async with type annotations.",
    )

    result = service.create_proposal(req)

    # 1. Proposal verified
    assert result.proposal.request_id == "req_adapt_1"
    assert result.proposal.status == "draft"
    assert "login_user" in result.proposal.adapted_code
    assert result.proposal.rationale != ""

    # 2. Diff verified
    assert result.diff != ""
    assert "--- original_bricks.py" in result.diff
    assert "+++ proposed_adaptation.py" in result.diff

    # 3. Provider metadata verified
    assert result.provider_metadata.provider_name == "mock_provider"
    assert result.provider_metadata.model_id == "deterministic-v1"


def test_custom_provider_override(service_env):
    db_mgr, brick_id, service = service_env

    custom_provider = MockCompositionProvider(
        provider_name="custom_llm_adapter",
        model_id="qwen-coder-32b",
        custom_generator=lambda ctx: "async def login_user(u: str, p: str) -> bool: return True\n",
    )

    req = CompositionRequest(
        request_id="req_custom_1",
        target_environment=TargetEnvironment(language="python"),
        selected_brick_ids=["brick_login_01"],
        adaptation_instructions="Adapt to async",
    )

    result = service.create_proposal(req, provider=custom_provider)

    assert result.provider_metadata.provider_name == "custom_llm_adapter"
    assert result.provider_metadata.model_id == "qwen-coder-32b"
    assert "async def login_user" in result.proposed_source
    assert "-" in result.diff and "+" in result.diff

