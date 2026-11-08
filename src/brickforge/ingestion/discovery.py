import os
from datetime import datetime

BINARY_MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp", ".tiff",
    ".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".aiff",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".msi",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".whl", ".pyc", ".pyo", ".pyd", ".class",
    ".o", ".obj", ".rlib", ".rmeta", ".d", ".timestamp",
    ".db", ".sqlite", ".sqlite3",
    ".dat", ".settings", ".suo", ".user", ".cache", ".log", ".lock",
    ".sdf", ".ipch", ".pdb", ".idb", ".tlog",
}

IGNORED_EXACT_FILENAMES = {
    "desktop.ini",
    "thumbs.db",
    ".ds_store",
}


def walk_registered_roots(roots, ignore_rules=None):
    """Walk registered roots and yield eligible source files with metadata.

    Prunes ignored directories in-place during os.walk to avoid descending into
    giant vendor, git, or build directories (.git, node_modules, .venv, bin, obj).
    """
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # Prune directory recursion in-place
            if ignore_rules is not None:
                rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
                parent_prefix = None if rel_dir == "." else rel_dir
                dirnames[:] = [
                    d for d in dirnames
                    if not (hasattr(ignore_rules, "is_dir_ignored") and ignore_rules.is_dir_ignored(d, parent_prefix))
                ]

            for filename in filenames:
                lower_name = filename.lower()
                if lower_name in IGNORED_EXACT_FILENAMES:
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext in BINARY_MEDIA_EXTENSIONS:
                    continue
                if filename.startswith(root + os.sep) or filename.startswith(root + "/"):
                    file_path = filename
                elif os.path.isabs(filename):
                    file_path = filename
                else:
                    file_path = os.path.join(dirpath, filename)

                if os.path.exists(file_path) and not os.path.isfile(file_path):
                    continue

                rel_path = os.path.relpath(file_path, root).replace("\\", "/")

                try:
                    file_size = os.path.getsize(file_path)
                except OSError:
                    file_size = 0

                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                except OSError:
                    mtime = datetime.now().isoformat()

                yield {
                    "relative_path": rel_path,
                    "language_hint": get_language_hint(filename),
                    "file_size": file_size,
                    "modification_time": mtime,
                }


def get_language_hint(filename):
    """Determine file language based on extension."""
    extension = os.path.splitext(filename)[1].lower()
    mapping = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript-react",
        ".java": "java",
        ".go": "go",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".rs": "rust",
        ".html": "html",
        ".htm": "html",
        ".xhtml": "html",
        ".css": "css",
        ".scss": "css",
        ".sass": "css",
        ".less": "css",
        ".json": "json",
        ".xml": "xml",
        ".xaml": "xml",
        ".csproj": "xml",
        ".props": "xml",
        ".targets": "xml",
        ".config": "xml",
        ".resx": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "shell",
        ".bash": "shell",
        ".ps1": "powershell",
    }
    return mapping.get(extension, "unknown")

