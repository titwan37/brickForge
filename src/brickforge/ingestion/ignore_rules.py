import fnmatch
import os
from typing import List, Optional

DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".git/*",
    ".gitignore",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    "__pycache__",
    "__pycache__/*",
    "*.pyc",
    "node_modules",
    "node_modules/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    ".pytest_cache",
    ".pytest_cache/*",
    ".env",
    ".env.*",
]


class IgnoreRules:
    """Configurable ignore and inclusion rules for file ingestion."""

    def __init__(self, config_path: Optional[str] = None, use_defaults: bool = True):
        self.config_path = config_path
        self.use_defaults = use_defaults
        self.ignore_patterns = self.load_ignore_patterns()

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

    def is_ignored(self, path: str) -> bool:
        """Check if a path matches any ignore pattern."""
        norm_path = path.replace("\\", "/")
        base_name = os.path.basename(norm_path)
        parts = norm_path.split("/")

        for pattern in self.ignore_patterns:
            clean_pattern = pattern.rstrip("/")
            if fnmatch.fnmatch(norm_path, clean_pattern) or fnmatch.fnmatch(base_name, clean_pattern):
                return True
            if any(fnmatch.fnmatch(part, clean_pattern) for part in parts):
                return True
        return False

