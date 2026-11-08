"""Configurable ignore and inclusion rules for file ingestion."""

from __future__ import annotations

import fnmatch
import os
import re
from typing import List, Optional, Set, Tuple

DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".git/*",
    ".gitignore",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    ".delta",
    ".delta/*",
    "site-packages",
    "site-packages/*",
    "__pycache__",
    "__pycache__/*",
    "*.pyc",
    "node_modules",
    "node_modules/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    "target",
    "target/*",
    ".pytest_cache",
    ".pytest_cache/*",
    ".mypy_cache",
    ".mypy_cache/*",
    ".ruff_cache",
    ".ruff_cache/*",
    ".env",
    ".env.*",
    "desktop.ini",
    "Thumbs.db",
    ".DS_Store",
]

COMMON_IGNORED_DIR_NAMES: Set[str] = {
    ".git",
    ".venv",
    "venv",
    ".conda",
    "miniconda3",
    "anaconda3",
    ".delta",
    "site-packages",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "htmlcov",
    "dist",
    "build",
    "target",
    ".vs",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    ".continue",
    ".continue-config",
    ".agents",
    "data",
}


class IgnoreRules:
    """Configurable ignore and inclusion rules for file ingestion with high-performance O(1) matching."""

    def __init__(self, config_path: Optional[str] = None, use_defaults: bool = True):
        self.config_path = config_path
        self.use_defaults = use_defaults
        self.ignore_patterns: List[str] = self.load_ignore_patterns()
        self._cached_pattern_tuple: Optional[Tuple[str, ...]] = None
        self._exact_names: Set[str] = set()
        self._exact_exts: Set[str] = set()
        self._complex_globs: List[str] = []

    def load_ignore_patterns(self) -> List[str]:
        patterns: List[str] = []
        if self.use_defaults:
            patterns.extend(DEFAULT_IGNORE_PATTERNS)

        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as file:
                for line in file:
                    pattern = line.strip()
                    if pattern and not pattern.startswith("#"):
                        patterns.append(pattern)
        return patterns

    def _ensure_index(self) -> None:
        """Dynamically build / synchronize fast lookup sets if patterns changed."""
        current_tuple = tuple(self.ignore_patterns) if hasattr(self, "ignore_patterns") and self.ignore_patterns else ()
        if current_tuple == getattr(self, "_cached_pattern_tuple", None) and hasattr(self, "_exact_names"):
            return

        self._exact_names = set(COMMON_IGNORED_DIR_NAMES)
        self._exact_exts = set()
        self._complex_globs = []

        for p in current_tuple:
            cleaned = str(p).strip().replace("\\", "/")
            if not cleaned or cleaned.startswith("#"):
                continue

            # Strip leading/trailing glob wrappers: **/foo/** -> foo
            bare = cleaned
            while bare.startswith("**/") or bare.startswith("./"):
                bare = bare[3:] if bare.startswith("**/") else bare[2:]
            while bare.endswith("/**") or bare.endswith("/*"):
                bare = bare[:-3] if bare.endswith("/**") else bare[:-2]
            bare = bare.strip("/")

            # Check if this is an extension pattern: e.g. *.pyc, *.db
            if bare.startswith("*.") and "*" not in bare[2:] and "?" not in bare and "/" not in bare:
                self._exact_exts.add(bare[1:].lower())
                continue

            # Check if this is an exact directory or file name
            if "*" not in bare and "?" not in bare and "[" not in bare:
                self._exact_names.add(bare.lower())
                continue

            self._complex_globs.append(cleaned)

        self._cached_pattern_tuple = current_tuple

    def is_ignored(self, path: str) -> bool:
        """Check if a path matches any ignore pattern (optimized O(1) fast-path)."""
        self._ensure_index()

        norm_path = path.replace("\\", "/").strip("/")
        parts = norm_path.split("/")

        # 1. Fast O(1) set lookup on any path segment (directory or filename)
        for part in parts:
            if part.lower() in self._exact_names:
                return True

        # 2. Fast O(1) set lookup on file extension
        base_name = parts[-1] if parts else norm_path
        _, ext = os.path.splitext(base_name)
        if ext and ext.lower() in self._exact_exts:
            return True

        # 3. Fallback for wildcards / globs
        if self._complex_globs:
            for pattern in self._complex_globs:
                clean_pattern = pattern.rstrip("/")
                if fnmatch.fnmatch(norm_path, clean_pattern) or fnmatch.fnmatch(base_name, clean_pattern):
                    return True
                if any(fnmatch.fnmatch(part, clean_pattern) for part in parts):
                    return True

        return False

    def is_dir_ignored(self, dirname: str, parent_rel_path: Optional[str] = None) -> bool:
        """Fast-path check to determine if a directory should be pruned during traversal."""
        self._ensure_index()

        dir_lower = dirname.lower()
        if dir_lower in self._exact_names:
            return True

        if parent_rel_path:
            full_rel = f"{parent_rel_path}/{dirname}".replace("\\", "/")
        else:
            full_rel = dirname

        return self.is_ignored(full_rel)
