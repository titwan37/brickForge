"""Deterministic identity, provenance tracking, and deduplication rules for code bricks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union


def normalize_code_for_semantic_hash(source_code: str) -> str:
    """Normalize code formatting to compute a whitespace- and comment-agnostic semantic hash."""
    lines = []
    for line in source_code.splitlines():
        # Remove single-line comments (# ...)
        stripped = re.sub(r"#.*$", "", line).strip()
        if stripped:
            # Collapse multiple spaces
            lines.append(" ".join(stripped.split()))
    return "\n".join(lines)


def compute_semantic_hash(source_code: str, normalize: bool = True) -> str:
    """Compute SHA-256 hash of code content, optionally normalized to detect structural duplicates."""
    target = normalize_code_for_semantic_hash(source_code) if normalize else source_code
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


def compute_brick_id(
    repository_id: str,
    relative_path: str,
    qualified_name: str,
    kind: str,
    signature_hash: Optional[str] = None,
) -> str:
    """Generate a deterministic, globally unique brick ID preserving provenance."""
    norm_path = relative_path.replace("\\", "/").strip().lstrip("/")
    raw_key = f"{repository_id}:{norm_path}:{qualified_name}:{kind}"
    if signature_hash:
        raw_key += f":{signature_hash[:16]}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]
    return f"brick_{digest}"


@dataclass(frozen=True)
class BrickIdentity:
    """Immutable identity and provenance record for a code brick."""

    brick_id: str
    repository_id: str
    relative_path: str
    qualified_name: str
    kind: str
    content_hash: str
    semantic_hash: str
    signature_hash: Optional[str] = None

    @classmethod
    def from_symbol_and_provenance(
        cls,
        repository_id: str,
        relative_path: str,
        qualified_name: str,
        kind: str,
        source_code: str,
        signature_hash: Optional[str] = None,
    ) -> BrickIdentity:
        """Factory creating BrickIdentity with deterministic IDs and content hashes."""
        norm_path = relative_path.replace("\\", "/").strip().lstrip("/")
        b_id = compute_brick_id(repository_id, norm_path, qualified_name, kind, signature_hash)
        c_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        s_hash = compute_semantic_hash(source_code, normalize=True)
        return cls(
            brick_id=b_id,
            repository_id=repository_id,
            relative_path=norm_path,
            qualified_name=qualified_name,
            kind=kind,
            content_hash=c_hash,
            semantic_hash=s_hash,
            signature_hash=signature_hash,
        )


def is_same_provenance(a: BrickIdentity, b: BrickIdentity) -> bool:
    """Check if two brick identities share the exact repository, file, and symbol path."""
    return (
        a.repository_id == b.repository_id
        and a.relative_path == b.relative_path
        and a.qualified_name == b.qualified_name
        and a.kind == b.kind
    )


def are_exact_duplicates(a: BrickIdentity, b: BrickIdentity) -> bool:
    """Check if two bricks have identical source code content."""
    return a.content_hash == b.content_hash


def are_semantic_duplicates(a: BrickIdentity, b: BrickIdentity) -> bool:
    """Check if two bricks are structurally/semantically equivalent despite whitespace or comments."""
    return a.kind == b.kind and a.semantic_hash == b.semantic_hash


def group_duplicate_bricks(
    bricks: Sequence[BrickIdentity],
    semantic: bool = True,
) -> Dict[str, List[BrickIdentity]]:
    """Group bricks by content or semantic hash while keeping their individual provenance intact.

    Returns:
        Mapping of hash -> list of BrickIdentity instances sharing that code.
    """
    groups: Dict[str, List[BrickIdentity]] = {}
    for b in bricks:
        key = b.semantic_hash if semantic else b.content_hash
        groups.setdefault(key, []).append(b)
    return {k: v for k, v in groups.items() if len(v) > 1}


def detect_renamed_bricks(
    previous_bricks: Sequence[BrickIdentity],
    current_bricks: Sequence[BrickIdentity],
) -> List[Tuple[BrickIdentity, BrickIdentity]]:
    """Detect symbols that were moved or renamed within the same repository.

    Matches bricks that have the same repository_id, kind, and semantic_hash,
    but different relative_path or qualified_name.
    """
    renamed: List[Tuple[BrickIdentity, BrickIdentity]] = []
    # Index current by (repository_id, kind, semantic_hash)
    curr_map: Dict[Tuple[str, str, str], List[BrickIdentity]] = {}
    for cb in current_bricks:
        curr_map.setdefault((cb.repository_id, cb.kind, cb.semantic_hash), []).append(cb)

    for pb in previous_bricks:
        key = (pb.repository_id, pb.kind, pb.semantic_hash)
        candidates = curr_map.get(key, [])
        for cb in candidates:
            if not is_same_provenance(pb, cb):
                renamed.append((pb, cb))

    return renamed

