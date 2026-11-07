"""Unit tests for composition provider interface and mock implementation."""

import pytest

from brickforge.composition.context import CompositionContext
from brickforge.composition.models import CompositionConstraints, TargetEnvironment
from brickforge.composition.provider import MockCompositionProvider


@pytest.fixture
def sample_context():
    return CompositionContext(
        request_id="req_test_101",
        target_environment=TargetEnvironment(language="python", framework="fastapi"),
        adaptation_instructions="Add docstrings and type annotations.",
        constraints=CompositionConstraints(),
        contracts=[{"symbol_name": "clean_text", "kind": "function"}],
        source_bundles=[{"brick_id": "b1", "symbol_name": "clean_text", "source_code": "def clean_text(s):\n    return s.strip()"}],
        manifests=[],
    )


def test_mock_provider_default_generation(sample_context):
    provider = MockCompositionProvider()
    assert provider.provider_name == "mock_provider"
    assert provider.model_id == "deterministic-v1"

    proposal = provider.generate_proposal(sample_context)

    assert proposal.status == "draft"
    assert proposal.request_id == "req_test_101"
    assert "clean_text" in proposal.adapted_code
    assert proposal.source_brick_ids == ["b1"]
    assert len(proposal.artifacts) == 1
    assert proposal.artifacts[0].file_path == "adapted_module.py"
    assert proposal.confidence_score == 0.90
    assert not proposal.warnings


def test_mock_provider_custom_generator(sample_context):
    def custom_gen(ctx):
        return f"# Custom generated: {ctx.request_id}"

    provider = MockCompositionProvider(custom_generator=custom_gen)
    proposal = provider.generate_proposal(sample_context)

    assert proposal.adapted_code == "# Custom generated: req_test_101"


def test_mock_provider_records_truncation_warning(sample_context):
    sample_context.is_truncated = True
    provider = MockCompositionProvider()
    proposal = provider.generate_proposal(sample_context)

    assert any("truncated" in w for w in proposal.warnings)

