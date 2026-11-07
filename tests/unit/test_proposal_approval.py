"""Unit tests for proposal approval, rejection, and secure allowlisted export."""

from pathlib import Path
import pytest

from brickforge.composition.approval import ProposalApprovalWorkflow
from brickforge.composition.models import CompositionProposal, ProposalArtifact


@pytest.fixture
def sample_proposal():
    art = ProposalArtifact.create("service.py", "def run(): return 42\n")
    return CompositionProposal(
        proposal_id="prop_test_01",
        request_id="req_01",
        status="draft",
        adapted_code="def run(): return 42\n",
        source_brick_ids=["b1"],
        artifacts=[art],
    )


def test_proposal_accept_and_reject(sample_proposal):
    workflow = ProposalApprovalWorkflow()

    # Accept
    workflow.accept(sample_proposal, reviewer="alice", notes="Looks great.")
    assert sample_proposal.status == "accepted"
    assert "alice" in sample_proposal.rationale

    # Cannot re-accept once accepted
    with pytest.raises(ValueError, match="Cannot accept"):
        workflow.accept(sample_proposal)

    # Reject a fresh draft
    fresh_prop = CompositionProposal(
        proposal_id="prop_02",
        request_id="req_02",
        status="draft",
        adapted_code="",
        source_brick_ids=[],
    )
    workflow.reject(fresh_prop, reviewer="bob", reason="Missing tests.")
    assert fresh_prop.status == "rejected"
    assert any("Missing tests" in w for w in fresh_prop.warnings)


def test_export_allowlisting(tmp_path: Path, sample_proposal):
    allowed_dir = tmp_path / "allowed_exports"
    unauthorized_dir = tmp_path / "unauthorized"
    allowed_dir.mkdir()
    unauthorized_dir.mkdir()

    workflow = ProposalApprovalWorkflow(allowed_export_destinations=[allowed_dir])

    # 1. Export to allowed destination succeeds
    dest = allowed_dir / "my_project"
    written = workflow.export(sample_proposal, destination_dir=dest)
    assert len(written) == 1
    assert written[0].is_file()
    assert written[0].read_text(encoding="utf-8") == "def run(): return 42\n"

    # 2. Export to non-allowlisted destination raises PermissionError
    with pytest.raises(PermissionError, match="not permitted"):
        workflow.export(sample_proposal, destination_dir=unauthorized_dir)


def test_export_prevents_path_traversal(tmp_path: Path):
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    workflow = ProposalApprovalWorkflow(allowed_export_destinations=[allowed_dir])

    evil_art = ProposalArtifact.create("../../outside.py", "malicious content")
    proposal = CompositionProposal(
        proposal_id="evil_prop",
        request_id="req_evil",
        status="draft",
        adapted_code="",
        source_brick_ids=[],
        artifacts=[evil_art],
    )

    with pytest.raises(ValueError, match="traversal"):
        workflow.export(proposal, destination_dir=allowed_dir)

