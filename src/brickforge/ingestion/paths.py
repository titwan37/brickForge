from pathlib import Path
from typing import Iterable, Union


def safe_path_canonicalization(path: Union[str, Path], allowed_roots: Iterable[Union[str, Path]]) -> Path:
    """Resolve symlinks and normalize paths before scanning.

    Ensure every candidate file remains inside an allowed registered root.
    Rejects path traversal or paths outside allowed roots.
    """
    canonical_path = Path(path).resolve()
    for root in allowed_roots:
        root_path = Path(root)
        try:
            if canonical_path.is_relative_to(root_path):
                return canonical_path
        except (ValueError, AttributeError):
            continue
    raise ValueError("Path traversal detected or unsafe root accessed")

