"""Unit tests for composition request and proposal domain models."""

import json
import pytest

from brickforge.composition.models import (
    CompositionConstraints,
    CompositionProposal,
    CompositionRequest,
    ProposalArtifact,
    TargetEnvironment,
)


def test_composition_request_roundtrip():
    req = CompositionRequest(
        request_id="req_test_001",
        target_environment=TargetEnvironment(
            language="python",
            language_version=">=3.11",
            framework="fastapi",
        ),
        selected_brick_ids=["brick_jwt_1", "brick_crypto_2"],
        adaptation_instructions="Wrap token verification in a FastAPI dependency.",
        interface_contract={
            "inputs": [{"name": "auth_header", "type": "str"}],
            "outputs": [{"name": "user_id", "type": "str"}],
        },
        constraints=CompositionConstraints(
            max_external_dependencies=2,
            disallow_eval_exec=True,
            pure_function_preferred=True,
        ),
    )

    data = req.to_dict()
    assert data["request_id"] == "req_test_001"
    assert data["target_environment"]["framework"] == "fastapi"
    assert data["constraints"]["pure_function_preferred"] is True

    json_str = req.to_json()
    assert "FastAPI" in json_str

    restored = CompositionRequest.from_dict(json.loads(json_str))
    assert restored.request_id == req.request_id
    assert restored.target_environment.framework == "fastapi"
    assert restored.selected_brick_ids == ["brick_jwt_1", "brick_crypto_2"]
    assert restored.constraints.max_external_dependencies == 2


def test_proposal_artifact_creation():
    art = ProposalArtifact.create(
        file_path="src/security/dependencies.py",
        content="def get_current_user(): pass\n",
    )
    assert art.artifact_id.startswith("art_")
    assert art.file_path == "src/security/dependencies.py"
    assert len(art.content_hash) == 64


def test_composition_proposal_lifecycle_and_serialization():
    art = ProposalArtifact.create("out/service.py", "class AdaptedService: pass")
    prop = CompositionProposal(
        proposal_id="prop_001",
        request_id="req_test_001",
        status="draft",
        adapted_code="class AdaptedService: pass",
        source_brick_ids=["brick_1"],
        artifacts=[art],
        rationale="Adapted synchronous client to async coroutines for FastAPI.",
        confidence_score=0.95,
        warnings=["Check connection pooling settings."],
    )

    # Initial state is draft proposal
    assert prop.status == "draft"

    data = prop.to_dict()
    assert data["proposal_id"] == "prop_001"
    assert len(data["artifacts"]) == 1

    json_str = prop.to_json()
    restored = CompositionProposal.from_dict(json.loads(json_str))

    assert restored.proposal_id == prop.proposal_id
    assert restored.status == "draft"
    assert len(restored.artifacts) == 1
    assert restored.artifacts[0].file_path == "out/service.py"
    assert restored.confidence_score == 0.95

    # Lifecycle state transition to review and accepted
    prop.status = "review"
    assert prop.status == "review"
    prop.status = "accepted"
    assert prop.status == "accepted"

