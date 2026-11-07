"""Extraction manifest and provenance report generator for code brick bundles."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class ManifestBrickItem:
    """Provenance and hash descriptor for a single brick inside an extraction manifest."""

    brick_id: str
    symbol_name: str
    qualified_name: str
    kind: str
    source_file: str
    source_hash: str
    is_target: bool = False


@dataclass
class ExtractionManifest:
    """Complete provenance and transformation manifest for an extracted code bundle."""

    manifest_id: str
    created_at: str
    target_brick_id: str
    selected_bricks: List[ManifestBrickItem] = field(default_factory=list)
    included_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    source_hashes: Dict[str, str] = field(default_factory=dict)
    imports: List[str] = field(default_factory=list)
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_dependencies: List[str] = field(default_factory=list)
    external_packages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to serializable dictionary."""
        return {
            "manifest_id": self.manifest_id,
            "created_at": self.created_at,
            "target_brick_id": self.target_brick_id,
            "selected_bricks": [asdict(b) for b in self.selected_bricks],
            "included_dependencies": list(self.included_dependencies),
            "source_files": list(self.source_files),
            "source_hashes": dict(self.source_hashes),
            "imports": list(self.imports),
            "transformations": list(self.transformations),
            "unresolved_dependencies": list(self.unresolved_dependencies),
            "external_packages": list(self.external_packages),
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize manifest to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExtractionManifest:
        """Construct manifest instance from dictionary data."""
        bricks = [
            ManifestBrickItem(
                brick_id=b.get("brick_id", ""),
                symbol_name=b.get("symbol_name", ""),
                qualified_name=b.get("qualified_name", ""),
                kind=b.get("kind", "function"),
                source_file=b.get("source_file", ""),
                source_hash=b.get("source_hash", ""),
                is_target=bool(b.get("is_target", False)),
            )
            for b in data.get("selected_bricks", [])
        ]
        return cls(
            manifest_id=data.get("manifest_id", ""),
            created_at=data.get("created_at", ""),
            target_brick_id=data.get("target_brick_id", ""),
            selected_bricks=bricks,
            included_dependencies=data.get("included_dependencies", []),
            source_files=data.get("source_files", []),
            source_hashes=data.get("source_hashes", {}),
            imports=data.get("imports", []),
            transformations=data.get("transformations", []),
            unresolved_dependencies=data.get("unresolved_dependencies", []),
            external_packages=data.get("external_packages", []),
        )


class ManifestGenerator:
    """Creates structured provenance manifests for extraction bundles."""

    def generate(
        self,
        target_brick_id: str,
        bricks: Sequence[Dict[str, Any]],
        import_headers: Sequence[str],
        transformations: Optional[Sequence[Dict[str, Any]]] = None,
        unresolved_dependencies: Optional[Sequence[str]] = None,
        external_packages: Optional[Sequence[str]] = None,
        dependencies: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> ExtractionManifest:
        """Synthesize a complete provenance report and manifest."""
        manifest_id = f"man_{uuid.uuid4().hex[:16]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        selected_bricks: List[ManifestBrickItem] = []
        source_files: Set[str] = set()
        source_hashes: Dict[str, str] = {}

        for b in bricks:
            b_id = str(b.get("id") or b.get("brick_id", ""))
            s_file = str(b.get("relative_path") or b.get("file_path", ""))
            s_hash = str(b.get("source_hash", ""))

            source_files.add(s_file)
            source_hashes[b_id] = s_hash

            selected_bricks.append(
                ManifestBrickItem(
                    brick_id=b_id,
                    symbol_name=b.get("symbol_name", ""),
                    qualified_name=b.get("qualified_name", ""),
                    kind=b.get("kind", "function"),
                    source_file=s_file,
                    source_hash=s_hash,
                    is_target=(b_id == target_brick_id),
                )
            )

        return ExtractionManifest(
            manifest_id=manifest_id,
            created_at=now_iso,
            target_brick_id=target_brick_id,
            selected_bricks=selected_bricks,
            included_dependencies=list(dependencies or []),
            source_files=sorted(source_files),
            source_hashes=source_hashes,
            imports=list(import_headers),
            transformations=list(transformations or []),
            unresolved_dependencies=list(unresolved_dependencies or []),
            external_packages=sorted(set(external_packages or ())),
        )

