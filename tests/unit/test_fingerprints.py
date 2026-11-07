"""Unit tests for content hashing and file fingerprinting."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from brickforge.ingestion.fingerprints import (
    FileFingerprint,
    compute_bytes_hash,
    compute_content_hash,
    compute_file_id,
    generate_fingerprint,
    has_content_changed,
    normalize_relative_path,
    quick_stat_matches,
)


class TestFingerprints:
    """Tests for file fingerprinting and content hashing."""

    def test_normalize_relative_path(self):
        assert normalize_relative_path(r"foo\bar\baz.py") == "foo/bar/baz.py"
        assert normalize_relative_path("/foo/bar/baz.py") == "foo/bar/baz.py"
        assert normalize_relative_path(Path("foo/bar/baz.py")) == "foo/bar/baz.py"

    def test_compute_file_id_deterministic(self):
        id1 = compute_file_id("repo-123", "src/main.py")
        id2 = compute_file_id("repo-123", r"src\main.py")
        assert id1 == id2
        assert len(id1) == 64  # SHA-256 hex string

        # Different repo or path yields different ID
        id_diff_repo = compute_file_id("repo-456", "src/main.py")
        id_diff_path = compute_file_id("repo-123", "src/other.py")
        assert id1 != id_diff_repo
        assert id1 != id_diff_path

    def test_compute_bytes_hash(self):
        data = b"hello brickforge"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_bytes_hash(data) == expected

    def test_compute_content_hash(self, tmp_path: Path):
        file = tmp_path / "test.py"
        content = b"print('hello world')\n" * 100
        file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = compute_content_hash(file, chunk_size=32)

        assert actual_hash == expected_hash

    def test_compute_content_hash_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")

        expected = hashlib.sha256(b"").hexdigest()
        assert compute_content_hash(empty_file) == expected

    def test_generate_fingerprint(self, tmp_path: Path):
        file = tmp_path / "example.py"
        content = b"def add(a, b): return a + b\n"
        file.write_bytes(content)

        fp = generate_fingerprint(file, repo_id="repo-1", relative_path="sub/example.py")

        assert isinstance(fp, FileFingerprint)
        assert fp.file_id == compute_file_id("repo-1", "sub/example.py")
        assert fp.file_hash == hashlib.sha256(content).hexdigest()
        assert fp.byte_size == len(content)
        assert fp.relative_path == "sub/example.py"
        assert fp.modified_ns > 0

    def test_generate_fingerprint_auto_relative_path(self, tmp_path: Path):
        file = tmp_path / "auto.py"
        file.write_bytes(b"data")

        fp = generate_fingerprint(file, repo_id="repo-1")
        assert fp.relative_path == "auto.py"
        assert fp.byte_size == 4

    def test_has_content_changed(self):
        hash1 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        hash2 = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"

        # Content changes when previous hash is None or different
        assert has_content_changed(hash1, None) is True
        assert has_content_changed(hash1, "") is True
        assert has_content_changed(hash1, hash2) is True

        # Unchanged when hash is identical (case-insensitive)
        assert has_content_changed(hash1, hash1) is False
        assert has_content_changed(hash1, hash1.upper()) is False

    def test_quick_stat_matches(self):
        assert quick_stat_matches(100, 100, 1000, 1000) is True
        assert quick_stat_matches(100, 200, 1000, 1000) is False
        assert quick_stat_matches(100, 100, 1000, 2000) is False
        assert quick_stat_matches(100, None, 1000, 1000) is False
        assert quick_stat_matches(100, 100, 1000, None) is False

    def test_nonexistent_file_raises(self, tmp_path: Path):
        missing = tmp_path / "missing.py"
        with pytest.raises(FileNotFoundError):
            compute_content_hash(missing)

        with pytest.raises(FileNotFoundError):
            generate_fingerprint(missing, repo_id="repo-1")

