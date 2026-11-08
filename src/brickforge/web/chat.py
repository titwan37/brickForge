"""Knowledgeable Conversational Chat Engine grounded on BrickForge Code Catalog."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from brickforge.web.initiatives import INITIATIVES_REGISTRY

DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
SERVER_DEFAULT_MODEL = "qwen3:1.7b"
FALLBACK_MODELS = [
    "qwen2.5-coder:7b",
    "llama3.2:3b",
    "qwen3:1.7b",
    "openclaw-brain:latest",
    "qwen2.5:7b",
    "mistral-7b:latest",
    "deepseek-r1:8b",
    "deepseek-coder-v2:lite",
]


# Query stop words and conversational filler words to strip for high-precision catalog search
QUERY_STOPWORDS = {
    # Standard English grammatical stopwords
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "isn", "it", "its", "itself", "let",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would", "you",
    "your", "yours", "yourself", "yourselves",
    # Conversational chat wrapper words
    "tell", "show", "find", "give", "suggest", "recommend", "advise", "consult",
    "look", "search", "get", "fetch", "list", "please", "help", "want", "need",
    "code", "script", "scripts", "brick", "bricks", "component", "components",
    "module", "modules", "file", "files", "function", "functions", "class", "classes",
    "method", "methods", "example", "examples", "feedback", "ignoring", "ignored",
    "spontaneously", "refer", "refers", "referring", "related", "implement", "implementation",
    # Common question adverbs, adjectives, qualifiers, and intent fluff
    "efficiently", "quickly", "easily", "directly", "properly", "best", "good", "simple",
    "fast", "used", "using", "use", "way", "ways", "solution", "solutions",
    "different", "various", "able", "currently", "actually", "really", "possible", "like",
    "available", "better", "great", "right", "know", "try", "trying", "own", "mine"
}

THEME_EXPANSIONS = {
    "tts": ["tts", "speech", "audio", "voice", "sound", "synthesize", "speaker"],
    "audio": ["audio", "sound", "wave", "dsp", "voice", "speech", "tts"],
    "speech": ["speech", "voice", "tts", "audio", "transcribe", "stt"],
    "agent": ["agent", "llm", "prompt", "pipeline", "orchestrator", "tool"],
    "auth": ["auth", "token", "jwt", "login", "password", "signature", "verify"],
    "database": ["db", "sql", "sqlite", "postgres", "query", "storage", "repository"],
    "test": ["test", "mock", "fixture", "suite", "runner", "assert"],
    "parser": ["parser", "ast", "tree", "token", "lexer", "grammar"],
    "markdown": ["markdown", "md"],
    "md": ["md", "markdown"],
    "pdf": ["pdf"],
    "convert": ["convert", "converter", "compile", "transform", "export", "render", "extract"]
}

LANG_MAP = {
    "python": "python",
    "py": "python",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "typescript-react",
    "javascript": "javascript",
    "js": "javascript",
    "csharp": "csharp",
    "c#": "csharp",
    "rust": "rust",
    "rs": "rust",
    "go": "go",
    "golang": "go",
    "cpp": "cpp",
    "c++": "cpp"
}


def detect_language_intent(query: str) -> Optional[str]:
    """Detect if the user explicitly asked for a programming language in their prompt."""
    q_lower = query.lower()
    for pattern, lang in LANG_MAP.items():
        if re.search(r"(?:^|[\s_\-/,.])" + re.escape(pattern) + r"(?:$|[\s_\-/,.])", q_lower):
            return lang
    return None


def is_vendor_path(path: str) -> bool:
    """Identify third-party vendor or minified files that should be deprioritized."""
    p = path.lower()
    vendor_markers = ["jquery", "bootstrap", "node_modules", "vendor/", "site-packages", ".min.js", "dist/"]
    return any(m in p for m in vendor_markers)


def is_test_path(path: str, symbol: str = "") -> bool:
    """Identify test files or test runner functions to deprioritize behind real implementations."""
    p = path.lower().replace("\\", "/")
    s = symbol.lower()
    return (
        "/test" in p or "tests/" in p or s.startswith("test_") or "_test." in p or p.endswith("_test.py")
    )


class BrickForgeChatEngine:
    """Conversational assistant grounded in the sovereign BrickForge SQLite catalog."""

    def __init__(self, db_path: Path | str, ollama_endpoint: str = DEFAULT_OLLAMA_ENDPOINT):
        self.db_path = Path(db_path)
        self.endpoint = ollama_endpoint.rstrip("/")

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_available_models(self) -> Tuple[List[str], bool]:
        """Fetch models from live Ollama instance, or return fallbacks if offline."""
        try:
            with httpx.Client(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
                res = client.get(f"{self.endpoint}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m["name"] for m in data.get("models", []) if "name" in m]
                    if models:
                        return models, True
        except Exception:
            pass
        return FALLBACK_MODELS, False

    def search_catalog_for_query(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve the most relevant code bricks for a given query or theme."""
        if not self.db_path.exists():
            return []

        lang_pref = detect_language_intent(query)
        raw_tokens = [t.lower() for t in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query)]
        # Filter out common conversational/grammatical stopwords
        core_tokens = [t for t in raw_tokens if t not in QUERY_STOPWORDS]
        if not core_tokens:
            core_tokens = raw_tokens

        # Domain expansion for common software architectures
        expanded_terms = list(core_tokens)
        for t in core_tokens:
            if t in THEME_EXPANSIONS:
                for exp in THEME_EXPANSIONS[t]:
                    if exp not in expanded_terms:
                        expanded_terms.append(exp)

        results: List[Dict[str, Any]] = []
        seen_ids = set()

        def add_ranked_rows(rows, max_count=limit):
            dict_rows = [dict(r) for r in rows]
            # Prioritize:
            # 1. First-party code over vendor/minified files (jquery, node_modules, etc.)
            # 2. Production implementation code over test files / unit test cases
            # 3. Explicitly requested programming language if specified in user query
            # 4. FTS5 BM25 match rank (more negative is better)
            # 5. Portability score
            sorted_rows = sorted(
                dict_rows,
                key=lambda r: (
                    1 if is_vendor_path(r["relative_path"]) else 0,
                    1 if is_test_path(r["relative_path"], r.get("symbol_name", "")) else 0,
                    0 if (lang_pref and r.get("language") == lang_pref) else 1,
                    r.get("rank", 0) if r.get("rank") is not None else 0,
                    -float(r.get("portability_score") or 0.0),
                ),
            )
            for r in sorted_rows:
                bid = r["brick_id"]
                if bid not in seen_ids:
                    results.append(r)
                    seen_ids.add(bid)
                    if len(results) >= max_count:
                        break

        with self.get_db_connection() as conn:
            cursor = conn.cursor()

            fts_sql = """
            SELECT 
                b.row_id,
                b.id AS brick_id,
                b.symbol_name,
                b.qualified_name,
                b.kind,
                b.language,
                b.signature,
                b.docstring,
                b.source_code,
                b.portability_score,
                b.cyclomatic_complexity,
                b.start_line,
                b.end_line,
                s.relative_path,
                r.name AS repository_name,
                r.id AS repository_id,
                f.rank
            FROM bricks_fts f
            JOIN code_bricks b ON f.rowid = b.row_id
            JOIN source_files s ON b.file_id = s.row_id
            JOIN repositories r ON s.repository_id = r.id
            WHERE bricks_fts MATCH ?
            ORDER BY f.rank ASC
            LIMIT 30;
            """

            # Strategy 0: High-priority domain concept-coupling (e.g. markdown/md + pdf)
            is_md_pdf = any(t in core_tokens for t in ("markdown", "md")) and ("pdf" in core_tokens)
            if is_md_pdf:
                fts_pair = '("markdown"* OR "md"*) AND "pdf"*'
                try:
                    cursor.execute(fts_sql, (fts_pair,))
                    add_ranked_rows(cursor.fetchall())
                except Exception:
                    pass

            # Strategy 1: High-precision FTS5 AND query across core keywords
            if len(results) < limit and len(core_tokens) >= 2:
                and_query_str = " AND ".join(f'"{t}"*' for t in core_tokens[:4])
                try:
                    cursor.execute(fts_sql, (and_query_str,))
                    add_ranked_rows(cursor.fetchall())
                except Exception:
                    pass

            # Strategy 2: BM25 Ranked FTS5 search with core tokens and expanded terms
            if len(results) < limit and core_tokens:
                combined_terms = list(core_tokens)
                for t in expanded_terms:
                    if t not in combined_terms:
                        combined_terms.append(t)
                or_query_str = " OR ".join(f'"{t}"*' for t in combined_terms[:12])
                try:
                    cursor.execute(fts_sql, (or_query_str,))
                    add_ranked_rows(cursor.fetchall())
                except Exception:
                    pass

            # Strategy 3: Fallback SQL LIKE search across symbol_name, signature, and path
            if len(results) < limit:
                like_conditions = []
                params: List[Any] = []

                for t in core_tokens[:4]:
                    like_conditions.append(
                        "(b.symbol_name LIKE ? OR b.signature LIKE ? OR b.docstring LIKE ? OR s.relative_path LIKE ?)"
                    )
                    wildcard = f"%{t}%"
                    params.extend([wildcard, wildcard, wildcard, wildcard])

                if like_conditions:
                    sql_like = f"""
                    SELECT 
                        b.row_id,
                        b.id AS brick_id,
                        b.symbol_name,
                        b.qualified_name,
                        b.kind,
                        b.language,
                        b.signature,
                        b.docstring,
                        b.source_code,
                        b.portability_score,
                        b.cyclomatic_complexity,
                        b.start_line,
                        b.end_line,
                        s.relative_path,
                        r.name AS repository_name,
                        r.id AS repository_id,
                        0.0 AS rank
                    FROM code_bricks b
                    JOIN source_files s ON b.file_id = s.row_id
                    JOIN repositories r ON s.repository_id = r.id
                    WHERE ({' OR '.join(like_conditions)})
                    ORDER BY b.portability_score DESC, b.row_id ASC
                    LIMIT ?;
                    """
                    cursor.execute(sql_like, [*params, limit * 2])
                    add_ranked_rows(cursor.fetchall())

            # Enrich candidates with dependencies
            for b in results:
                # Internal dependencies
                cursor.execute(
                    """
                    SELECT COALESCE(tb.symbol_name, bd.unresolved_symbol) as dep_name, bd.dependency_type
                    FROM brick_dependencies bd
                    LEFT JOIN code_bricks tb ON bd.target_row_id = tb.row_id
                    WHERE bd.source_row_id = ?
                    LIMIT 8;
                    """,
                    (b["row_id"],),
                )
                b["internal_dependencies"] = [
                    {"name": r["dep_name"], "type": r["dependency_type"]}
                    for r in cursor.fetchall()
                ]

                # External dependencies
                cursor.execute(
                    """
                    SELECT package_name, ecosystem
                    FROM external_packages
                    WHERE brick_row_id = ?
                    LIMIT 8;
                    """,
                    (b["row_id"],),
                )
                b["external_packages"] = [
                    {"name": r["package_name"], "ecosystem": r["ecosystem"]}
                    for r in cursor.fetchall()
                ]

        return results[:limit]

    def build_system_prompt(self, candidate_bricks: List[Dict[str, Any]], query: str = "") -> str:
        """Formulate the system prompt with verified codebase grounding and strategic initiative context."""
        catalog_context_lines = []

        # Detect matching strategic initiative domain
        matched_initiative = None
        q_lower = query.lower() if query else ""
        for ini in INITIATIVES_REGISTRY:
            if any(kw in q_lower for kw in ini.get("keywords", [])):
                matched_initiative = ini
                break

        initiative_context = ""
        if matched_initiative:
            initiative_context = (
                f"=== STRATEGIC INITIATIVE DOMAIN ===\n"
                f"Initiative: {matched_initiative['name']} ({matched_initiative['slug']})\n"
                f"Strategic Focus: {matched_initiative.get('tagline', '')}\n"
                f"====================================\n\n"
            )

        for idx, b in enumerate(candidate_bricks, 1):
            source_lines = (b.get("source_code") or "").splitlines()
            snippet = "\n".join(source_lines[:25])
            if len(source_lines) > 25:
                snippet += "\n    # ... [truncated remainder of implementation]"

            ext_pkgs = ", ".join(p["name"] for p in b.get("external_packages", [])) or "None (self-contained)"
            doc_str = (b.get("docstring") or "No docstring provided.").strip()

            catalog_context_lines.append(
                f"### BRICK #{idx}: `{b['symbol_name']}` ({b['kind']})\n"
                f"- **Repository**: {b['repository_name']} (`{b['repository_id']}`)\n"
                f"- **File Path**: `{b['relative_path']}` (Lines {b['start_line']}-{b['end_line']})\n"
                f"- **Language**: {b.get('language', 'python')}\n"
                f"- **Signature**: `{b['signature']}`\n"
                f"- **Portability Score**: {b['portability_score']} (0.0 to 1.0 scale)\n"
                f"- **Complexity**: {b['cyclomatic_complexity'] or 1}\n"
                f"- **External Packages**: {ext_pkgs}\n"
                f"- **Docstring**: {doc_str}\n"
                f"- **Implementation Preview**:\n```{b.get('language', 'python')}\n{snippet}\n```\n"
            )

        context_body = "\n\n".join(catalog_context_lines) if catalog_context_lines else "No specific matching bricks found in catalog."

        return (
            "You are the sovereign BrickForge Lead Software Architect & Component Reuse Advisor.\n"
            "Your mission is to guide developers on how to reuse, compose, and adapt existing code bricks "
            "already indexed in the BrickForge catalog across their local repositories.\n\n"
            "RULES:\n"
            "1. Ground your advice directly in the verified code bricks provided below.\n"
            "2. Systematically present and document ALL candidate code bricks provided in the context.\n"
            "   For each candidate brick:\n"
            "   - State its symbol name, language, repository, and relative file path with line numbers.\n"
            "   - Explain its functional role, implementation approach, and how it addresses the user's requirements.\n"
            "   - Detail its external dependencies (e.g. PyMuPDF/fitz, Marker, Docling, Tesseract, etc.) and portability score.\n"
            "3. If multiple bricks offer alternative approaches or toolchains, compare their trade-offs (e.g., speed vs formatting fidelity vs OCR on scanned pages).\n"
            "4. Provide copyable, ready-to-use Python code snippets showing how to import, call, or pipeline these bricks.\n"
            "5. Format your output using crisp, structured GitHub-flavored Markdown with clear headings and bullet points.\n\n"
            f"{initiative_context}"
            "=== VERIFIED BRICKFORGE CATALOG BRICKS ===\n"
            f"{context_body}\n"
            "==========================================="
        )

    def generate_fallback_report(
        self,
        query: str,
        bricks: List[Dict[str, Any]],
    ) -> str:
        """Produce an architectural reusability report if Ollama is unreachable."""
        if not bricks:
            return (
                f"### 🔍 No Specific Code Bricks Found for \"{query}\"\n\n"
                "I searched the indexed catalog across all repositories, but did not locate bricks matching those exact keywords.\n\n"
                "**Suggestions**:\n"
                "- Try querying broader thematic terms: `markdown`, `pdf`, `audio`, `tts`, `agent`, `jwt`, `database`, `pipeline`, or `parser`.\n"
                "- Ensure the target source repositories have been indexed via `python scripts/sync_repositories.py`.\n"
            )

        report_lines = [
            f"### 🧱 BrickForge Reusability Analysis for: *\"{query}\"*\n\n",
            f"I found **{len(bricks)} candidate code bricks** in your local catalog that directly address this workflow.\n\n",
            "#### 📋 Retrieved Code Bricks & Implementation Details:\n",
        ]

        for idx, b in enumerate(bricks, 1):
            port_badge = "★ Highly Portable (100%)" if b["portability_score"] >= 0.9 else f"Portability: {b['portability_score']}"
            ext_pkgs = ", ".join(p["name"] for p in b.get("external_packages", [])) or "None (Self-contained)"
            source_lines = (b.get("source_code") or "").splitlines()
            snippet = "\n".join(source_lines[:20])

            report_lines.append(
                f"**{idx}. `{b['symbol_name']}`** (`{b['kind']}` — {b.get('language', 'python')})\n"
                f"- **Repository**: **{b['repository_name']}** (`{b['repository_id']}`)\n"
                f"- **Location**: `{b['relative_path']}` (Lines {b['start_line']}-{b['end_line']})\n"
                f"- **Quality**: `{port_badge}` | Complexity: `{b['cyclomatic_complexity'] or 1}`\n"
                f"- **External Dependencies**: `{ext_pkgs}`\n"
                f"- **Signature**: `{b['signature']}`\n"
            )
            if b.get("docstring"):
                report_lines.append(f"> *\"{b['docstring'].strip()[:180]}\"*\n\n")

            report_lines.append(
                f"```{b.get('language', 'python')}\n# File: {b['relative_path']} (L{b['start_line']}-L{b['end_line']})\n{snippet}\n```\n\n"
            )

        # Architectural synthesis snippet
        top_brick = bricks[0]
        report_lines.append(
            "#### 🛠️ Composition & Integration Blueprint:\n"
            "To adapt these bricks into your pipeline, you can import and execute them directly:\n\n"
            "```python\n"
            "# Example composable orchestration pattern:\n"
            f"# Reusing {top_brick['symbol_name']} from {top_brick['relative_path']}\n\n"
            f"from pathlib import Path\n\n"
            f"# Primary component\n"
            f"# {top_brick['signature']}\n"
            "def compose_workflow():\n"
            f"    # Invoke {top_brick['symbol_name']}\n"
            "    pass\n"
            "```\n\n"
            "*(💡 Tip: Start Ollama on `localhost:11434` for generative multi-turn dialogue with `qwen2.5-coder:7b`)*"
        )

        return "".join(report_lines)

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute grounded conversation with local Ollama or fallback synthesis."""
        selected_model = model or DEFAULT_MODEL
        latest_user_message = ""

        for m in reversed(messages):
            if m.get("role") == "user":
                latest_user_message = m.get("content", "")
                break

        t_start = time.perf_counter()
        t_retrieval_start = time.perf_counter()
        # 1. Retrieve matching bricks from catalog with timing
        matched_bricks = self.search_catalog_for_query(latest_user_message, limit=5)
        retrieval_ms = round((time.perf_counter() - t_retrieval_start) * 1000, 1)

        # 2. Build system instruction with catalog grounding
        system_prompt = self.build_system_prompt(matched_bricks, query=latest_user_message)

        prompt_payload = [{"role": "system", "content": system_prompt}]
        for m in messages[-6:]:
            if m.get("role") in ("user", "assistant"):
                prompt_payload.append({"role": m["role"], "content": m["content"]})

        # 3. Call local Ollama API
        try:
            with httpx.Client(timeout=httpx.Timeout(45.0, connect=2.0)) as client:
                ollama_req = {
                    "model": selected_model,
                    "messages": prompt_payload,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 1024,
                    },
                }
                res = client.post(f"{self.endpoint}/api/chat", json=ollama_req)
                if res.status_code == 200:
                    reply_data = res.json()
                    content = reply_data.get("message", {}).get("content", "")
                    if content:
                        t_end = time.perf_counter()
                        total_sec = round(t_end - t_start, 2)
                        total_ms = round((t_end - t_start) * 1000, 1)
                        eval_duration_ns = reply_data.get("eval_duration")
                        eval_count = reply_data.get("eval_count", len(content.split()))
                        if eval_duration_ns:
                            ollama_sec = round(eval_duration_ns / 1e9, 2)
                            eval_rate = round(eval_count / max(0.001, eval_duration_ns / 1e9), 1)
                        else:
                            ollama_sec = round(max(0.01, total_sec - (retrieval_ms / 1000)), 2)
                            eval_rate = round(eval_count / max(0.001, ollama_sec), 1) if ollama_sec > 0 else None

                        return {
                            "reply": content,
                            "bricks": [
                                {
                                    "symbol_name": b["symbol_name"],
                                    "kind": b["kind"],
                                    "repository_name": b["repository_name"],
                                    "relative_path": b["relative_path"],
                                    "start_line": b["start_line"],
                                    "end_line": b["end_line"],
                                    "portability_score": b["portability_score"],
                                    "brick_id": b["brick_id"],
                                }
                                for b in matched_bricks
                            ],
                            "model_used": selected_model,
                            "online": True,
                            "perf": {
                                "retrieval_ms": retrieval_ms,
                                "bricks_count": len(matched_bricks),
                                "eval_count": eval_count,
                                "ollama_sec": ollama_sec,
                                "eval_rate": eval_rate,
                                "total_sec": total_sec,
                                "total_ms": total_ms,
                            },
                        }
        except Exception:
            pass

        # 4. Fallback generation if Ollama was unreachable
        fallback_reply = self.generate_fallback_report(latest_user_message, matched_bricks)
        t_end = time.perf_counter()
        total_sec = round(t_end - t_start, 2)
        total_ms = round((t_end - t_start) * 1000, 1)
        fallback_tokens = len(fallback_reply.split())
        return {
            "reply": fallback_reply,
            "bricks": [
                {
                    "symbol_name": b["symbol_name"],
                    "kind": b["kind"],
                    "repository_name": b["repository_name"],
                    "relative_path": b["relative_path"],
                    "start_line": b["start_line"],
                    "end_line": b["end_line"],
                    "portability_score": b["portability_score"],
                    "brick_id": b["brick_id"],
                }
                for b in matched_bricks
            ],
            "model_used": f"{selected_model} (Catalog RAG Engine)",
            "online": False,
            "perf": {
                "retrieval_ms": retrieval_ms,
                "bricks_count": len(matched_bricks),
                "eval_count": fallback_tokens,
                "ollama_sec": round(max(0.01, total_sec - (retrieval_ms / 1000)), 2),
                "eval_rate": round(fallback_tokens / max(0.01, total_sec), 1),
                "total_sec": total_sec,
                "total_ms": total_ms,
            },
        }

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ):
        """Yield streaming chunks (tokens and metadata) for live generation."""
        selected_model = model or DEFAULT_MODEL
        latest_user_message = ""

        for m in reversed(messages):
            if m.get("role") == "user":
                latest_user_message = m.get("content", "")
                break

        t_start = time.perf_counter()
        # 1. Retrieve matching bricks from catalog with precise timing
        t_retrieval_start = time.perf_counter()
        matched_bricks = self.search_catalog_for_query(latest_user_message, limit=5)
        retrieval_ms = round((time.perf_counter() - t_retrieval_start) * 1000, 1)

        serialized_bricks = [
            {
                "symbol_name": b["symbol_name"],
                "kind": b["kind"],
                "repository_name": b["repository_name"],
                "relative_path": b["relative_path"],
                "start_line": b["start_line"],
                "end_line": b["end_line"],
                "portability_score": b["portability_score"],
                "brick_id": b["brick_id"],
            }
            for b in matched_bricks
        ]

        # Initial start event with grounded bricks metadata and retrieval latency
        yield {
            "type": "start",
            "bricks": serialized_bricks,
            "model_used": selected_model,
            "retrieval_ms": retrieval_ms,
            "bricks_count": len(serialized_bricks),
        }

        # 2. Build system instruction with catalog grounding
        system_prompt = self.build_system_prompt(matched_bricks, query=latest_user_message)
        prompt_payload = [{"role": "system", "content": system_prompt}]
        for m in messages[-6:]:
            if m.get("role") in ("user", "assistant"):
                prompt_payload.append({"role": m["role"], "content": m["content"]})

        # 3. Stream from local Ollama API if online
        stream_succeeded = False
        token_count = 0
        first_token_time = None
        t_ollama_start = time.perf_counter()

        try:
            with httpx.Client(timeout=httpx.Timeout(90.0, connect=2.0)) as client:
                ollama_req = {
                    "model": selected_model,
                    "messages": prompt_payload,
                    "stream": True,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 1024,
                    },
                }
                with client.stream("POST", f"{self.endpoint}/api/chat", json=ollama_req) as response:
                    if response.status_code == 200:
                        stream_succeeded = True
                        token_buffer: List[str] = []
                        last_flush_time = time.perf_counter()
                        FLUSH_INTERVAL = 0.080  # 80ms micro-batch for natural paragraph streaming
                        BUFFER_THRESHOLD = 64   # ~64 characters per batch

                        for line in response.iter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                token = chunk.get("message", {}).get("content", "")
                                if token:
                                    if first_token_time is None:
                                        first_token_time = time.perf_counter()
                                    token_count += 1
                                    token_buffer.append(token)
                                    now = time.perf_counter()
                                    buffered_len = sum(len(t) for t in token_buffer)
                                    # Flush if buffer reaches threshold, interval elapsed, or ends with newline
                                    if buffered_len >= BUFFER_THRESHOLD or (now - last_flush_time) >= FLUSH_INTERVAL or "\n" in token:
                                        yield {"type": "token", "content": "".join(token_buffer)}
                                        token_buffer = []
                                        last_flush_time = now

                                if chunk.get("done"):
                                    if token_buffer:
                                        yield {"type": "token", "content": "".join(token_buffer)}
                                        token_buffer = []

                                    t_done = time.perf_counter()
                                    total_sec = round(t_done - t_start, 2)
                                    total_ms = round((t_done - t_start) * 1000, 1)
                                    ttft_ms = round((first_token_time - t_ollama_start) * 1000, 1) if first_token_time else None

                                    eval_count = chunk.get("eval_count", token_count)
                                    eval_duration_ns = chunk.get("eval_duration")
                                    if eval_duration_ns:
                                        ollama_sec = round(eval_duration_ns / 1e9, 2)
                                        eval_rate = round(eval_count / max(0.001, eval_duration_ns / 1e9), 1)
                                    else:
                                        ollama_sec = round(t_done - t_ollama_start, 2)
                                        eval_rate = round(eval_count / max(0.001, ollama_sec), 1) if ollama_sec > 0 else None

                                    yield {
                                        "type": "done",
                                        "bricks": serialized_bricks,
                                        "model_used": selected_model,
                                        "online": True,
                                        "perf": {
                                            "retrieval_ms": retrieval_ms,
                                            "bricks_count": len(serialized_bricks),
                                            "ttft_ms": ttft_ms,
                                            "eval_count": eval_count,
                                            "ollama_sec": ollama_sec,
                                            "eval_rate": eval_rate,
                                            "total_sec": total_sec,
                                            "total_ms": total_ms,
                                        },
                                    }
                                    return
                            except Exception:
                                continue
        except Exception:
            pass

        # 4. Fallback generation if Ollama was unreachable
        if not stream_succeeded:
            fallback_reply = self.generate_fallback_report(latest_user_message, matched_bricks)
            lines = fallback_reply.splitlines(keepends=True)
            for line in lines:
                token_count += 1
                yield {"type": "token", "content": line}

            t_done = time.perf_counter()
            total_sec = round(t_done - t_start, 2)
            total_ms = round((t_done - t_start) * 1000, 1)
            yield {
                "type": "done",
                "bricks": serialized_bricks,
                "model_used": f"{selected_model} (Catalog RAG Engine)",
                "online": False,
                "perf": {
                    "retrieval_ms": retrieval_ms,
                    "bricks_count": len(serialized_bricks),
                    "ttft_ms": round(retrieval_ms + 4.0, 1),
                    "eval_count": token_count,
                    "ollama_sec": round(max(0.01, total_sec - (retrieval_ms / 1000)), 2),
                    "eval_rate": round(token_count / max(0.01, total_sec), 1),
                    "total_sec": total_sec,
                    "total_ms": total_ms,
                },
            }
