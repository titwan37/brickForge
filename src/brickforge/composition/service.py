"""Composition and adaptation proposal orchestration service."""

from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from brickforge.composition.context import CompositionContext, CompositionContextBuilder
from brickforge.composition.models import CompositionProposal, CompositionRequest, ProposalArtifact
from brickforge.composition.provider import BaseCompositionProvider, MockCompositionProvider, ProviderMetadata
from brickforge.storage.database import DatabaseManager


@dataclass
class ProposalResult:
    """Rich workflow result containing the proposal, unified diffs, and provider metadata."""

    proposal: CompositionProposal
    diff: str
    provider_metadata: ProviderMetadata
    original_source: str
    proposed_source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "diff": self.diff,
            "provider_metadata": {
                "provider_name": self.provider_metadata.provider_name,
                "model_id": self.provider_metadata.model_id,
            },
            "original_source": self.original_source,
            "proposed_source": self.proposed_source,
        }


class CompositionService:
    """Orchestrates end-to-end code adaptation proposals, diffing, and provider provenance."""

    def __init__(
        self,
        db: Union[DatabaseManager, sqlite3.Connection],
        default_provider: Optional[BaseCompositionProvider] = None,
        context_builder: Optional[CompositionContextBuilder] = None,
    ):
        self.db = db
        self.provider = default_provider or MockCompositionProvider()
        self.context_builder = context_builder or CompositionContextBuilder(db)

    def create_proposal(
        self,
        request: CompositionRequest,
        provider: Optional[BaseCompositionProvider] = None,
    ) -> ProposalResult:
        """Execute composition workflow: build context, invoke provider, and compute diffs."""
        active_provider = provider or self.provider

        # 1. Build bounded context
        context: CompositionContext = self.context_builder.build_context(request)

        # 2. Extract original concatenated source for diffing
        orig_sources = [b.get("source_code", "").strip() for b in context.source_bundles]
        original_combined = "\n\n".join(orig_sources)

        # 3. Invoke provider to produce proposal
        proposal: CompositionProposal = active_provider.generate_proposal(context)

        # 4. Compute unified diff
        diff_lines = list(
            difflib.unified_diff(
                original_combined.splitlines(keepends=True),
                proposal.adapted_code.splitlines(keepends=True),
                fromfile="original_bricks.py",
                tofile="proposed_adaptation.py",
            )
        )
        unified_diff = "".join(diff_lines)

        # 5. Record provider metadata
        meta = ProviderMetadata(
            provider_name=active_provider.provider_name,
            model_id=active_provider.model_id,
        )

        return ProposalResult(
            proposal=proposal,
            diff=unified_diff,
            provider_metadata=meta,
            original_source=original_combined,
            proposed_source=proposal.adapted_code,
        )

