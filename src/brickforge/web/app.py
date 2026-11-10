"""FastAPI application powering the BrickForge Catalog Explorer web interface."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from brickforge.web.chat import BrickForgeChatEngine, DEFAULT_MODEL
from brickforge.web.projects import (
    get_all_projects,
    normalize_language_badge,
    detect_file_language,
)
from brickforge.web.initiatives import (
    INITIATIVES_REGISTRY,
    get_all_initiatives_with_rollups,
    classify_project_initiative,
    ensure_initiatives_schema,
)

DEFAULT_DB_PATH = Path("data/brickforge.db")


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    model: Optional[str] = None


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Create an optimized SQLite connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


TOPIC_SQL_EXPR = """
CASE
    WHEN s.relative_path LIKE '%test%' OR s.relative_path LIKE '%spec%' OR s.relative_path LIKE '%mock%' 
         OR s.relative_path LIKE '%benchmark%' OR b.symbol_name LIKE 'test_%' OR b.symbol_name LIKE 'Test%' THEN 'Testing & Benchmarks'
    WHEN s.relative_path LIKE '%agent%' OR s.relative_path LIKE '%llm%' OR s.relative_path LIKE '%prompt%' 
         OR s.relative_path LIKE '%chat%' OR s.relative_path LIKE '%ai%' OR b.symbol_name LIKE '%agent%' 
         OR b.symbol_name LIKE '%llm%' OR b.symbol_name LIKE '%prompt%' THEN 'AI & LLM / Agents'
    WHEN s.relative_path LIKE '%audio%' OR s.relative_path LIKE '%voice%' OR s.relative_path LIKE '%speech%' 
         OR s.relative_path LIKE '%stt%' OR s.relative_path LIKE '%tts%' OR b.symbol_name LIKE '%audio%' 
         OR b.symbol_name LIKE '%voice%' THEN 'Audio & Speech / DSP'
    WHEN s.relative_path LIKE '%api%' OR s.relative_path LIKE '%server%' OR s.relative_path LIKE '%http%' 
         OR s.relative_path LIKE '%router%' OR s.relative_path LIKE '%client%' OR b.symbol_name LIKE '%api%' 
         OR b.symbol_name LIKE '%router%' THEN 'Web & APIs / Network'
    WHEN s.relative_path LIKE '%/db/%' OR s.relative_path LIKE '%sql%' OR s.relative_path LIKE '%database%' 
         OR s.relative_path LIKE '%storage%' OR s.relative_path LIKE '%cache%' OR b.symbol_name LIKE '%database%' 
         OR b.symbol_name LIKE '%sql%' OR b.symbol_name LIKE '%repo%' THEN 'Data & Database / Storage'
    WHEN s.relative_path LIKE '%doc%' OR s.relative_path LIKE '%pdf%' OR s.relative_path LIKE '%latex%' 
         OR s.relative_path LIKE '%markdown%' OR s.relative_path LIKE '%parser%' THEN 'Docs, PDF & Parsers'
    WHEN s.relative_path LIKE '%auth%' OR s.relative_path LIKE '%sec%' OR s.relative_path LIKE '%crypto%' 
         OR s.relative_path LIKE '%token%' THEN 'Security & Auth'
    WHEN s.relative_path LIKE '%ui%' OR s.relative_path LIKE '%view%' OR s.relative_path LIKE '%frontend%' 
         OR s.relative_path LIKE '%app%' OR s.relative_path LIKE '%component%' THEN 'UI & Frontend'
    ELSE 'Core & Utilities'
END
"""

TOPIC_ICONS = {
    "All": "grid",
    "AI & LLM / Agents": "bot",
    "Testing & Benchmarks": "check-circle-2",
    "Core & Utilities": "wrench",
    "UI & Frontend": "layout",
    "Data & Database / Storage": "database",
    "Docs, PDF & Parsers": "file-text",
    "Web & APIs / Network": "globe",
    "Audio & Speech / DSP": "mic",
    "Security & Auth": "shield-check",
}


def _build_bricks_filters(
    query: Optional[str],
    topic: Optional[str],
    kind: Optional[str],
    repo: Optional[str],
    language: Optional[str],
    initiative_project_keys: Optional[List[str]] = None,
) -> Tuple[List[str], List[Any]]:
    where_clauses: List[str] = []
    params: List[Any] = []

    # Filter by initiative project keys if provided
    if initiative_project_keys is not None:
        if not initiative_project_keys:
            where_clauses.append("1 = 0")  # Empty initiative match
        else:
            proj_clauses = []
            for pkey in initiative_project_keys:
                if ":" in pkey:
                    r_id, p_name = pkey.split(":", 1)
                    proj_clauses.append("(s.repository_id = ? AND (s.relative_path LIKE ? OR s.relative_path LIKE ?))")
                    params.extend([r_id, f"{p_name}/%", f"{p_name}\\%"])
                else:
                    proj_clauses.append("(s.relative_path LIKE ? OR s.relative_path LIKE ?)")
                    params.extend([f"{pkey}/%", f"{pkey}\\%"])
            where_clauses.append(f"({' OR '.join(proj_clauses)})")

    # Full text search or LIKE
    if query and query.strip():
        clean_q = query.strip()
        fts_param = "".join(c for c in clean_q if c.isalnum() or c in (" ", "_", "-")).strip()
        if fts_param:
            where_clauses.append(
                """
                b.row_id IN (
                    SELECT rowid FROM bricks_fts 
                    WHERE bricks_fts MATCH ?
                )
                """
            )
            params.append(f'"{fts_param}"*')
        else:
            where_clauses.append("(b.symbol_name LIKE ? OR b.signature LIKE ?)")
            params.extend([f"%{clean_q}%", f"%{clean_q}%"])

    # Topic filter
    if topic and topic.strip() and topic != "All":
        where_clauses.append(f"({TOPIC_SQL_EXPR}) = ?")
        params.append(topic.strip())

    # Kind filter
    if kind and kind.strip() and kind != "all":
        where_clauses.append("b.kind = ?")
        params.append(kind.strip())

    # Repository filter
    if repo and repo.strip() and repo != "all":
        where_clauses.append("s.repository_id = ?")
        params.append(repo.strip())

    # Language filter
    if language and language.strip() and language != "all":
        lang_val = language.strip().lower()
        if lang_val in ("py", "python"):
            where_clauses.append("(b.language = 'python' OR s.relative_path LIKE '%.py')")
        elif lang_val in ("ts", "typescript"):
            where_clauses.append("(b.language = 'typescript' OR s.relative_path LIKE '%.ts')")
        elif lang_val in ("tsx", "typescript-react"):
            where_clauses.append("(b.language = 'typescript-react' OR s.relative_path LIKE '%.tsx')")
        elif lang_val in ("js", "javascript"):
            where_clauses.append("(b.language = 'javascript' OR s.relative_path LIKE '%.js' OR s.relative_path LIKE '%.mjs' OR s.relative_path LIKE '%.cjs')")
        elif lang_val in ("cs", "csharp"):
            where_clauses.append("(b.language = 'csharp' OR s.relative_path LIKE '%.cs')")
        elif lang_val in ("rs", "rust"):
            where_clauses.append("(b.language = 'rust' OR s.relative_path LIKE '%.rs')")
        elif lang_val in ("cpp", "c++"):
            where_clauses.append("(b.language = 'cpp' OR s.relative_path LIKE '%.cpp' OR s.relative_path LIKE '%.hpp' OR s.relative_path LIKE '%.cc')")
        elif lang_val in ("c",):
            where_clauses.append("(b.language = 'c' OR s.relative_path LIKE '%.c' OR s.relative_path LIKE '%.h')")
        elif lang_val in ("go", "golang"):
            where_clauses.append("(b.language = 'go' OR s.relative_path LIKE '%.go')")
        elif lang_val in ("java",):
            where_clauses.append("(b.language = 'java' OR s.relative_path LIKE '%.java')")
        else:
            where_clauses.append("(b.language = ? OR s.relative_path LIKE ?)")
            params.extend([lang_val, f"%.{lang_val}"])

    return where_clauses, params


def create_app(db_path: Optional[Union[str, Path]] = None) -> FastAPI:
    resolved_db = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not resolved_db.is_absolute():
        project_root = Path(__file__).parent.parent.parent.parent
        resolved_db = (project_root / resolved_db).resolve()

    app = FastAPI(
        title="BrickForge Catalog Explorer",
        description="Sovereign AST Code Intelligence & Composable Component Registry UI",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    template_path = Path(__file__).parent / "templates" / "index.html"

    @app.get("/", response_class=HTMLResponse)
    @app.get("/catalog", response_class=HTMLResponse)
    @app.get("/chat", response_class=HTMLResponse)
    @app.get("/brickforge", response_class=HTMLResponse)
    @app.get("/brickforge/catalog", response_class=HTMLResponse)
    @app.get("/brickforge/chat", response_class=HTMLResponse)
    def index():
        if not template_path.exists():
            return HTMLResponse("<h1>BrickForge UI template not found</h1>", status_code=500)
        return HTMLResponse(template_path.read_text(encoding="utf-8"))

    @app.get("/service-worker.js")
    @app.get("/brickforge/service-worker.js")
    def service_worker():
        """Serve an empty no-op service worker to silence PWA / browser service-worker lookup 404s."""
        from fastapi.responses import Response
        return Response(content="// BrickForge no-op service worker\n", media_type="application/javascript")

    @app.get("/api/stats")
    @app.get("/brickforge/api/stats")
    def get_stats():
        if not resolved_db.exists():
            return {"error": "Database not found", "total_bricks": 0}

        with get_db_connection(resolved_db) as conn:
            cursor = conn.cursor()
            total_bricks = cursor.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
            total_files = cursor.execute("SELECT COUNT(*) FROM source_files;").fetchone()[0]
            total_repos = cursor.execute("SELECT COUNT(*) FROM repositories;").fetchone()[0]

            cursor.execute("SELECT kind, COUNT(*) FROM code_bricks GROUP BY kind;")
            by_kind = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT language, COUNT(*) FROM code_bricks GROUP BY language;")
            by_language = {row[0]: row[1] for row in cursor.fetchall()}

            projects = get_all_projects(conn)

            return {
                "total_bricks": total_bricks,
                "total_files": total_files,
                "total_repositories": total_repos,
                "total_projects": len(projects),
                "by_kind": by_kind,
                "by_language": by_language,
                "top_projects": [
                    {
                        "project_name": p["symbol_name"],
                        "repository_name": p["repository_name"],
                        "file_count": p["file_count"],
                        "brick_count": p["brick_count"],
                        "class_count": p["class_count"],
                        "function_count": p["function_count"],
                        "method_count": p["method_count"],
                        "languages": p["languages"],
                        "language_badges": p["language_badges"],
                        "ai_summary": p["ai_summary"],
                    }
                    for p in projects[:15]
                ],
                "database_path": str(resolved_db),
            }

    @app.get("/api/categories")
    @app.get("/brickforge/api/categories")
    def get_categories():
        if not resolved_db.exists():
            return {"topics": [], "kinds": [], "repositories": [], "languages": [], "projects": []}

        with get_db_connection(resolved_db) as conn:
            cursor = conn.cursor()

            # Thematic topics
            topic_query = f"""
            SELECT {TOPIC_SQL_EXPR} AS topic, COUNT(b.row_id) as count
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            GROUP BY topic
            ORDER BY count DESC;
            """
            cursor.execute(topic_query)
            topics = [
                {
                    "name": row["topic"],
                    "count": row["count"],
                    "icon": TOPIC_ICONS.get(row["topic"], "box"),
                }
                for row in cursor.fetchall()
            ]

            projects = get_all_projects(conn)

            # Kinds (functions, classes, methods + project level)
            cursor.execute(
                """
                SELECT kind, COUNT(*) as count 
                FROM code_bricks 
                GROUP BY kind 
                ORDER BY count DESC;
                """
            )
            kinds = [{"name": row["kind"], "count": row["count"]} for row in cursor.fetchall()]
            kinds.append({"name": "project", "count": len(projects)})

            # Repositories
            cursor.execute(
                """
                SELECT r.id, r.name, COUNT(b.row_id) as count
                FROM repositories r
                LEFT JOIN source_files s ON s.repository_id = r.id
                LEFT JOIN code_bricks b ON b.file_id = s.row_id
                GROUP BY r.id, r.name
                ORDER BY count DESC;
                """
            )
            repositories = [
                {"id": row["id"], "name": row["name"], "count": row["count"] or 0}
                for row in cursor.fetchall()
            ]

            # Languages
            cursor.execute(
                """
                SELECT language, COUNT(*) as count
                FROM code_bricks
                GROUP BY language
                ORDER BY count DESC;
                """
            )
            languages = [
                {
                    "name": row["language"],
                    "code": normalize_language_badge(row["language"]),
                    "count": row["count"],
                }
                for row in cursor.fetchall()
            ]

            total_bricks = cursor.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]

            # Strategic Initiatives & Domains
            initiatives = get_all_initiatives_with_rollups(conn, projects)

            return {
                "total_bricks": total_bricks,
                "total_projects": len(projects),
                "total_initiatives": len(initiatives),
                "topics": topics,
                "kinds": kinds,
                "repositories": repositories,
                "languages": languages,
                "initiatives": initiatives,
                "projects": [
                    {
                        "name": p["symbol_name"],
                        "repository_id": p["repository_id"],
                        "brick_count": p["brick_count"],
                        "file_count": p["file_count"],
                        "initiative_id": p.get("initiative_id"),
                        "initiative_name": p.get("initiative_name"),
                    }
                    for p in projects[:30]
                ],
            }

    @app.get("/api/initiatives")
    @app.get("/brickforge/api/initiatives")
    def get_initiatives():
        if not resolved_db.exists():
            return []
        with get_db_connection(resolved_db) as conn:
            projects = get_all_projects(conn)
            return get_all_initiatives_with_rollups(conn, projects)

    @app.get("/api/initiative/{initiative_id}")
    @app.get("/brickforge/api/initiative/{initiative_id}")
    def get_initiative_detail(initiative_id: str):
        if not resolved_db.exists():
            raise HTTPException(status_code=404, detail="Database not found")
        with get_db_connection(resolved_db) as conn:
            projects = get_all_projects(conn)
            initiatives = get_all_initiatives_with_rollups(conn, projects)
            target = next((ini for ini in initiatives if ini["id"] == initiative_id or ini["slug"] == initiative_id), None)
            if not target:
                raise HTTPException(status_code=404, detail=f"Initiative '{initiative_id}' not found")
            return target

    @app.get("/api/bricks")
    @app.get("/brickforge/api/bricks")
    def search_bricks(
        query: Optional[str] = None,
        topic: Optional[str] = None,
        kind: Optional[str] = None,
        repo: Optional[str] = None,
        language: Optional[str] = None,
        initiative: Optional[str] = None,
        sort: str = "portability_desc",
        page: int = 1,
        page_size: int = 24,
    ):
        if not resolved_db.exists():
            return {"total": 0, "page": page, "page_size": page_size, "items": []}

        with get_db_connection(resolved_db) as conn:
            ini_proj_keys: Optional[List[str]] = None
            if initiative and initiative.strip() and initiative != "all":
                ini_key = initiative.strip()
                projects = get_all_projects(conn)
                inis = get_all_initiatives_with_rollups(conn, projects)
                match_ini = next((x for x in inis if x["id"] == ini_key or x["slug"] == ini_key), None)
                if match_ini:
                    ini_proj_keys = [p["project_key"] for p in match_ini.get("projects", [])]
                else:
                    ini_proj_keys = []

            # First-class Project Level support: api/bricks?kind=project
            if kind and kind.strip().lower() == "project":
                projects = get_all_projects(conn)
                # Compute initiative rollups to attach initiative tags
                get_all_initiatives_with_rollups(conn, projects)

                # Initiative filter
                if ini_proj_keys is not None:
                    projects = [p for p in projects if f"{p['repository_id']}:{p['symbol_name']}" in ini_proj_keys]

                # Repository filter
                if repo and repo.strip() and repo != "all":
                    projects = [p for p in projects if p["repository_id"] == repo.strip()]

                # Language filter
                if language and language.strip() and language != "all":
                    target_lang = language.strip().lower()
                    projects = [
                        p for p in projects 
                        if target_lang in [l.lower() for l in p.get("languages", [])]
                        or target_lang in [b.lower() for b in p.get("language_badges", [])]
                    ]

                # Query filter (matches project name or ai_summary)
                if query and query.strip():
                    q_lower = query.strip().lower()
                    projects = [
                        p for p in projects 
                        if q_lower in p["symbol_name"].lower() or q_lower in p.get("ai_summary", "").lower()
                    ]

                # Sorting
                if sort == "name_asc":
                    projects.sort(key=lambda x: x["symbol_name"].lower())
                elif sort == "name_desc":
                    projects.sort(key=lambda x: x["symbol_name"].lower(), reverse=True)
                elif sort == "complexity_desc":
                    projects.sort(key=lambda x: x.get("file_count", 0), reverse=True)
                else:  # portability_desc or default
                    projects.sort(key=lambda x: x.get("brick_count", 0), reverse=True)

                total_items = len(projects)
                offset = (page - 1) * page_size
                page_items = projects[offset : offset + page_size]

                return {
                    "total": total_items,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_items + page_size - 1) // page_size if total_items > 0 else 1,
                    "items": page_items,
                }

            cursor = conn.cursor()
            where_clauses, params = _build_bricks_filters(query, topic, kind, repo, language, initiative_project_keys=ini_proj_keys)
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Count total matching
            count_sql = f"""
            SELECT COUNT(b.row_id)
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            {where_sql};
            """
            total_items = cursor.execute(count_sql, params).fetchone()[0]

            # Sorting
            sort_map = {
                "portability_desc": "b.portability_score DESC, b.row_id ASC",
                "name_asc": "b.symbol_name ASC",
                "name_desc": "b.symbol_name DESC",
                "complexity_desc": "b.cyclomatic_complexity DESC",
                "recent": "b.indexed_at DESC",
            }
            order_clause = sort_map.get(sort, "b.portability_score DESC, b.row_id ASC")

            # Offset pagination
            offset = (page - 1) * page_size
            data_sql = f"""
            SELECT 
                b.row_id,
                b.id AS brick_id,
                b.symbol_name,
                b.qualified_name,
                b.kind,
                b.language,
                b.visibility,
                b.signature,
                b.docstring,
                b.is_async,
                b.cyclomatic_complexity,
                b.portability_score,
                b.start_line,
                b.end_line,
                s.repository_id,
                s.relative_path,
                s.loc,
                {TOPIC_SQL_EXPR} AS topic
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            {where_sql}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?;
            """
            cursor.execute(data_sql, [*params, page_size, offset])
            rows = cursor.fetchall()

            items = []
            for r in rows:
                rel = r["relative_path"] or ""
                proj = rel.split("/")[0] if "/" in rel else (rel.split("\\")[0] if "\\" in rel else "root")
                lang_badge = normalize_language_badge(r["language"], rel)

                items.append({
                    "row_id": r["row_id"],
                    "brick_id": r["brick_id"],
                    "symbol_name": r["symbol_name"],
                    "qualified_name": r["qualified_name"],
                    "kind": r["kind"],
                    "language": r["language"] or "python",
                    "language_code": lang_badge,
                    "language_badge": lang_badge,
                    "project": proj,
                    "visibility": r["visibility"],
                    "signature": r["signature"] or f"{r['kind']} {r['symbol_name']}",
                    "docstring": (r["docstring"] or "").strip()[:180],
                    "has_docstring": bool(r["docstring"]),
                    "is_async": bool(r["is_async"]),
                    "cyclomatic_complexity": r["cyclomatic_complexity"] or 1,
                    "portability_score": round(float(r["portability_score"] or 1.0), 2),
                    "start_line": r["start_line"],
                    "end_line": r["end_line"],
                    "line_count": (r["end_line"] - r["start_line"] + 1) if r["end_line"] and r["start_line"] else (r["loc"] or 0),
                    "repository_id": r["repository_id"],
                    "relative_path": r["relative_path"],
                    "topic": r["topic"],
                })

            return {
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_items + page_size - 1) // page_size if total_items > 0 else 1,
                "items": items,
            }

    @app.get("/api/bricks/export")
    @app.get("/brickforge/api/bricks/export")
    def export_bricks(
        query: Optional[str] = None,
        topic: Optional[str] = None,
        kind: Optional[str] = None,
        repo: Optional[str] = None,
        language: Optional[str] = None,
        initiative: Optional[str] = None,
        sort: str = "portability_desc",
        limit: int = 5000,
    ):
        if not resolved_db.exists():
            return {
                "version": "1.0",
                "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_matches": 0,
                "exported_count": 0,
                "filters": {
                    "query": query,
                    "topic": topic,
                    "kind": kind,
                    "repo": repo,
                    "language": language,
                    "initiative": initiative,
                    "sort": sort,
                },
                "items": [],
            }

        with get_db_connection(resolved_db) as conn:
            ini_proj_keys: Optional[List[str]] = None
            if initiative and initiative.strip() and initiative != "all":
                ini_key = initiative.strip()
                projects = get_all_projects(conn)
                inis = get_all_initiatives_with_rollups(conn, projects)
                match_ini = next((x for x in inis if x["id"] == ini_key or x["slug"] == ini_key), None)
                if match_ini:
                    ini_proj_keys = [p["project_key"] for p in match_ini.get("projects", [])]
                else:
                    ini_proj_keys = []

            # First-class Project Level support: api/bricks/export?kind=project
            if kind and kind.strip().lower() == "project":
                projects = get_all_projects(conn)
                get_all_initiatives_with_rollups(conn, projects)

                if ini_proj_keys is not None:
                    projects = [p for p in projects if f"{p['repository_id']}:{p['symbol_name']}" in ini_proj_keys]

                if repo and repo.strip() and repo != "all":
                    projects = [p for p in projects if p["repository_id"] == repo.strip()]

                if language and language.strip() and language != "all":
                    target_lang = language.strip().lower()
                    projects = [
                        p for p in projects 
                        if target_lang in [l.lower() for l in p.get("languages", [])]
                        or target_lang in [b.lower() for b in p.get("language_badges", [])]
                    ]

                if query and query.strip():
                    q_lower = query.strip().lower()
                    projects = [
                        p for p in projects 
                        if q_lower in p["symbol_name"].lower() or q_lower in p.get("ai_summary", "").lower()
                    ]

                if sort == "name_asc":
                    projects.sort(key=lambda x: x["symbol_name"].lower())
                elif sort == "name_desc":
                    projects.sort(key=lambda x: x["symbol_name"].lower(), reverse=True)
                elif sort == "complexity_desc":
                    projects.sort(key=lambda x: x.get("file_count", 0), reverse=True)
                else:
                    projects.sort(key=lambda x: x.get("brick_count", 0), reverse=True)

                total_items = len(projects)
                export_items = projects[:limit]

                return {
                    "version": "1.0",
                    "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "total_matches": total_items,
                    "exported_count": len(export_items),
                    "filters": {
                        "query": query,
                        "topic": topic,
                        "kind": kind,
                        "repo": repo,
                        "language": language,
                        "initiative": initiative,
                        "sort": sort,
                    },
                    "items": export_items,
                }

            cursor = conn.cursor()
            where_clauses, params = _build_bricks_filters(query, topic, kind, repo, language, initiative_project_keys=ini_proj_keys)
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            count_sql = f"""
            SELECT COUNT(b.row_id)
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            {where_sql};
            """
            total_items = cursor.execute(count_sql, params).fetchone()[0]

            sort_map = {
                "portability_desc": "b.portability_score DESC, b.row_id ASC",
                "name_asc": "b.symbol_name ASC",
                "name_desc": "b.symbol_name DESC",
                "complexity_desc": "b.cyclomatic_complexity DESC",
                "recent": "b.indexed_at DESC",
            }
            order_clause = sort_map.get(sort, "b.portability_score DESC, b.row_id ASC")

            data_sql = f"""
            SELECT 
                b.row_id,
                b.id AS brick_id,
                b.symbol_name,
                b.qualified_name,
                b.kind,
                b.language,
                b.visibility,
                b.signature,
                b.docstring,
                b.is_async,
                b.cyclomatic_complexity,
                b.portability_score,
                b.start_line,
                b.end_line,
                s.repository_id,
                s.relative_path,
                s.loc,
                {TOPIC_SQL_EXPR} AS topic
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            {where_sql}
            ORDER BY {order_clause}
            LIMIT ?;
            """
            cursor.execute(data_sql, [*params, limit])
            rows = cursor.fetchall()

            items = []
            for r in rows:
                rel = r["relative_path"] or ""
                proj = rel.split("/")[0] if "/" in rel else (rel.split("\\")[0] if "\\" in rel else "root")
                lang_badge = normalize_language_badge(r["language"], rel)

                items.append({
                    "brick_id": r["brick_id"],
                    "symbol_name": r["symbol_name"],
                    "qualified_name": r["qualified_name"],
                    "kind": r["kind"],
                    "language": r["language"] or "python",
                    "language_badge": lang_badge,
                    "project": proj,
                    "visibility": r["visibility"],
                    "signature": r["signature"] or f"{r['kind']} {r['symbol_name']}",
                    "docstring": (r["docstring"] or "").strip(),
                    "is_async": bool(r["is_async"]),
                    "cyclomatic_complexity": r["cyclomatic_complexity"] or 1,
                    "portability_score": round(float(r["portability_score"] or 1.0), 2),
                    "start_line": r["start_line"],
                    "end_line": r["end_line"],
                    "line_count": (r["end_line"] - r["start_line"] + 1) if r["end_line"] and r["start_line"] else (r["loc"] or 0),
                    "repository_id": r["repository_id"],
                    "relative_path": r["relative_path"],
                    "topic": r["topic"],
                })

            return {
                "version": "1.0",
                "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_matches": total_items,
                "exported_count": len(items),
                "filters": {
                    "query": query,
                    "topic": topic,
                    "kind": kind,
                    "repo": repo,
                    "language": language,
                    "initiative": initiative,
                    "sort": sort,
                },
                "items": items,
            }

    @app.get("/api/brick/{brick_id}")
    @app.get("/brickforge/api/brick/{brick_id}")
    def get_brick_detail(brick_id: str):
        if not resolved_db.exists():
            raise HTTPException(status_code=404, detail="Database not found")

        # Project level detail request: project:repo_id:project_name
        if str(brick_id).startswith("project:"):
            parts = str(brick_id).split(":", 2)
            repo_id = parts[1] if len(parts) > 1 else ""
            proj_name = parts[2] if len(parts) > 2 else ""

            with get_db_connection(resolved_db) as conn:
                projects = get_all_projects(conn)
                get_all_initiatives_with_rollups(conn, projects)
                target_proj = next(
                    (p for p in projects if p["symbol_name"] == proj_name and (not repo_id or p["repository_id"] == repo_id)),
                    None,
                )
                if not target_proj:
                    raise HTTPException(status_code=404, detail=f"Project '{proj_name}' not found")

                cursor = conn.cursor()
                sample_bricks_sql = f"""
                SELECT 
                    b.id as brick_id,
                    b.symbol_name,
                    b.kind,
                    b.language,
                    b.signature,
                    b.start_line,
                    b.end_line,
                    b.portability_score,
                    s.relative_path
                FROM code_bricks b
                JOIN source_files s ON b.file_id = s.row_id
                WHERE s.repository_id = ? AND (
                    s.relative_path LIKE ? OR s.relative_path LIKE ?
                )
                ORDER BY b.portability_score DESC, b.row_id ASC
                LIMIT 18;
                """
                cursor.execute(sample_bricks_sql, (target_proj["repository_id"], f"{proj_name}/%", f"{proj_name}\\%"))
                contained_bricks = [dict(row) for row in cursor.fetchall()]

                # Architectural summary code block
                manifest_lines = [
                    f"# ==============================================================================",
                    f"# PROJECT DOSSIER: {target_proj['symbol_name']}",
                    f"# Repository: {target_proj['repository_name']} ({target_proj['repository_id']})",
                    f"# Total Source Files: {target_proj['file_count']:,}",
                    f"# Indexed Code Bricks: {target_proj['brick_count']:,} ({target_proj['class_count']} Classes, {target_proj['function_count']} Functions, {target_proj['method_count']} Methods)",
                    f"# Detected Languages: {', '.join(target_proj['languages'])} ({', '.join(target_proj['language_badges'])})",
                    f"# Mean Portability Score: {target_proj['portability_score']}",
                    f"# ==============================================================================",
                    f"",
                    f'"""',
                    f'AI Project Intent & Reusability Overview:',
                    f'{target_proj["ai_summary"]}',
                    f'"""',
                    f"",
                    f"# Top Indexed Bricks in this Project:",
                ]
                for cb in contained_bricks:
                    manifest_lines.append(f"# • {cb['kind']} {cb['symbol_name']} in {cb['relative_path']} (L{cb['start_line']}-L{cb['end_line']})")

                return {
                    "row_id": -1,
                    "brick_id": target_proj["brick_id"],
                    "symbol_name": target_proj["symbol_name"],
                    "qualified_name": target_proj["qualified_name"],
                    "kind": "project",
                    "language": target_proj["language"],
                    "language_code": target_proj["language_code"],
                    "languages": target_proj["languages"],
                    "language_badges": target_proj["language_badges"],
                    "signature": target_proj["signature"],
                    "docstring": target_proj["ai_summary"],
                    "ai_summary": target_proj["ai_summary"],
                    "source_code": "\n".join(manifest_lines),
                    "portability_score": target_proj["portability_score"],
                    "cyclomatic_complexity": 1,
                    "is_async": False,
                    "start_line": 1,
                    "end_line": target_proj["file_count"],
                    "line_count": target_proj["file_count"],
                    "file_count": target_proj["file_count"],
                    "brick_count": target_proj["brick_count"],
                    "class_count": target_proj["class_count"],
                    "function_count": target_proj["function_count"],
                    "method_count": target_proj["method_count"],
                    "repository_id": target_proj["repository_id"],
                    "repository_name": target_proj["repository_name"],
                    "relative_path": target_proj["relative_path"],
                    "topic": "Project Dossier",
                    "dependencies": [
                        {
                            "target_symbol": cb["symbol_name"],
                            "type": cb["kind"],
                            "package_name": cb["relative_path"],
                            "is_external": False,
                        }
                        for cb in contained_bricks
                    ],
                }

        with get_db_connection(resolved_db) as conn:
            cursor = conn.cursor()
            query = f"""
            SELECT 
                b.*,
                s.repository_id,
                s.relative_path,
                s.loc,
                r.name AS repository_name,
                r.root_path AS repository_root,
                {TOPIC_SQL_EXPR} AS topic
            FROM code_bricks b
            JOIN source_files s ON b.file_id = s.row_id
            JOIN repositories r ON s.repository_id = r.id
            WHERE b.id = ? OR b.row_id = ?;
            """
            # Allow query by either uuid id or row_id
            row_id_val = int(brick_id) if str(brick_id).isdigit() else -1
            row = cursor.execute(query, (str(brick_id), row_id_val)).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Code brick not found")

            # Fetch internal dependencies
            cursor.execute(
                """
                SELECT 
                    COALESCE(tb.symbol_name, bd.unresolved_symbol) AS target_symbol,
                    bd.dependency_type
                FROM brick_dependencies bd
                LEFT JOIN code_bricks tb ON bd.target_row_id = tb.row_id
                WHERE bd.source_row_id = ?;
                """,
                (row["row_id"],),
            )
            deps = [
                {
                    "target_symbol": d["target_symbol"] or "unknown",
                    "type": d["dependency_type"],
                    "package_name": "",
                    "is_external": False,
                }
                for d in cursor.fetchall()
            ]

            # Fetch external packages
            cursor.execute(
                """
                SELECT package_name, ecosystem, import_statement
                FROM external_packages
                WHERE brick_row_id = ?;
                """,
                (row["row_id"],),
            )
            for ep in cursor.fetchall():
                deps.append({
                    "target_symbol": ep["package_name"],
                    "type": ep["ecosystem"] or "pip",
                    "package_name": ep["package_name"],
                    "is_external": True,
                })

            # Parse parameters / contract hints from signature
            contract = {
                "row_id": row["row_id"],
                "brick_id": row["id"],
                "symbol_name": row["symbol_name"],
                "qualified_name": row["qualified_name"],
                "kind": row["kind"],
                "language": row["language"],
                "signature": row["signature"],
                "docstring": row["docstring"],
                "source_code": row["source_code"],
                "portability_score": row["portability_score"],
                "cyclomatic_complexity": row["cyclomatic_complexity"],
                "is_async": bool(row["is_async"]),
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "repository_id": row["repository_id"],
                "repository_name": row["repository_name"],
                "relative_path": row["relative_path"],
                "topic": row["topic"],
                "dependencies": deps,
            }

            return contract

    chat_engine = BrickForgeChatEngine(resolved_db)

    @app.get("/api/chat/models")
    @app.get("/brickforge/api/chat/models")
    def get_chat_models():
        models, is_online = chat_engine.get_available_models()
        # On remote production host (e.g. Ionos VPS where lightweight qwen3:1.7b is installed),
        # prioritize qwen3:1.7b as default; on local development machines, prefer qwen2.5-coder:7b
        # or the first available model.
        preferred_default = DEFAULT_MODEL
        if "qwen3:1.7b" in models:
            preferred_default = "qwen3:1.7b"
        elif DEFAULT_MODEL in models:
            preferred_default = DEFAULT_MODEL
        elif models:
            preferred_default = models[0]

        return {
            "models": models,
            "online": is_online,
            "default": preferred_default,
        }

    @app.post("/api/chat")
    @app.post("/brickforge/api/chat")
    def chat_conversation(req: ChatRequest):
        messages = list(req.history or [])
        messages.append({"role": "user", "content": req.message})
        response = chat_engine.chat(messages, model=req.model)
        return response

    @app.post("/api/chat/stream")
    @app.post("/brickforge/api/chat/stream")
    def chat_conversation_stream(req: ChatRequest):
        messages = list(req.history or [])
        messages.append({"role": "user", "content": req.message})

        def event_generator():
            for chunk in chat_engine.chat_stream(messages, model=req.model):
                yield f"data: {json.dumps(chunk)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    app.include_router(router, prefix="/brickforge/api", tags=["brickforge"])
    return app

