"""Content hashing and file fingerprinting for BrickForge.

Provides authoritative SHA-256 content hashing, stable file identity derivation,
and fingerprint metadata for incremental change detection.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB


@dataclass(frozen=True)
class FileFingerprint:
    """Fingerprint capturing file identity, content hash, and filesystem hints."""

    file_id: str
    file_hash: str
    byte_size: int
    modified_ns: int
    relative_path: str


def normalize_relative_path(path: Union[str, Path]) -> str:
    """Normalize relative path to forward slashes without leading slashes."""
    p_str = str(path).replace("\\", "/").strip()
    return p_str.lstrip("/")


def compute_file_id(repo_id: str, relative_path: Union[str, Path]) -> str:
    """Compute a deterministic, stable file ID from repository ID and normalized relative path.

    Uses SHA-256 digest of 'repo_id:normalized_relative_path'.
    """
    norm_path = normalize_relative_path(relative_path)
    combined = f"{repo_id}:{norm_path}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def compute_content_hash(
    file_path: Union[str, Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute SHA-256 hex digest of file contents by streaming chunks."""
    hasher = hashlib.sha256()
    path = Path(file_path)

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_bytes_hash(data: bytes) -> str:
    """Compute SHA-256 hex digest of in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def generate_fingerprint(
    file_path: Union[str, Path],
    repo_id: str,
    relative_path: Optional[Union[str, Path]] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> FileFingerprint:
    """Generate a complete FileFingerprint for a candidate source file.

    Computes SHA-256 content hash, resolves size and mtime_ns from stat,
    and derives the stable deterministic file ID.
    """
    path = Path(file_path)
    stat_result = os.stat(path)

    rel_path_str = (
        normalize_relative_path(relative_path)
        if relative_path is not None
        else normalize_relative_path(path.name)
    )

    file_id = compute_file_id(repo_id, rel_path_str)
    file_hash = compute_content_hash(path, chunk_size=chunk_size)

    return FileFingerprint(
        file_id=file_id,
        file_hash=file_hash,
        byte_size=stat_result.st_size,
        modified_ns=getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1e9)),
        relative_path=rel_path_str,
    )


def has_content_changed(current_hash: str, recorded_hash: Optional[str]) -> bool:
    """Authoritative change test based on SHA-256 content hash."""
    if not recorded_hash:
        return True
    return current_hash.lower() != recorded_hash.lower()


def quick_stat_matches(
    current_size: int,
    recorded_size: Optional[int],
    current_mtime_ns: int,
    recorded_mtime_ns: Optional[int],
) -> bool:
    """Check if file size and mtime match recorded state (fast optimization hint)."""
    if recorded_size is None or recorded_mtime_ns is None:
        return False
    return current_size == recorded_size and current_mtime_ns == recorded_mtime_ns

