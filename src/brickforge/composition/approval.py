"""Proposal approval, rejection, and destination-allowlisted export workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from brickforge.composition.models import CompositionProposal, ProposalArtifact


class ProposalApprovalWorkflow:
    """Manages review lifecycle transitions and secure export for composition proposals."""

    def __init__(self, allowed_export_destinations: Optional[Sequence[Union[str, Path]]] = None):
        self.allowed_destinations = [
            Path(d).resolve() for d in (allowed_export_destinations or ())
        ]

    def accept(
        self,
        proposal: CompositionProposal,
        reviewer: str = "user",
        notes: str = "",
    ) -> CompositionProposal:
        """Approve and accept a draft composition proposal."""
        if proposal.status not in ("draft", "review"):
            raise ValueError(f"Cannot accept proposal in status '{proposal.status}'.")

        proposal.status = "accepted"
        if notes:
            proposal.rationale += f" [Accepted by {reviewer}: {notes}]"
        return proposal

    def reject(
        self,
        proposal: CompositionProposal,
        reviewer: str = "user",
        reason: str = "",
    ) -> CompositionProposal:
        """Reject a draft composition proposal."""
        if proposal.status not in ("draft", "review"):
            raise ValueError(f"Cannot reject proposal in status '{proposal.status}'.")

        proposal.status = "rejected"
        if reason:
            proposal.warnings.append(f"Rejected by {reviewer}: {reason}")
        return proposal

    def export(
        self,
        proposal: CompositionProposal,
        destination_dir: Union[str, Path],
        allowlist_override: Optional[Sequence[Union[str, Path]]] = None,
    ) -> List[Path]:
        """Export proposal artifacts to a verified destination path.

        Enforces strict destination allowlisting to prevent accidental overwrites
        of existing source catalog files or unauthorized directory writes.
        """
        dest_path = Path(destination_dir).resolve()
        effective_allowlist = (
            [Path(d).resolve() for d in allowlist_override]
            if allowlist_override is not None
            else self.allowed_destinations
        )

        # 1. Enforce destination allowlist
        is_allowed = False
        for allowed in effective_allowlist:
            try:
                # True if dest_path is equal to allowed or is a subdirectory of allowed
                if dest_path == allowed or dest_path.is_relative_to(allowed):
                    is_allowed = True
                    break
            except AttributeError:
                # Fallback for Python versions without is_relative_to
                if dest_path == allowed or str(dest_path).startswith(str(allowed)):
                    is_allowed = True
                    break

        if not is_allowed:
            raise PermissionError(
                f"Export destination '{dest_path}' is not permitted. "
                f"Destination must be inside an allowlisted path: {[str(p) for p in effective_allowlist]}"
            )

        # 2. Write artifacts safely
        dest_path.mkdir(parents=True, exist_ok=True)
        written_paths: List[Path] = []

        # If proposal has specific artifacts, write them
        if proposal.artifacts:
            for art in proposal.artifacts:
                target_file = (dest_path / art.file_path).resolve()
                # Prevent directory traversal outside dest_path
                if not (target_file == dest_path or target_file.is_relative_to(dest_path)):
                    raise ValueError(f"Artifact path traversal attempted: {art.file_path}")

                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(art.content, encoding="utf-8")
                written_paths.append(target_file)
        else:
            # Export adapted code as main artifact
            main_file = dest_path / "adapted_solution.py"
            main_file.write_text(proposal.adapted_code, encoding="utf-8")
            written_paths.append(main_file)

        return written_paths

