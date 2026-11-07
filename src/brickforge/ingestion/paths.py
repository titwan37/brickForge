import os
from pathlib import Path

def safe_path_canonicalization(path: str, allowed_roots: list) -> Path:
    """
    Resolve symlinks and normalize paths before scanning. Ensure every candidate file remains inside a registered root.
    """
    canonical_path = Path(path).resolve()
    for root in allowed_roots:
        if canonical_path.is_relative_to(root):
            return canonical_path
    raise ValueError("Path traversal detected or unsafe root accessed")

# Example usage
allowed_roots = [Path("/safe/root1"), Path("/safe/root2")]
try:
    safe_path = safe_path_canonicalization("/unsafe/path", allowed_roots)
    print(f"Safe path: {safe_path}")
except ValueError as e:
    print(e)
