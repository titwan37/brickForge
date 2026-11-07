import os
from datetime import datetime


def walk_registered_roots(roots):
    """Walk registered roots and yield eligible source files with metadata."""
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            for filename in filenames:
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
        ".ts": "typescript",
        ".tsx": "typescript",
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
        ".css": "css",
        ".json": "json",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "shell",
        ".ps1": "powershell",
    }
    return mapping.get(extension, "unknown")

