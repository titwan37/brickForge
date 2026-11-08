"""Project-level aggregation and AI intent synthesis for BrickForge Catalog."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

_INTENT_CACHE: Dict[str, str] = {}


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
    if lower.endswith(".json"):
        return "json", "json"
    if lower.endswith((".md", ".markdown")):
        return "markdown", "md"
    if lower.endswith(".sql"):
        return "sql", "sql"
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


def extract_project_ai_intent(repo_root: Optional[str], project_name: str, top_topics: List[str] = None) -> str:
    """Extract or synthesize the project intent from README or codebase symbols."""
    cache_key = f"{repo_root}:{project_name}"
    if cache_key in _INTENT_CACHE:
        return _INTENT_CACHE[cache_key]

    if repo_root:
        proj_dir = Path(repo_root) / project_name
        readme_candidates = [
            proj_dir / "README.md",
            proj_dir / "readme.md",
            proj_dir / "docs" / "README.md",
            proj_dir / "package.json",
        ]
        for candidate in readme_candidates:
            if candidate.exists():
                try:
                    if candidate.suffix == ".json":
                        import json
                        pkg = json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
                        desc = pkg.get("description")
                        if desc and len(desc.strip()) > 5:
                            _INTENT_CACHE[cache_key] = desc.strip()
                            return desc.strip()
                    else:
                        lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                        para: List[str] = []
                        for line in lines:
                            s = line.strip()
                            if not s:
                                if para:
                                    break
                                continue
                            if s.startswith(("#", "[!", "[![", "```", "<!--", "http")):
                                if s.startswith("> **") and s.endswith("**"):
                                    clean_quote = s.strip("> *").strip()
                                    if len(clean_quote) > 15:
                                        _INTENT_CACHE[cache_key] = clean_quote
                                        return clean_quote
                                if para:
                                    break
                                continue
                            clean_s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", s)
                            clean_s = re.sub(r"[*_`]", "", clean_s)
                            para.append(clean_s)
                            if len(" ".join(para)) > 260:
                                break
                        if para:
                            intent_text = " ".join(para).strip()
                            if len(intent_text) > 20:
                                _INTENT_CACHE[cache_key] = intent_text
                                return intent_text
                except Exception:
                    pass

    # Fallback domain-aware synthesis
    domain_hint = f" specializing in {', '.join(top_topics)}" if top_topics else ""
    fallback_intent = f"Sovereign codebase component suite '{project_name}'{domain_hint}, comprising modular utilities, domain models, and service pipelines."
    _INTENT_CACHE[cache_key] = fallback_intent
    return fallback_intent


def get_all_projects(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Aggregate all distinct projects across all registered repositories."""
    cursor = conn.cursor()

    # Get repository root paths
    cursor.execute("SELECT id, name, root_path FROM repositories;")
    repo_map = {row["id"]: {"name": row["name"], "root": row["root_path"]} for row in cursor.fetchall()}

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
    projects: List[Dict[str, Any]] = []

    for r in rows:
        p_name = r["project_name"]
        if not p_name or p_name in (".git", ".pytest_cache", ".ruff_cache", "site-packages"):
            continue

        repo_info = repo_map.get(r["repository_id"], {"name": r["repository_id"], "root": None})
        repo_root = repo_info["root"]

        # Detect languages used in this project
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

        ai_summary = extract_project_ai_intent(repo_root, p_name)

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

    return projects
