"""Deterministic composition context builder assembling contracts, bundles, and constraints."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from brickforge.composition.models import CompositionConstraints, CompositionRequest, TargetEnvironment
from brickforge.contracts import BrickContract
from brickforge.extraction.bundler import ExtractionBundle, SourceBundler
from brickforge.extraction.manifest import ExtractionManifest, ManifestGenerator
from brickforge.storage.database import DatabaseManager


@dataclass
class CompositionContext:
    """Bounded, deterministic context package prepared for an external agent or model."""

    request_id: str
    target_environment: TargetEnvironment
    adaptation_instructions: str
    constraints: CompositionConstraints
    contracts: List[Dict[str, Any]] = field(default_factory=list)
    source_bundles: List[Dict[str, Any]] = field(default_factory=list)
    manifests: List[Dict[str, Any]] = field(default_factory=list)
    estimated_tokens: int = 0
    max_context_tokens: int = 16000
    is_truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert composition context to a serializable dictionary."""
        return {
            "request_id": self.request_id,
            "target_environment": asdict(self.target_environment),
            "adaptation_instructions": self.adaptation_instructions,
            "constraints": asdict(self.constraints),
            "contracts": list(self.contracts),
            "source_bundles": list(self.source_bundles),
            "manifests": list(self.manifests),
            "estimated_tokens": self.estimated_tokens,
            "max_context_tokens": self.max_context_tokens,
            "is_truncated": self.is_truncated,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize composition context to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_prompt_context(self) -> str:
        """Render deterministic prompt-ready text context for external models."""
        sections: List[str] = [
            "# Composition Context",
            f"**Request ID:** {self.request_id}",
            f"**Target Language:** {self.target_environment.language} ({self.target_environment.language_version})",
        ]
        if self.target_environment.framework:
            sections.append(f"**Target Framework:** {self.target_environment.framework}")

        sections.append("\n## Instructions")
        sections.append(self.adaptation_instructions)

        sections.append("\n## Constraints")
        sections.append(f"- Max external dependencies: {self.constraints.max_external_dependencies}")
        sections.append(f"- Disallow eval/exec: {self.constraints.disallow_eval_exec}")
        sections.append(f"- Pure function preferred: {self.constraints.pure_function_preferred}")
        for rule in self.constraints.custom_rules:
            sections.append(f"- Rule: {rule}")

        sections.append("\n## Selected Brick Contracts")
        for c in self.contracts:
            sections.append(
                f"### `{c.get('qualified_name', c.get('symbol_name'))}` ({c.get('kind')})\n"
                f"- Signature: `{c.get('signature')}`\n"
                f"- Location: {c.get('source_location', {}).get('file_path')}\n"
                f"- Docstring: {c.get('docstring') or 'None'}"
            )

        sections.append("\n## Source Bundles")
        for b in self.source_bundles:
            sections.append(f"### Source: `{b.get('symbol_name')}`\n```python\n{b.get('source_code', '').strip()}\n```")

        if self.is_truncated:
            sections.append("\n> [!WARNING] Context was truncated to stay within the configured token budget.")

        return "\n".join(sections) + "\n"


class CompositionContextBuilder:
    """Builds bounded context packages for external agents without calling external LLMs."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection], default_max_tokens: int = 16000):
        self.db = db
        self.default_max_tokens = default_max_tokens
        self.bundler = SourceBundler(db)
        self.manifest_gen = ManifestGenerator()

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    def build_context(
        self,
        request: CompositionRequest,
        max_tokens: Optional[int] = None,
    ) -> CompositionContext:
        """Deterministically assemble contracts, source bundles, and manifests into bounded context."""
        budget = max_tokens or self.default_max_tokens
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            contracts: List[Dict[str, Any]] = []
            bundles: List[Dict[str, Any]] = []
            manifests: List[Dict[str, Any]] = []

            total_chars = 0
            truncated = False

            for b_id in request.selected_brick_ids:
                # Query brick by string ID or numeric row_id
                cursor.execute(
                    """
                    SELECT cb.*, sf.relative_path
                    FROM code_bricks cb
                    JOIN source_files sf ON sf.row_id = cb.file_id
                    WHERE cb.id = ? OR cb.row_id = ?;
                    """,
                    (b_id, int(b_id) if b_id.isdigit() else -1),
                )
                brick_row = cursor.fetchone()
                if not brick_row:
                    continue

                b_row_dict = dict(brick_row)
                row_id = b_row_dict["row_id"]

                # Fetch dependencies and external packages for contract
                cursor.execute("SELECT * FROM brick_dependencies WHERE source_row_id = ?;", (row_id,))
                dep_rows = [dict(r) for r in cursor.fetchall()]
                cursor.execute("SELECT * FROM external_packages WHERE brick_row_id = ?;", (row_id,))
                pkg_rows = [dict(r) for r in cursor.fetchall()]

                # Build contract
                contract = BrickContract.from_database_records(
                    brick_row=b_row_dict,
                    file_path=b_row_dict["relative_path"],
                    dependencies=dep_rows,
                    packages=pkg_rows,
                )
                contract_dict = contract.to_dict()

                # Build bundle
                bundle = self.bundler.bundle_brick(brick_row_id=row_id, include_helpers=True)

                # Build manifest
                manifest = self.manifest_gen.generate(
                    target_brick_id=b_row_dict["id"],
                    bricks=[b_row_dict],
                    import_headers=bundle.import_headers,
                    unresolved_dependencies=bundle.unresolved_dependencies,
                    external_packages=bundle.external_packages,
                )

                # Check token budget (approximate 4 chars per token)
                bundle_payload = {
                    "brick_id": b_row_dict["id"],
                    "symbol_name": b_row_dict["symbol_name"],
                    "source_code": bundle.bundled_source,
                }
                added_chars = len(json.dumps(contract_dict)) + len(bundle.bundled_source)
                if (total_chars + added_chars) // 4 > budget:
                    truncated = True
                    break

                contracts.append(contract_dict)
                bundles.append(bundle_payload)
                manifests.append(manifest.to_dict())
                total_chars += added_chars

            estimated_tokens = max(1, total_chars // 4)

            return CompositionContext(
                request_id=request.request_id,
                target_environment=request.target_environment,
                adaptation_instructions=request.adaptation_instructions,
                constraints=request.constraints,
                contracts=contracts,
                source_bundles=bundles,
                manifests=manifests,
                estimated_tokens=estimated_tokens,
                max_context_tokens=budget,
                is_truncated=truncated,
            )
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

