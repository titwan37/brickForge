"""Project-level aggregation and AI intent synthesis for BrickForge Catalog."""

from __future__ import annotations

import ast
from collections import Counter
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_MODEL = "lfm3:latest"
FALLBACK_OLLAMA_MODELS = [
    "lfm3:latest",
    "llama3.2:3b",
    "qwen2.5-coder:7b",
    "qwen2.5:7b",
    "mistral-7b:latest",
    "jetelain/Qwen3.5-9B:latest",
]

# Circuit breaker state so we don't wait 4.5s x N projects when Ollama is offline/stalled
_OLLAMA_CIRCUIT_OPEN: bool = False
_OLLAMA_CONSECUTIVE_FAILURES: int = 0
MAX_OLLAMA_FAILURES: int = 2

# Console telemetry toggle (can be disabled via env var BRICKFORGE_QUIET=1)
VERBOSE_CONSOLE: bool = os.environ.get("BRICKFORGE_QUIET", "0") != "1"


def _log_perf(msg: str, end: str = "\n") -> None:
    """Print immediate, unbuffered performance telemetry to stdout."""
    if VERBOSE_CONSOLE:
        timestamp = time.strftime("%H:%M:%S")
        sys.stdout.write(f"[BrickForge {timestamp}] {msg}{end}")
        sys.stdout.flush()


# Directories and extensions for the heavy-source code scanner
IGNORED_DIRS: Set[str] = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__",
    "node_modules", "target", "dist", "build", "out", ".next",
    ".nuxt", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "vendor", "bin", "obj", "coverage", "site-packages", ".idea", ".vscode",
    "assets", "models", "weights", "checkpoints", "datasets", "logs"
}

SOURCE_CODE_EXTENSIONS: Set[str] = {
    ".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".cs", ".cpp", ".hpp", ".cc", ".c", ".h", ".go", ".java",
    ".ps1", ".sh", ".bat", ".sql", ".r", ".vue", ".svelte", ".lua", ".rb", ".php"
}

# Loose root files with these extensions are artifacts/configs, NOT standalone software projects
NON_PROJECT_ROOT_EXTENSIONS: Set[str] = {
    ".log", ".aux", ".out", ".toc", ".lof", ".lot", ".synctex", ".fls", ".fdb_latexmk",
    ".ini", ".csv", ".tsv", ".url", ".lnk", ".bak", ".tmp", ".temp", ".swp",
    ".lock", ".txt", ".md", ".markdown", ".rst", ".tex", ".pdf", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".webp", ".mp3", ".mp4", ".wav", ".ogg", ".zip", ".tar", ".gz", ".7z",
    ".rar", ".db", ".sqlite", ".sqlite3", ".wal", ".shm", ".css", ".scss", ".less",
    ".html", ".htm", ".xml", ".yaml", ".yml", ".toml", ".json", ".code-workspace",
    ".lst"
}

IGNORED_PROJECT_NAMES: Set[str] = {
    ".git", ".github", ".gitlab", ".vscode", ".idea", ".vs",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "__pycache__",
    "node_modules", "site-packages", "venv", ".venv", "env",
    ".gradio", ".continue", ".cache", ".delta", ".firebaserc", ".blackboxrules",
    "cache", "output", "temp_output", "null", "profiles", "dist", "build", "out"
}

BOILERPLATE_SYMBOLS: Set[str] = {
    "__init__", "__str__", "__repr__", "__eq__", "__hash__", "__len__",
    "__iter__", "__next__", "__enter__", "__exit__", "main", "new", "default",
    "from", "into", "clone", "fmt", "drop", "deref", "constructor", "render",
    "ngoninit", "ngondestroy", "tostring", "gethashcode", "equals", "dispose",
    "setup", "teardown", "test", "run", "start", "stop", "init", "get", "set"
}

STOP_WORDS: Set[str] = {
    "the", "and", "for", "with", "from", "into", "this", "that", "data",
    "item", "items", "value", "values", "info", "list", "dict", "array",
    "object", "string", "number", "bool", "boolean", "result", "response",
    "request", "error", "none", "null", "true", "false", "self", "args",
    "kwargs", "param", "params", "config", "options", "helper", "utils",
    "util", "base", "abstract", "impl", "internal", "private", "public",
    "handle", "handler", "process", "manager", "service", "class", "func",
    "function", "method", "module", "file", "path", "name", "type", "id"
}


def is_valid_project_candidate(project_name: str) -> bool:
    """Filter out loose root config/log/document files and hidden cache folders."""
    if not project_name or project_name in IGNORED_PROJECT_NAMES:
        return False
    lower = project_name.lower().strip()
    if lower in IGNORED_PROJECT_NAMES:
        return False
    # Ignore hidden dotfiles/dotfolders unless explicitly whitelisted
    if lower.startswith(".") and lower not in (".agents", ".continue-config"):
        return False
    # If the top-level entry has a file extension, only allow actual standalone scripts (.py, .ps1, .rs, .js, etc.)
    ext = Path(lower).suffix
    if ext:
        if ext in NON_PROJECT_ROOT_EXTENSIONS:
            return False
        if ext not in SOURCE_CODE_EXTENSIONS:
            return False
    return True


def get_summaries_cache_path() -> Path:
    """Return canonical path to persisted project summaries JSON."""
    p = Path("data/project_summaries.json")
    if p.exists():
        return p
    alt = Path(__file__).resolve().parent.parent.parent.parent / "data" / "project_summaries.json"
    return alt


def load_persisted_summaries() -> Dict[str, str]:
    """Load cached project summaries from disk."""
    cache_path = get_summaries_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.debug("Failed to read project summaries cache: %s", e)
    return {}


_INTENT_CACHE: Dict[str, str] = load_persisted_summaries()


def save_persisted_summary(cache_key: str, summary: str, flush_disk: bool = True) -> None:
    """Save an AI project summary to in-memory cache and optionally flush to persistent JSON."""
    if isinstance(summary, tuple):
        summary = summary[0]
    _INTENT_CACHE[cache_key] = summary
    if flush_disk:
        flush_summaries_cache()


def flush_summaries_cache() -> None:
    """Write in-memory summary cache to disk in a single atomic operation."""
    cache_path = get_summaries_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(_INTENT_CACHE, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug("Failed to write project summaries cache: %s", e)


def detect_file_language(relative_path: str) -> Tuple[str, str]:
    """Return normalized language name and short code (e.g., ('python', 'py'))."""
    lower = relative_path.lower()
    if lower.endswith(".py"):
        return "python", "py"
    if lower.endswith(".tsx"):
        return "typescript-react", "tsx"
    if lower.endswith(".ts"):
        return "typescript", "ts"
    if lower.endswith(".jsx"):
        return "javascript-react", "jsx"
    if lower.endswith((".js", ".mjs", ".cjs")):
        return "javascript", "js"
    if lower.endswith(".cs"):
        return "csharp", "cs"
    if lower.endswith(".rs"):
        return "rust", "rs"
    if lower.endswith((".cpp", ".hpp", ".cc", ".cxx")):
        return "cpp", "cpp"
    if lower.endswith((".c", ".h")):
        return "c", "c"
    if lower.endswith(".go"):
        return "go", "go"
    if lower.endswith(".java"):
        return "java", "java"
    if lower.endswith(".ps1"):
        return "powershell", "ps1"
    if lower.endswith((".sh", ".bash")):
        return "shell", "sh"
    if lower.endswith(".sql"):
        return "sql", "sql"
    if lower.endswith(".json"):
        return "json", "json"
    if lower.endswith((".md", ".markdown")):
        return "markdown", "md"
    return "unknown", "txt"


def normalize_language_badge(lang: Optional[str], path: Optional[str] = None) -> str:
    """Return a clean, unique short code badge (py, ts, tsx, js, cs, rs, etc.)."""
    if path:
        _, ext = detect_file_language(path)
        if ext != "txt":
            return ext

    if not lang:
        return "py"
    l_lower = lang.lower().strip()
    if "python" in l_lower or l_lower == "py":
        return "py"
    if "react" in l_lower or "tsx" in l_lower:
        return "tsx"
    if "typescript" in l_lower or l_lower == "ts":
        return "ts"
    if "jsx" in l_lower:
        return "jsx"
    if "javascript" in l_lower or l_lower == "js":
        return "js"
    if "csharp" in l_lower or "c#" in l_lower or l_lower == "cs":
        return "cs"
    if "rust" in l_lower or "rs" in l_lower:
        return "rs"
    if "cpp" in l_lower or "c++" in l_lower:
        return "cpp"
    if l_lower == "c":
        return "c"
    if "go" in l_lower:
        return "go"
    if "java" in l_lower:
        return "java"
    return l_lower[:4]


def strip_html_and_badges(text: Union[str, Tuple[str, ...], None]) -> str:
    """Strip all HTML tags, images, badge shields, language switchers, and formatting noise."""
    if not text:
        return ""
    # Defensive guard in case a caller passes a (summary, tag) tuple
    if isinstance(text, tuple):
        text = str(text[0]) if text else ""

    text = (
        text.replace("&nbsp;", " ")
        .replace("&middot;", " · ")
        .replace("&bull;", " • ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(
        r"<(script|style|picture|video|audio)[^>]*>.*?</\1>",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)
    text = re.sub(r"\[\s*!\[[^\]]*\]\([^\)]*\)\s*\]\([^\)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)

    cleaned_lines: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s_lower = s.lower()
        if any(
            w in s_lower
            for w in ("english", "türkçe", "deutsch", "français", "español", "русский", "日本語", "العربية", "中文")
        ) and ("|" in s or "·" in s or "/" in s):
            continue
        if ("·" in s or "|" in s or "•" in s) and len(
            re.findall(
                r"(discord|telegram|twitter|website|github|docs|pypi|license|quickstart|catalog|playground|product hunt|npm)",
                s_lower,
            )
        ) >= 2:
            continue
        if re.match(r"^[-=_*#]{3,}$", s):
            continue
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^>\s*", "", s)
        s = re.sub(r"[*_`]", "", s)
        s = " ".join(s.split())
        if len(s) > 3:
            cleaned_lines.append(s)

    return "\n".join(cleaned_lines)


def split_identifier_tokens(identifier: str) -> List[str]:
    """Split camelCase, PascalCase, and snake_case identifiers into lowercase domain tokens."""
    clean = Path(identifier).stem.strip("_")
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", clean)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    tokens = re.split(r"[_\-\s\.]+", spaced.lower())
    return [t for t in tokens if len(t) > 2 and t not in STOP_WORDS and not t.isdigit()]


def _parse_source_file_symbols_and_comments(file_path: Path, code_text: str) -> Dict[str, List[str]]:
    """Extract classes, functions/methods, and meaningful comments from a single source file."""
    classes: List[str] = []
    methods: List[str] = []
    comments: List[str] = []

    ext = file_path.suffix.lower()

    # 1. Python native AST parsing
    if ext == ".py":
        try:
            tree = ast.parse(code_text)
            mod_doc = ast.get_docstring(tree)
            if mod_doc:
                cleaned = strip_html_and_badges(mod_doc)
                if len(cleaned) > 12:
                    comments.append(cleaned[:220])

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    c_doc = ast.get_docstring(node)
                    if c_doc and len(comments) < 8:
                        cleaned = strip_html_and_badges(c_doc)
                        if len(cleaned) > 12:
                            comments.append(f"{node.name}: {cleaned[:160]}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.lower() not in BOILERPLATE_SYMBOLS and not (
                        node.name.startswith("__") and node.name.endswith("__")
                    ):
                        methods.append(node.name)
                    f_doc = ast.get_docstring(node)
                    if f_doc and len(comments) < 8:
                        cleaned = strip_html_and_badges(f_doc)
                        if len(cleaned) > 15:
                            comments.append(f"{node.name}(): {cleaned[:140]}")
        except SyntaxError:
            pass

    # 2. Multi-language Regex Extraction (Rust, TS/JS, C#, C++, Go, PowerShell, Shell)
    if not classes and not methods:
        for m in re.finditer(
            r"\b(?:class|struct|trait|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
            code_text,
        ):
            name = m.group(1)
            if name.lower() not in BOILERPLATE_SYMBOLS:
                classes.append(name)

        func_patterns = [
            r"\b(?:def|async\s+def|fn|func|function)\s+([A-Za-z_][A-Za-z0-9_\-]*)\s*[<\(\{]",
            r"\b(?:public|private|protected|internal|static|async|virtual|override)\s+(?:[A-Za-z0-9_<>\[\],\s]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
        ]
        for pat in func_patterns:
            for m in re.finditer(pat, code_text):
                fn_name = m.group(1)
                if fn_name.lower() not in BOILERPLATE_SYMBOLS and fn_name not in ("if", "for", "while", "switch", "catch"):
                    methods.append(fn_name)

    # 3. Extract inline and block comments
    if len(comments) < 5:
        for m in re.finditer(r"(?:/\*\*?([\s\S]*?)\*/|\"\"\"([\s\S]*?)\"\"\"|<#([\s\S]*?)#>)", code_text[:15000]):
            raw_block = m.group(1) or m.group(2) or m.group(3) or ""
            cleaned_block = re.sub(r"^\s*\*\s?", "", raw_block, flags=re.MULTILINE).strip()
            cleaned_block = strip_html_and_badges(cleaned_block)
            if 18 < len(cleaned_block) < 300 and not any(
                lic in cleaned_block.lower() for lic in ("copyright", "mit license", "apache license", "all rights reserved")
            ):
                comments.append(cleaned_block)
                if len(comments) >= 6:
                    break

        line_comment_buffer: List[str] = []
        for line in code_text[:15000].splitlines():
            s = line.strip()
            m_line = re.match(r"^(?:///|//!|//|#)\s*(.+)$", s)
            if m_line:
                c_text = m_line.group(1).strip()
                if (
                    not c_text.startswith(("!", "pragma", "noinspection", "type:", "ruff:", "eslint", "fmt:", "todo", "fixme"))
                    and not re.match(r"^[-=_*#/]{3,}$", c_text)
                    and len(c_text) > 4
                ):
                    line_comment_buffer.append(c_text)
            else:
                if line_comment_buffer:
                    joined = strip_html_and_badges(" ".join(line_comment_buffer))
                    if 20 <= len(joined) <= 260 and not any(
                        lic in joined.lower() for lic in ("copyright", "licensed under", "spdx-license")
                    ):
                        comments.append(joined)
                        if len(comments) >= 8:
                            break
                    line_comment_buffer = []
        if line_comment_buffer and len(comments) < 8:
            joined = strip_html_and_badges(" ".join(line_comment_buffer))
            if 20 <= len(joined) <= 260:
                comments.append(joined)

    return {
        "classes": list(dict.fromkeys(classes))[:20],
        "methods": list(dict.fromkeys(methods))[:35],
        "comments": list(dict.fromkeys(comments))[:8],
    }


def extract_heavy_source_telemetry(
    repo_root: Optional[str],
    project_name: str,
    conn: Optional[sqlite3.Connection] = None,
    repository_id: Optional[str] = None,
    top_n_files: int = 3,
) -> Dict[str, Any]:
    """
    Intermediate analyzer: inspect the heaviest source code files in the project
    (via SQLite catalog first, then bounded filesystem fallback, including single-file scripts).
    """
    t0 = time.perf_counter()
    telemetry: Dict[str, Any] = {
        "heaviest_files": [],
        "classes": [],
        "methods": [],
        "comments": [],
        "inferred_concepts": [],
        "subfolders": [],
        "source": "none",
    }

    # --- Tier A: Fast SQLite Catalog Inspection ---
    if conn is not None and repository_id:
        try:
            cur = conn.cursor()
            like_slash = f"{project_name}/%"
            like_backslash = f"{project_name}\\%"
            cur.execute(
                """
                SELECT s.row_id, s.relative_path,
                       COUNT(b.row_id) AS b_count,
                       MAX(COALESCE(b.end_line, 0)) AS max_line
                FROM source_files s
                LEFT JOIN code_bricks b ON b.file_id = s.row_id
                WHERE s.repository_id = ?
                  AND (s.relative_path = ? OR s.relative_path LIKE ? OR s.relative_path LIKE ?)
                GROUP BY s.row_id
                ORDER BY b_count DESC, max_line DESC
                LIMIT ?;
                """,
                (repository_id, project_name, like_slash, like_backslash, top_n_files),
            )
            heavy_rows = cur.fetchall()
            file_ids = [r["row_id"] for r in heavy_rows if r["b_count"] > 0]

            if file_ids:
                telemetry["source"] = "sqlite-bricks"
                telemetry["heaviest_files"] = [Path(r["relative_path"]).name for r in heavy_rows]
                placeholders = ",".join("?" for _ in file_ids)
                cur.execute(
                    f"""
                    SELECT symbol_name, kind, docstring, ai_summary,
                           (COALESCE(end_line, 0) - COALESCE(start_line, 0)) AS span
                    FROM code_bricks
                    WHERE file_id IN ({placeholders})
                    ORDER BY span DESC
                    LIMIT 80;
                    """,
                    file_ids,
                )
                for b in cur.fetchall():
                    sym = b["symbol_name"]
                    kind = (b["kind"] or "").lower()
                    if kind in ("class", "struct", "trait", "interface"):
                        if sym not in telemetry["classes"]:
                            telemetry["classes"].append(sym)
                    elif sym.lower() not in BOILERPLATE_SYMBOLS and not sym.startswith("__"):
                        if sym not in telemetry["methods"]:
                            telemetry["methods"].append(sym)

                    doc = (b["docstring"] or b["ai_summary"] or "").strip()
                    if doc and len(telemetry["comments"]) < 8:
                        clean_doc = strip_html_and_badges(doc)
                        if len(clean_doc) > 15:
                            telemetry["comments"].append(f"{sym}: {clean_doc[:160]}")
        except Exception as e:
            logger.debug("SQLite heavy-source telemetry lookup failed for %s: %s", project_name, e)

    # --- Tier B: Bounded Filesystem Scan (Directory OR Single Standalone File) ---
    if repo_root and (len(telemetry["methods"]) < 5 or len(telemetry["comments"]) < 2):
        proj_path = Path(repo_root) / project_name
        if not proj_path.exists() and Path(repo_root).name == project_name:
            proj_path = Path(repo_root)

        top_files: List[Path] = []

        # Case 1: Standalone root script file (e.g. pythonEnvUpdate.py, setGoogleDNS.ps1)
        if proj_path.exists() and proj_path.is_file():
            top_files = [proj_path]
            telemetry["source"] = "fs-single-file"

        # Case 2: Standard project directory
        elif proj_path.exists() and proj_path.is_dir():
            candidate_files: List[Tuple[int, Path]] = []
            any_files: List[Tuple[int, Path]] = []
            scanned_files_count = 0
            max_files_to_scan = 1500
            base_depth = len(proj_path.parts)

            try:
                for root, dirs, files in os.walk(proj_path):
                    current_depth = len(Path(root).parts) - base_depth
                    if current_depth == 0:
                        telemetry["subfolders"] = [
                            d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith(".")
                        ][:8]
                    if current_depth > 5:
                        dirs[:] = []
                        continue

                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in IGNORED_DIRS and not d.startswith(".")
                    ]
                    for fname in files:
                        scanned_files_count += 1
                        if scanned_files_count > max_files_to_scan:
                            break
                        fpath = Path(root) / fname
                        ext = fpath.suffix.lower()
                        if fname.endswith((".min.js", ".bundle.js", ".d.ts", ".g.cs", ".Designer.cs")):
                            continue
                        try:
                            size = fpath.stat().st_size
                            if 60 < size < 1_500_000:
                                if ext in SOURCE_CODE_EXTENSIONS:
                                    candidate_files.append((size, fpath))
                                elif ext in (".md", ".tex", ".json", ".yaml", ".yml", ".xml", ".xaml", ".html"):
                                    any_files.append((size, fpath))
                        except OSError:
                            continue
                    if scanned_files_count > max_files_to_scan:
                        break
            except Exception as e:
                logger.debug("Error walking directory for %s: %s", project_name, e)

            candidate_files.sort(key=lambda x: x[0], reverse=True)
            top_files = [f for _, f in candidate_files[:top_n_files]]
            if top_files:
                telemetry["source"] = f"fs-ast({len(top_files)} files)"
            elif any_files:
                any_files.sort(key=lambda x: x[0], reverse=True)
                top_files = [f for _, f in any_files[:top_n_files]]
                telemetry["source"] = f"fs-struct({len(top_files)} files)"

        for fpath in top_files:
            if fpath.name not in telemetry["heaviest_files"]:
                telemetry["heaviest_files"].append(fpath.name)
            try:
                code_text = fpath.read_text(encoding="utf-8", errors="replace")[:65536]
                extracted = _parse_source_file_symbols_and_comments(fpath, code_text)
                for c in extracted["classes"]:
                    if c not in telemetry["classes"]:
                        telemetry["classes"].append(c)
                for m in extracted["methods"]:
                    if m not in telemetry["methods"]:
                        telemetry["methods"].append(m)
                for cm in extracted["comments"]:
                    if cm not in telemetry["comments"]:
                        telemetry["comments"].append(cm)
            except Exception:
                continue

    # --- Compute Inferred Domain Concepts from Project Name, Files, Folders & Identifiers ---
    token_counter: Counter = Counter()
    for tok in split_identifier_tokens(project_name):
        token_counter[tok] += 2
    for fname in telemetry["heaviest_files"] + telemetry["subfolders"]:
        for tok in split_identifier_tokens(fname):
            token_counter[tok] += 1
    for ident in telemetry["classes"][:20] + telemetry["methods"][:35]:
        for tok in split_identifier_tokens(ident):
            token_counter[tok] += 1

    telemetry["classes"] = telemetry["classes"][:15]
    telemetry["methods"] = telemetry["methods"][:25]
    telemetry["comments"] = telemetry["comments"][:6]
    telemetry["inferred_concepts"] = [word for word, _ in token_counter.most_common(8)]
    telemetry["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    return telemetry


def collect_project_context(
    repo_root: Optional[str],
    project_name: str,
    conn: Optional[sqlite3.Connection] = None,
    repository_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect documentation from README, subfolder docs/, manifests, code headers, and heavy source files."""
    context: Dict[str, Any] = {
        "project_name": project_name,
        "taglines": [],
        "readme_paragraphs": [],
        "docs_excerpts": [],
        "manifest_desc": "",
        "code_comments": [],
        "heavy_source": {},
        "context_mode": "docs",
        "_resolution_tag": "STATIC-DOCS",
    }

    proj_dir: Optional[Path] = None
    if repo_root:
        candidate = Path(repo_root) / project_name
        if not candidate.exists() and Path(repo_root).name == project_name:
            candidate = Path(repo_root)
        if candidate.exists() and candidate.is_dir():
            proj_dir = candidate

    if proj_dir is not None:
        # 1. Manifests
        pkg_json = proj_dir / "package.json"
        if pkg_json.exists():
            try:
                pkg_data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                desc = pkg_data.get("description", "")
                if desc and len(desc.strip()) > 5:
                    context["manifest_desc"] = strip_html_and_badges(desc.strip())
            except Exception:
                pass

        pyproject = proj_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8", errors="replace")
                desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                if desc_match:
                    context["manifest_desc"] = strip_html_and_badges(desc_match.group(1).strip())
            except Exception:
                pass

        cargo = proj_dir / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text(encoding="utf-8", errors="replace")
                desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                if desc_match:
                    context["manifest_desc"] = strip_html_and_badges(desc_match.group(1).strip())
            except Exception:
                pass

        # 2. README and main documentation files
        readme_candidates = [
            proj_dir / "README.md",
            proj_dir / "readme.md",
            proj_dir / "README.rst",
            proj_dir / "README.txt",
            proj_dir / "OVERVIEW.md",
            proj_dir / "ARCHITECTURE.md",
        ]
        for rpath in readme_candidates:
            if rpath.exists() and rpath.is_file():
                try:
                    raw_text = rpath.read_text(encoding="utf-8", errors="replace")[:32000]
                    cleaned = strip_html_and_badges(raw_text)
                    paragraphs = [p.strip() for p in cleaned.split("\n") if len(p.strip()) > 15]
                    meaningful = [p for p in paragraphs if p.lower() != project_name.lower()]
                    if meaningful:
                        context["taglines"].append(meaningful[0])
                        context["readme_paragraphs"].extend(meaningful[1:5])
                    break
                except Exception:
                    pass

        # 3. Subfolder "docs" or "doc"
        for docs_folder_name in ("docs", "doc"):
            docs_dir = proj_dir / docs_folder_name
            if docs_dir.exists() and docs_dir.is_dir():
                doc_files = [
                    docs_dir / "README.md",
                    docs_dir / "readme.md",
                    docs_dir / "ARCHITECTURE.md",
                    docs_dir / "architecture.md",
                    docs_dir / "overview.md",
                    docs_dir / "design.md",
                    docs_dir / "introduction.md",
                    docs_dir / "index.md",
                    docs_dir / "summary.md",
                ]
                for f in list(docs_dir.glob("*.md"))[:10]:
                    if f not in doc_files:
                        doc_files.append(f)

                seen_files = set()
                for df in doc_files:
                    if not df.exists() or not df.is_file():
                        continue
                    try:
                        canon = str(df.resolve()).lower()
                        if canon in seen_files:
                            continue
                        seen_files.add(canon)
                        raw = df.read_text(encoding="utf-8", errors="replace")[:20000]
                        cleaned = strip_html_and_badges(raw)
                        lines = [
                            l.strip()
                            for l in cleaned.split("\n")
                            if len(l.strip()) > 20
                            and l.lower() != project_name.lower()
                            and not any(
                                nav in l.lower()
                                for nav in ("back to", "back to the main", "table of contents", "per-release notes")
                            )
                        ]
                        if lines:
                            context["docs_excerpts"].append(f"From {df.name}: " + " ".join(lines[:3]))
                            if len(context["docs_excerpts"]) >= 3:
                                break
                    except Exception:
                        pass
                break

        # 4. Code headers / entry point comments
        code_candidates = [
            proj_dir / "__init__.py",
            proj_dir / "src" / "__init__.py",
            proj_dir / "main.py",
            proj_dir / "app.py",
            proj_dir / "src" / "lib.rs",
            proj_dir / "src" / "main.rs",
            proj_dir / "src" / "index.ts",
            proj_dir / "index.ts",
            proj_dir / "src" / "index.js",
            proj_dir / "Program.cs",
        ]
        for cpath in code_candidates:
            if cpath.exists() and cpath.is_file():
                try:
                    code_text = cpath.read_text(encoding="utf-8", errors="replace")[:2000]
                    py_doc = re.search(r'^(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', code_text.strip(), flags=re.DOTALL)
                    if py_doc:
                        cleaned_doc = strip_html_and_badges(py_doc.group(1))
                        if len(cleaned_doc) > 15:
                            context["code_comments"].append(cleaned_doc[:250])
                            break
                    rust_docs = [re.sub(r"^//!\s*", "", l) for l in code_text.splitlines() if l.strip().startswith("//!")]
                    if rust_docs:
                        cleaned_doc = strip_html_and_badges(" ".join(rust_docs))
                        if len(cleaned_doc) > 15:
                            context["code_comments"].append(cleaned_doc[:250])
                            break
                    js_doc = re.search(r"/\*\*(.*?)\*/", code_text, flags=re.DOTALL)
                    if js_doc:
                        cleaned_doc = strip_html_and_badges(
                            re.sub(r"^\s*\*\s*", "", js_doc.group(1), flags=re.MULTILINE)
                        )
                        if len(cleaned_doc) > 15:
                            context["code_comments"].append(cleaned_doc[:250])
                            break
                except Exception:
                    pass

    # 5. INTERMEDIATE METHOD: If primary docs are missing or sparse, analyze heaviest source code files
    doc_char_count = (
        len(context["manifest_desc"])
        + sum(len(x) for x in context["taglines"])
        + sum(len(x) for x in context["readme_paragraphs"])
        + sum(len(x) for x in context["docs_excerpts"])
        + sum(len(x) for x in context["code_comments"])
    )
    if doc_char_count < 60:
        context["heavy_source"] = extract_heavy_source_telemetry(
            repo_root=repo_root,
            project_name=project_name,
            conn=conn,
            repository_id=repository_id,
            top_n_files=3,
        )
        hs = context["heavy_source"]
        context["context_mode"] = (
            f"heavy-source:{hs.get('source', 'none')}"
            f"({len(hs.get('methods', []))}fns,{len(hs.get('classes', []))}cls,{hs.get('elapsed_ms', 0)}ms)"
        )

    return context


def query_ollama_project_summary(
    project_name: str,
    context: Dict[str, Any],
    model: str = DEFAULT_OLLAMA_MODEL,
    endpoint: str = "http://127.0.0.1:11434",
) -> Optional[str]:
    """Ask local Ollama LLM to synthesize a project overview, with a fast-fail circuit breaker."""
    global _OLLAMA_CIRCUIT_OPEN, _OLLAMA_CONSECUTIVE_FAILURES

    if _OLLAMA_CIRCUIT_OPEN:
        return None

    text_pieces = []
    if context.get("taglines"):
        text_pieces.append("Tagline: " + " ".join(context["taglines"][:2]))
    if context.get("manifest_desc"):
        text_pieces.append("Package Description: " + context["manifest_desc"])
    if context.get("readme_paragraphs"):
        text_pieces.append("README: " + " ".join(context["readme_paragraphs"][:3]))
    if context.get("docs_excerpts"):
        text_pieces.append("Documentation: " + " ".join(context["docs_excerpts"][:2]))
    if context.get("code_comments"):
        text_pieces.append("Code Header: " + " ".join(context["code_comments"][:2]))

    heavy = context.get("heavy_source") or {}
    if heavy:
        if heavy.get("heaviest_files"):
            text_pieces.append("Core Source Modules: " + ", ".join(heavy["heaviest_files"]))
        if heavy.get("classes"):
            text_pieces.append("Key Classes/Structs: " + ", ".join(heavy["classes"][:12]))
        if heavy.get("methods"):
            text_pieces.append("Key Methods/Functions: " + ", ".join(heavy["methods"][:20]))
        if heavy.get("comments"):
            text_pieces.append("Internal Source Comments & Docstrings: " + " | ".join(heavy["comments"][:5]))
        if heavy.get("inferred_concepts"):
            text_pieces.append("Dominant Domain Keywords: " + ", ".join(heavy["inferred_concepts"]))

    raw_context = "\n".join(text_pieces)[:2800]
    if len(raw_context.strip()) < 20:
        return None

    prompt = (
        f"You are a principal software architect. Below is context (documentation or extracted method names, classes, and inline comments from the heaviest source files) for the project '{project_name}':\n\n"
        f"{raw_context}\n\n"
        f"Provide a clear, cohesive architectural overview (2 to 3 paragraphs) explaining:\n"
        f"1. What this project is and its primary functional purpose (infer intent from class/method names and comments if formal docs are absent).\n"
        f"2. Core features, architecture, and key components.\n"
        f"3. Intended use cases and workflows.\n\n"
        f"CRITICAL RULES: Do NOT include ANY HTML tags (<p>, <img>, <div>, etc.). Output clean, human-readable plain text or standard markdown prose only."
    )

    models_to_try = [model] + [m for m in FALLBACK_OLLAMA_MODELS if m != model]

    for m in models_to_try[:2]:
        t_req = time.perf_counter()
        try:
            req_data = json.dumps(
                {
                    "model": m,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 350,
                    },
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{endpoint}/api/generate",
                data=req_data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    response_text = data.get("response", "").strip()
                    if response_text:
                        clean_resp = strip_html_and_badges(response_text)
                        if len(clean_resp) > 40:
                            _OLLAMA_CONSECUTIVE_FAILURES = 0
                            return clean_resp
        except Exception as err:
            elapsed = round((time.perf_counter() - t_req) * 1000)
            _OLLAMA_CONSECUTIVE_FAILURES += 1
            _log_perf(f"  [!] Ollama ({m}) failed/timed out after {elapsed}ms ({err.__class__.__name__})")
            if _OLLAMA_CONSECUTIVE_FAILURES >= MAX_OLLAMA_FAILURES:
                _OLLAMA_CIRCUIT_OPEN = True
                _log_perf("  [CIRCUIT-BREAKER] Ollama unreachable/slow -> switching remaining projects to instant AST/Static synthesis.")
                break
            continue

    return None


def synthesize_clean_fallback_summary(
    project_name: str,
    context: Dict[str, Any],
    top_topics: Optional[List[str]] = None,
) -> str:
    """
    Construct an extended, professional summary from collected documentation,
    or via the intermediate heavy-source code analyzer before falling back to a generic string.
    Always returns a clean `str` (stores resolution badge in `context['_resolution_tag']`).
    """
    sentences: List[str] = []

    tagline = ""
    if context.get("manifest_desc"):
        tagline = context["manifest_desc"]
    elif context.get("taglines"):
        tagline = context["taglines"][0]

    if tagline:
        if not tagline.endswith((".", "!", "?")):
            tagline += "."
        sentences.append(tagline)

    if context.get("readme_paragraphs"):
        for p in context["readme_paragraphs"][:2]:
            clean_p = p.strip()
            if clean_p and clean_p != tagline:
                if not clean_p.endswith((".", "!", "?")):
                    clean_p += "."
                sentences.append(clean_p)

    if context.get("docs_excerpts"):
        for doc in context["docs_excerpts"][:2]:
            if not doc.endswith((".", "!", "?")):
                doc += "."
            sentences.append(doc)

    if not context.get("readme_paragraphs") and context.get("code_comments"):
        for c in context["code_comments"][:1]:
            if not c.endswith((".", "!", "?")):
                c += "."
            sentences.append(c)

    if sentences:
        combined = " ".join(sentences).strip()
        combined = strip_html_and_badges(combined)
        if len(combined) > 30:
            context["_resolution_tag"] = "STATIC-DOCS"
            return combined

    # INTERMEDIATE SOLUTION: Synthesize purpose from heaviest source files, methods, comments, or structure
    heavy = context.get("heavy_source") or {}
    if heavy and (
        heavy.get("methods")
        or heavy.get("classes")
        or heavy.get("comments")
        or heavy.get("heaviest_files")
        or heavy.get("subfolders")
    ):
        heavy_sentences: List[str] = []
        files_str = ", ".join(heavy.get("heaviest_files", [])[:3])
        concepts_str = ", ".join(heavy.get("inferred_concepts", [])[:5])
        subfolders_str = ", ".join(heavy.get("subfolders", [])[:5])

        if concepts_str and files_str:
            heavy_sentences.append(
                f"'{project_name}' is a software module centered on {concepts_str}, primarily implemented across {files_str}."
            )
        elif files_str:
            heavy_sentences.append(
                f"'{project_name}' is an implementation module whose primary logic resides in {files_str}."
            )
        elif subfolders_str:
            heavy_sentences.append(
                f"'{project_name}' is a multi-component workspace organized across submodules ({subfolders_str})."
            )

        if heavy.get("comments"):
            top_comment = heavy["comments"][0].strip()
            if not top_comment.endswith((".", "!", "?")):
                top_comment += "."
            heavy_sentences.append(f"Internal source documentation highlights: {top_comment}")

        arch_parts: List[str] = []
        if heavy.get("classes"):
            arch_parts.append(f"domain structures ({', '.join(heavy['classes'][:5])})")
        if heavy.get("methods"):
            arch_parts.append(f"core operations ({', '.join(heavy['methods'][:7])})")

        if arch_parts:
            heavy_sentences.append(f"Its architecture exposes {' and '.join(arch_parts)}.")

        synthesized_heavy = strip_html_and_badges(" ".join(heavy_sentences).strip())
        if len(synthesized_heavy) > 30:
            context["_resolution_tag"] = f"HEAVY-AST({heavy.get('source', 'ast')})"
            return synthesized_heavy

    # Final Fallback (uses tokenized project name concepts if available)
    name_tokens = split_identifier_tokens(project_name)
    topics = top_topics or name_tokens
    domain_hint = f" specializing in {', '.join(topics)}" if topics else ""
    context["_resolution_tag"] = "DUMMY-FALLBACK"
    return (
        f"Sovereign codebase component suite '{project_name}'{domain_hint}, "
        f"comprising modular utilities, domain models, and service pipelines."
    )


def extract_project_ai_intent(
    repo_root: Optional[str],
    project_name: str,
    top_topics: Optional[List[str]] = None,
    use_ollama: bool = True,
    force: bool = False,
    conn: Optional[sqlite3.Connection] = None,
    repository_id: Optional[str] = None,
    progress_prefix: str = "",
    flush_disk: bool = True,
) -> str:
    """Extract or synthesize an extended, HTML-free project overview with console timing telemetry."""
    t_start = time.perf_counter()
    cache_key = f"{repo_root}:{project_name}"

    if not force and cache_key in _INTENT_CACHE and _INTENT_CACHE[cache_key]:
        cached = _INTENT_CACHE[cache_key]
        if isinstance(cached, tuple):
            cached = cached[0]
        if "<p" in cached or "<img" in cached or "<picture" in cached:
            cached = strip_html_and_badges(cached)
            _INTENT_CACHE[cache_key] = cached
        if (
            len(cached) > 25
            and not cached.startswith("<p")
            and not cached.startswith("Sovereign codebase component suite")
        ):
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
            if progress_prefix:
                _log_perf(f"{progress_prefix} {project_name:<28} -> [CACHE-HIT] ({elapsed_ms}ms)")
            return cached

    # Collect multi-source context (README, docs/, manifests, headers, or heavy source code fallback)
    t_ctx = time.perf_counter()
    context = collect_project_context(
        repo_root=repo_root,
        project_name=project_name,
        conn=conn,
        repository_id=repository_id,
    )
    ctx_ms = round((time.perf_counter() - t_ctx) * 1000, 1)

    # Try Ollama if enabled and circuit breaker is closed
    ai_summary = None
    resolution_tag = ""
    if use_ollama and not _OLLAMA_CIRCUIT_OPEN:
        ai_summary = query_ollama_project_summary(project_name, context)
        if ai_summary:
            resolution_tag = f"OLLAMA+{context.get('context_mode', 'docs')}"

    # Fall back to rich static/intermediate synthesis if Ollama is offline or unavailable
    if not ai_summary:
        ai_summary = synthesize_clean_fallback_summary(project_name, context, top_topics)
        resolution_tag = context.get("_resolution_tag", "STATIC-DOCS")

    ai_summary = strip_html_and_badges(ai_summary)
    save_persisted_summary(cache_key, ai_summary, flush_disk=flush_disk)

    total_ms = round((time.perf_counter() - t_start) * 1000, 1)
    if progress_prefix:
        _log_perf(
            f"{progress_prefix} {project_name:<28} -> [{resolution_tag}] "
            f"(ctx: {ctx_ms}ms | total: {total_ms}ms | len: {len(ai_summary)} chars)"
        )

    return ai_summary


def get_all_projects(
    conn: sqlite3.Connection,
    use_ollama: bool = False,
    compute_summaries: bool = True,
) -> List[Dict[str, Any]]:
    """Aggregate all distinct projects across all registered repositories with live console progress."""
    t_all = time.perf_counter()
    _log_perf("=== Starting get_all_projects() catalog aggregation ===")

    cursor = conn.cursor()

    # Get repository root paths
    cursor.execute("SELECT id, name, root_path FROM repositories;")
    repo_map = {row["id"]: {"name": row["name"], "root": row["root_path"]} for row in cursor.fetchall()}
    _log_perf(f"Loaded {len(repo_map)} registered repositories from SQLite.")

    t_sql = time.perf_counter()
    query = """
    SELECT 
        s.repository_id,
        CASE 
            WHEN INSTR(s.relative_path, '/') > 0 THEN SUBSTR(s.relative_path, 1, INSTR(s.relative_path, '/') - 1)
            WHEN INSTR(s.relative_path, '\\') > 0 THEN SUBSTR(s.relative_path, 1, INSTR(s.relative_path, '\\') - 1)
            ELSE s.relative_path
        END AS project_name,
        COUNT(DISTINCT s.row_id) AS file_count,
        COUNT(b.row_id) AS brick_count,
        SUM(CASE WHEN b.kind = 'class' THEN 1 ELSE 0 END) AS class_count,
        SUM(CASE WHEN b.kind = 'function' THEN 1 ELSE 0 END) AS function_count,
        SUM(CASE WHEN b.kind = 'method' THEN 1 ELSE 0 END) AS method_count,
        ROUND(AVG(b.portability_score), 2) AS avg_portability,
        GROUP_CONCAT(DISTINCT s.relative_path) AS sample_paths
    FROM source_files s
    LEFT JOIN code_bricks b ON b.file_id = s.row_id
    GROUP BY s.repository_id, project_name
    HAVING file_count > 0
    ORDER BY brick_count DESC, file_count DESC;
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    sql_ms = round((time.perf_counter() - t_sql) * 1000, 1)

    valid_rows = [r for r in rows if is_valid_project_candidate(r["project_name"])]
    skipped_noise = len(rows) - len(valid_rows)
    total_projects = len(valid_rows)
    _log_perf(
        f"SQLite GROUP BY query completed in {sql_ms}ms -> {total_projects} valid projects "
        f"(filtered {skipped_noise} loose non-project files/caches)."
    )

    projects: List[Dict[str, Any]] = []

    for idx, r in enumerate(valid_rows, start=1):
        p_name = r["project_name"]
        repo_info = repo_map.get(r["repository_id"], {"name": r["repository_id"], "root": None})
        repo_root = repo_info["root"]

        sample_paths = (r["sample_paths"] or "").split(",")[:40]
        detected_langs = set()
        detected_badges = set()
        for p in sample_paths:
            lang_name, badge = detect_file_language(p)
            if lang_name != "unknown":
                detected_langs.add(lang_name)
                detected_badges.add(badge)

        if not detected_langs:
            detected_langs.add("python")
            detected_badges.add("py")

        progress_tag = f"[{idx:03d}/{total_projects:03d}]"
        if compute_summaries:
            ai_summary = extract_project_ai_intent(
                repo_root=repo_root,
                project_name=p_name,
                use_ollama=use_ollama,
                conn=conn,
                repository_id=r["repository_id"],
                progress_prefix=progress_tag,
                flush_disk=False,  # Flush once at the end of the loop for speed
            )
        else:
            cache_key = f"{repo_root}:{p_name}"
            ai_summary = _INTENT_CACHE.get(cache_key, "")

        project_item = {
            "row_id": -1,
            "brick_id": f"project:{r['repository_id']}:{p_name}",
            "symbol_name": p_name,
            "qualified_name": f"{r['repository_id']}.{p_name}",
            "kind": "project",
            "language": list(detected_langs)[0],
            "language_code": list(detected_badges)[0],
            "languages": sorted(list(detected_langs)),
            "language_badges": sorted(list(detected_badges)),
            "visibility": "public",
            "signature": f"Project {p_name} ({r['file_count']:,} files, {r['brick_count']:,} bricks)",
            "docstring": ai_summary,
            "ai_summary": ai_summary,
            "has_docstring": True,
            "is_async": False,
            "cyclomatic_complexity": 1,
            "portability_score": float(r["avg_portability"] or 1.0),
            "start_line": 1,
            "end_line": r["file_count"],
            "line_count": r["file_count"],
            "file_count": r["file_count"],
            "brick_count": r["brick_count"],
            "class_count": r["class_count"] or 0,
            "function_count": r["function_count"] or 0,
            "method_count": r["method_count"] or 0,
            "repository_id": r["repository_id"],
            "repository_name": repo_info["name"],
            "relative_path": p_name,
            "topic": "Project Workspace",
        }
        projects.append(project_item)

    if compute_summaries:
        flush_summaries_cache()

    total_elapsed = round((time.perf_counter() - t_all) * 1000, 1)
    _log_perf(f"=== Completed get_all_projects(): {len(projects)} projects ready in {total_elapsed}ms ===")
    return projects


THEME_KEYWORDS = {
    "Testing & Benchmark": {"test", "tests", "testing", "mock", "fixture", "assert", "benchmark", "bench", "suite", "runner", "spy", "stub", "pytest"},
    "API & Endpoints": {"api", "route", "router", "routes", "endpoint", "request", "response", "handler", "webhook", "http", "rest", "payload", "client", "controller"},
    "UI & Event Handling": {"ui", "view", "component", "components", "modal", "drawer", "button", "render", "draw", "display", "show", "hide", "toast", "click", "event", "listener", "bind", "dispatch", "toggle", "preview", "frontend"},
    "Database & Storage": {"db", "database", "sql", "sqlite", "query", "repository", "table", "model", "models", "schema", "storage", "session", "crud", "persist", "cache"},
    "Authentication & Security": {"auth", "token", "jwt", "user", "users", "login", "logout", "password", "permission", "role", "credential", "oauth", "hash", "cipher", "crypt", "verify", "protect", "compliance", "bokashi"},
    "Media, Audio & Synthesis": {"audio", "sound", "voice", "speech", "tts", "stt", "speaker", "music", "sample", "wave", "stream", "transcribe", "synthesize", "video", "image", "picture", "frame", "visual"},
    "Parsing & AST Analysis": {"parse", "parser", "ast", "token", "tokens", "lexer", "grammar", "syntax", "symbol", "tree", "extract", "walk", "visitor", "regex"},
    "Workflow & Orchestration": {"task", "job", "pipeline", "workflow", "orchestrator", "worker", "queue", "agent", "step", "plan", "schedule", "cron", "batch", "sync", "runner"},
}


def classify_function_theme(name: str, relative_path: str, docstring: Optional[str] = "") -> str:
    """Classifies a function or method into an aggregated thematic purpose."""
    text = f"{name} {relative_path} {docstring or ''}".lower()
    tokens = set(re.findall(r"[a-z0-9_]{2,}", text))
    best_theme = "Core Logic & Processing"
    best_score = 0
    for theme, kw_set in THEME_KEYWORDS.items():
        score = len(tokens.intersection(kw_set))
        if score > best_score:
            best_score = score
            best_theme = theme
    return best_theme


def synthesize_intended_purpose(name: str, signature: Optional[str] = "", docstring: Optional[str] = "") -> str:
    """Synthesizes the intended purpose from docstring or decomposed verb-noun identifier semantics."""
    if docstring and len(docstring.strip()) > 3:
        clean = docstring.strip().splitlines()[0].strip()
        clean = re.sub(r"^[#\-\*\"\'\`\s]+", "", clean)
        clean = re.sub(r"[\"\'\`]+$", "", clean)
        if len(clean) >= 5:
            return clean[:140]

    clean_name = name.strip("_")
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", clean_name)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    raw_tokens = [t.lower() for t in re.split(r"[_\-\s\.]+", spaced) if t]

    action_verbs = {
        "get": "Retrieves", "fetch": "Fetches", "load": "Loads", "read": "Reads",
        "set": "Sets", "save": "Saves", "store": "Stores", "write": "Writes",
        "update": "Updates", "modify": "Modifies", "patch": "Patches",
        "delete": "Deletes", "remove": "Removes", "drop": "Drops", "clear": "Clears",
        "create": "Creates", "build": "Builds", "make": "Makes", "generate": "Generates",
        "init": "Initializes", "setup": "Sets up", "start": "Starts", "stop": "Stops",
        "handle": "Handles", "process": "Processes", "parse": "Parses", "transform": "Transforms",
        "validate": "Validates", "check": "Checks", "verify": "Verifies", "is": "Checks if", "has": "Checks whether",
        "render": "Renders", "show": "Displays", "display": "Displays", "draw": "Draws",
        "bind": "Binds", "listen": "Listens to", "on": "Event listener for",
        "apply": "Applies", "execute": "Executes", "run": "Runs", "sync": "Synchronizes",
        "find": "Finds", "search": "Searches", "query": "Queries", "filter": "Filters",
        "convert": "Converts", "format": "Formats", "serialize": "Serializes", "deserialize": "Deserializes",
    }

    if raw_tokens and raw_tokens[0] in action_verbs:
        verb = action_verbs[raw_tokens[0]]
        noun = " ".join(raw_tokens[1:]) if len(raw_tokens) > 1 else "target entity"
        return f"{verb} {noun}"
    return f"Executes {name}() logic"


def get_project_functions_catalog(
    conn: sqlite3.Connection,
    project_name: str,
    repository_id: Optional[str] = None,
    max_chapter_size: int = 30,
) -> Dict[str, Any]:
    """
    Retrieves all standalone functions and class methods for a project,
    clustered by pre-existing folder location and aggregated purpose (thema),
    sorted alphabetically A->Z, with synthesized intended purposes.
    """
    cursor = conn.cursor()
    sql = """
    SELECT 
        b.id AS brick_id,
        b.symbol_name,
        b.qualified_name,
        b.kind,
        b.language,
        b.signature,
        b.docstring,
        b.start_line,
        b.end_line,
        b.portability_score,
        b.cyclomatic_complexity,
        s.relative_path
    FROM code_bricks b
    JOIN source_files s ON b.file_id = s.row_id
    WHERE (s.relative_path LIKE ? OR s.relative_path LIKE ?)
      AND b.kind IN ('function', 'method')
      AND s.relative_path NOT LIKE '%node_modules%'
      AND s.relative_path NOT LIKE '%.delta%'
      AND s.relative_path NOT LIKE '%.git%'
      AND s.relative_path NOT LIKE '%.venv%'
    """
    params: List[Any] = [f"{project_name}/%", f"{project_name}\\%"]
    if repository_id:
        sql += " AND s.repository_id = ?"
        params.append(repository_id)

    sql += " ORDER BY s.relative_path ASC, b.symbol_name ASC;"
    cursor.execute(sql, params)
    raw_bricks = cursor.fetchall()

    def get_rel_folder(full_rel_path: str, p_name: str) -> str:
        norm = full_rel_path.replace("\\", "/")
        if norm.startswith(p_name + "/"):
            norm = norm[len(p_name) + 1:]
        folder = os.path.dirname(norm)
        return folder if folder else "(root)"

    # Cluster by (folder, theme)
    folder_theme_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in raw_bricks:
        rel_path = row["relative_path"].replace("\\", "/")
        name = row["symbol_name"]
        doc = row["docstring"]
        sig = row["signature"]
        theme = classify_function_theme(name, rel_path, doc)
        folder = get_rel_folder(rel_path, project_name)
        purpose = synthesize_intended_purpose(name, sig, doc)

        item = {
            "brick_id": row["brick_id"],
            "symbol_name": name,
            "qualified_name": row["qualified_name"],
            "kind": row["kind"],
            "language": row["language"],
            "language_code": normalize_language_badge(row["language"], rel_path),
            "signature": sig,
            "docstring": doc,
            "purpose": purpose,
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "portability_score": row["portability_score"],
            "complexity": row["cyclomatic_complexity"] or 1,
            "relative_path": rel_path,
            "folder": folder,
            "theme": theme,
        }
        key = (folder, theme)
        folder_theme_map.setdefault(key, []).append(item)

    # Subdivide chapters if they exceed max_chapter_size
    chapters: List[Dict[str, Any]] = []
    total_functions_count = 0

    for (folder, theme), items in sorted(folder_theme_map.items(), key=lambda x: (x[0][0], x[0][1])):
        items_sorted = sorted(items, key=lambda it: it["symbol_name"].lower())
        total_functions_count += len(items_sorted)

        if len(items_sorted) <= max_chapter_size:
            chapter_id = f"{folder}::{theme}".replace(" ", "_").replace("/", "_").replace(".", "_")
            chapters.append({
                "chapter_id": chapter_id,
                "folder": folder,
                "theme": theme,
                "chapter_title": f"{folder} • {theme}",
                "functions_count": len(items_sorted),
                "functions": items_sorted,
            })
        else:
            # Subdivide by filename to maintain manageable chapter sizes
            file_groups: Dict[str, List[Dict[str, Any]]] = {}
            for it in items_sorted:
                fname = os.path.basename(it["relative_path"])
                file_groups.setdefault(fname, []).append(it)

            for fname, f_items in sorted(file_groups.items()):
                f_sorted = sorted(f_items, key=lambda it: it["symbol_name"].lower())
                chapter_id = f"{folder}_{fname}::{theme}".replace(" ", "_").replace("/", "_").replace(".", "_")
                chapters.append({
                    "chapter_id": chapter_id,
                    "folder": f"{folder}/{fname}",
                    "theme": theme,
                    "chapter_title": f"{folder}/{fname} • {theme}",
                    "functions_count": len(f_sorted),
                    "functions": f_sorted,
                })

    return {
        "project_name": project_name,
        "repository_id": repository_id,
        "total_functions": total_functions_count,
        "chapters_count": len(chapters),
        "chapters": chapters,
    }
