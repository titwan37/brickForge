"""Project-level aggregation and AI intent synthesis for BrickForge Catalog."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_MODEL = "jetelain/Qwen3.5-9B:latest"
FALLBACK_OLLAMA_MODELS = [
    "jetelain/Qwen3.5-9B:latest",
    "qwen2.5-coder:7b",
    "llama3.2:3b",
    "qwen2.5:7b",
    "mistral-7b:latest",
]


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


def save_persisted_summary(cache_key: str, summary: str):
    """Save an AI project summary to in-memory cache and persistent JSON."""
    _INTENT_CACHE[cache_key] = summary
    cache_path = get_summaries_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        current = load_persisted_summaries()
        current[cache_key] = summary
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
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


def strip_html_and_badges(text: str) -> str:
    """Strip all HTML tags, images, badge shields, language switchers, and formatting noise."""
    if not text:
        return ""

    # Decode HTML entities
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

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Remove HTML blocks (script, style, picture, video, audio)
    text = re.sub(r"<(script|style|picture|video|audio)[^>]*>.*?</\1>", " ", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all HTML tags completely: <p...>, </p>, <img...>, <div...>, etc.
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove markdown images: ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)

    # Remove markdown badge links: [![alt](badge_url)](target_url)
    text = re.sub(r"\[\s*!\[[^\]]*\]\([^\)]*\)\s*\]\([^\)]*\)", "", text)

    # Convert markdown links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)

    # Remove reference-style links [text][id]
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)

    # Remove raw URLs
    text = re.sub(r"https?://\S+", "", text)

    cleaned_lines: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        # Skip language translation selector lines (e.g. English | Türkçe | العربية | 日本語)
        s_lower = s.lower()
        if any(w in s_lower for w in ("english", "türkçe", "deutsch", "français", "español", "русский", "日本語", "العربية", "中文")) and ("|" in s or "·" in s or "/" in s):
            continue
        # Skip badge link rows or navigation link bars
        if ("·" in s or "|" in s or "•" in s) and len(re.findall(r"(discord|telegram|twitter|website|github|docs|pypi|license|quickstart|catalog|playground|product hunt|npm)", s_lower)) >= 2:
            continue
        # Skip horizontal dividers
        if re.match(r"^[-=_*#]{3,}$", s):
            continue
        # Remove leading markdown heading hashes
        s = re.sub(r"^#+\s*", "", s)
        # Remove leading blockquote markers
        s = re.sub(r"^>\s*", "", s)
        # Strip bold/italic/code markers
        s = re.sub(r"[*_`]", "", s)
        # Normalize whitespace
        s = " ".join(s.split())
        if len(s) > 3:
            cleaned_lines.append(s)

    return "\n".join(cleaned_lines)


def collect_project_context(repo_root: Optional[str], project_name: str) -> Dict[str, Any]:
    """Collect documentation from README, subfolder docs/, manifests, and code headers."""
    context: Dict[str, Any] = {
        "project_name": project_name,
        "taglines": [],
        "readme_paragraphs": [],
        "docs_excerpts": [],
        "manifest_desc": "",
        "code_comments": [],
    }

    if not repo_root:
        return context

    proj_dir = Path(repo_root) / project_name
    if not proj_dir.exists() and Path(repo_root).name == project_name:
        proj_dir = Path(repo_root)

    if not proj_dir.exists():
        return context

    # 1. Manifests (package.json, pyproject.toml, Cargo.toml, *.csproj)
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
        if rpath.exists():
            try:
                raw_text = rpath.read_text(encoding="utf-8", errors="replace")
                cleaned = strip_html_and_badges(raw_text)
                paragraphs = [p.strip() for p in cleaned.split("\n") if len(p.strip()) > 15]
                # Filter out pure headings that are just the project name
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
            for f in docs_dir.glob("*.md"):
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
                    raw = df.read_text(encoding="utf-8", errors="replace")
                    cleaned = strip_html_and_badges(raw)
                    lines = [
                        l.strip()
                        for l in cleaned.split("\n")
                        if len(l.strip()) > 20
                        and l.lower() != project_name.lower()
                        and not any(nav in l.lower() for nav in ("back to", "back to the main", "table of contents", "per-release notes"))
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
        if cpath.exists():
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
                js_doc = re.search(r'/\*\*(.*?)\*/', code_text, flags=re.DOTALL)
                if js_doc:
                    cleaned_doc = strip_html_and_badges(re.sub(r'^\s*\*\s*', '', js_doc.group(1), flags=re.MULTILINE))
                    if len(cleaned_doc) > 15:
                        context["code_comments"].append(cleaned_doc[:250])
                        break
            except Exception:
                pass

    return context


def query_ollama_project_summary(
    project_name: str,
    context: Dict[str, Any],
    model: str = DEFAULT_OLLAMA_MODEL,
    endpoint: str = "http://127.0.0.1:11434"
) -> Optional[str]:
    """Ask local Ollama LLM to synthesize a clean, informative, HTML-free project overview."""
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

    raw_context = "\n".join(text_pieces)[:2500]
    if len(raw_context.strip()) < 20:
        return None

    prompt = (
        f"You are a principal software architect. Below is context extracted from the codebase and documentation for the project '{project_name}':\n\n"
        f"{raw_context}\n\n"
        f"Provide a clear, cohesive architectural overview (2 to 3 paragraphs) explaining:\n"
        f"1. What this project is and its primary value proposition.\n"
        f"2. Core features, architecture, and technology stack.\n"
        f"3. Intended use cases and workflows.\n\n"
        f"CRITICAL RULES: Do NOT include ANY HTML tags (<p>, <img>, <div>, etc.). Output clean, human-readable plain text or standard markdown prose only."
    )

    models_to_try = [model] + [m for m in FALLBACK_OLLAMA_MODELS if m != model]

    for m in models_to_try[:2]:
        try:
            req_data = json.dumps({
                "model": m,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 450,
                }
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{endpoint}/api/generate",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    response_text = data.get("response", "").strip()
                    if response_text:
                        clean_resp = strip_html_and_badges(response_text)
                        if len(clean_resp) > 40:
                            return clean_resp
        except Exception:
            continue

    return None


def synthesize_clean_fallback_summary(
    project_name: str,
    context: Dict[str, Any],
    top_topics: List[str] = None
) -> str:
    """Construct an extended, professional summary from collected documentation without HTML."""
    sentences = []

    # 1. Tagline / Headline
    tagline = ""
    if context.get("manifest_desc"):
        tagline = context["manifest_desc"]
    elif context.get("taglines"):
        tagline = context["taglines"][0]

    if tagline:
        if not tagline.endswith((".", "!", "?")):
            tagline += "."
        sentences.append(tagline)

    # 2. Main README Description
    if context.get("readme_paragraphs"):
        for p in context["readme_paragraphs"][:2]:
            clean_p = p.strip()
            if clean_p and clean_p != tagline:
                if not clean_p.endswith((".", "!", "?")):
                    clean_p += "."
                sentences.append(clean_p)

    # 3. Subfolder docs context
    if context.get("docs_excerpts"):
        for doc in context["docs_excerpts"][:2]:
            if not doc.endswith((".", "!", "?")):
                doc += "."
            sentences.append(doc)

    # 4. Code Header context
    if not context.get("readme_paragraphs") and context.get("code_comments"):
        for c in context["code_comments"][:1]:
            if not c.endswith((".", "!", "?")):
                c += "."
            sentences.append(c)

    if sentences:
        combined = " ".join(sentences).strip()
        combined = strip_html_and_badges(combined)
        if len(combined) > 30:
            return combined

    # 5. Domain-aware fallback
    domain_hint = f" specializing in {', '.join(top_topics)}" if top_topics else ""
    return f"Sovereign codebase component suite '{project_name}'{domain_hint}, comprising modular utilities, domain models, and service pipelines."


def extract_project_ai_intent(
    repo_root: Optional[str],
    project_name: str,
    top_topics: List[str] = None,
    use_ollama: bool = True,
    force: bool = False,
) -> str:
    """Extract or synthesize an extended, HTML-free project overview."""
    cache_key = f"{repo_root}:{project_name}"
    if not force and cache_key in _INTENT_CACHE and _INTENT_CACHE[cache_key]:
        cached = _INTENT_CACHE[cache_key]
        if "<p" in cached or "<img" in cached or "<picture" in cached:
            cached = strip_html_and_badges(cached)
            _INTENT_CACHE[cache_key] = cached
        if len(cached) > 25 and not cached.startswith("<p"):
            return cached

    # Collect multi-source context (README, docs/, manifests, code headers)
    context = collect_project_context(repo_root, project_name)

    # Try Ollama if enabled
    ai_summary = None
    if use_ollama:
        ai_summary = query_ollama_project_summary(project_name, context)

    # Fall back to rich static synthesis if Ollama is offline or unavailable
    if not ai_summary:
        ai_summary = synthesize_clean_fallback_summary(project_name, context, top_topics)

    # Guarantee final cleanup
    ai_summary = strip_html_and_badges(ai_summary)

    # Persist in memory and disk cache
    save_persisted_summary(cache_key, ai_summary)
    return ai_summary


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
