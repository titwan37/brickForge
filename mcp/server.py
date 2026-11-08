"""BrickForge MCP Server — Exposes AST Code Bricks, Contracts & Initiatives to CodBot and IDEs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

# Ensure BrickForge logs go strictly to stderr so stdio MCP JSON-RPC is never corrupted
logging.basicConfig(
    level=logging.INFO,
    format="[BrickForge-MCP %(asctime)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("brickforge.mcp")

mcp = FastMCP(
    "BrickForge-Code-Catalog",
    instructions=(
        "Sovereign AST Code Intelligence & Composable Component Registry. "
        "Use `search_code_bricks` first to find reusable functions/classes across repositories, "
        "`inspect_brick_contract` to check signatures/dependencies cheaply, and "
        "`extract_composable_bundle` to pull self-contained source code for adaptation."
    ),
)

_DB_PATH: Path = Path("data/brickforge.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")  # Strict read-only guard for MCP queries
    return conn


# ==============================================================================
# 1. MCP RESOURCES (Direct URI Reads)
# ==============================================================================

@mcp.resource("brick://catalog/stats")
def resource_catalog_stats() -> str:
    """Overall catalog health, counts, and language breakdown."""
    return json.dumps(get_catalog_stats(), indent=2)


@mcp.resource("brick://bricks/{brick_id}/contract")
def resource_brick_contract(brick_id: str) -> str:
    """Lightweight AST contract, provenance, and dependencies without source body."""
    return json.dumps(inspect_brick_contract(brick_id=brick_id), indent=2)


@mcp.resource("brick://bricks/{brick_id}/source")
def resource_brick_source(brick_id: str) -> str:
    """Exact AST-sliced source implementation for a known brick_id."""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT b.id AS brick_id, b.symbol_name, b.qualified_name, b.kind, b.language,
                   b.signature, b.source_code, b.start_line, b.end_line,
                   s.repository_id, s.relative_path
            FROM code_bricks b
            JOIN source_files s ON s.row_id = b.file_id
            WHERE b.id = ? OR CAST(b.row_id AS TEXT) = ?
            LIMIT 1;
            """,
            (brick_id, brick_id),
        ).fetchone()
        if not row:
            return json.dumps({"error": f"Brick '{brick_id}' not found."})
        return json.dumps(dict(row), indent=2)


# ==============================================================================
# 2. MCP TOOLS (Parameterized Discovery, Contract Inspection & Bundling)
# ==============================================================================

@mcp.tool()
def get_catalog_stats() -> Dict[str, Any]:
    """Return global counts of indexed repositories, source files, code bricks, and languages."""
    t0 = time.perf_counter()
    with _get_conn() as conn:
        repos = conn.execute("SELECT COUNT(*) FROM repositories;").fetchone()[0]
        files = conn.execute("SELECT COUNT(*) FROM source_files;").fetchone()[0]
        bricks = conn.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
        langs = conn.execute(
            "SELECT language, COUNT(*) AS cnt FROM code_bricks GROUP BY language ORDER BY cnt DESC;"
        ).fetchall()

    return {
        "status": "healthy",
        "repositories_count": repos,
        "source_files_count": files,
        "code_bricks_count": bricks,
        "languages": {r["language"]: r["cnt"] for r in langs if r["language"]},
        "query_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


@mcp.tool()
def list_repositories() -> List[Dict[str, Any]]:
    """List registered repository roots using safe public metadata (redacts absolute host paths)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT r.id AS repository_id, r.name,
                   COUNT(DISTINCT s.row_id) AS file_count,
                   COUNT(b.row_id) AS brick_count
            FROM repositories r
            LEFT JOIN source_files s ON s.repository_id = r.id
            LEFT JOIN code_bricks b ON b.file_id = s.row_id
            GROUP BY r.id, r.name
            ORDER BY brick_count DESC;
            """
        ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def search_code_bricks(
    query: str,
    language: Optional[str] = None,
    kind: Optional[str] = None,
    repository_id: Optional[str] = None,
    min_portability: float = 0.5,
    limit: int = 8,
) -> Dict[str, Any]:
    """
    Search across 160,000+ indexed code bricks using FTS5 BM25 lexical ranking and AST filters.
    Returns compact contract hits (without full source bodies) to preserve agent context window.
    """
    t0 = time.perf_counter()
    limit = max(1, min(limit, 30))

    # Strip conversational stopwords and build safe FTS5 tokens
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "how", "can", "use",
        "using", "implement", "create", "build", "write", "function", "class", "code", "to", "in"
    }
    tokens = [
        t.lower() for t in "".join(c if c.isalnum() else " " for c in query).split()
        if len(t) >= 2 and t.lower() not in stop
    ][:6]

    if not tokens:
        return {"mode": "lexical_only", "hits": [], "query_ms": 0.0}

    fts_and = " AND ".join(f'"{t}"*' for t in tokens)
    fts_or = " OR ".join(f'"{t}"*' for t in tokens)

    sql = """
        SELECT b.id AS brick_id, b.row_id, b.symbol_name, b.qualified_name, b.kind,
               b.language, b.signature, SUBSTR(COALESCE(b.docstring, b.ai_summary, ''), 1, 240) AS summary,
               b.portability_score, b.cyclomatic_complexity,
               b.start_line, b.end_line,
               s.repository_id, s.relative_path,
               (SELECT COUNT(*) FROM brick_dependencies d WHERE d.source_brick_id = b.id AND d.target_brick_id IS NULL) AS unresolved_deps
        FROM bricks_fts f
        JOIN code_bricks b ON b.row_id = f.rowid
        JOIN source_files s ON s.row_id = b.file_id
        WHERE bricks_fts MATCH ?
          AND COALESCE(b.portability_score, 1.0) >= ?
          AND s.relative_path NOT LIKE '%node_modules%'
          AND s.relative_path NOT LIKE '%.min.js'
          AND s.relative_path NOT LIKE '%jquery%'
    """
    params: List[Any] = [fts_and, min_portability]

    if language:
        sql += " AND LOWER(b.language) = LOWER(?)"
        params.append(language.strip())
    if kind:
        sql += " AND LOWER(b.kind) = LOWER(?)"
        params.append(kind.strip())
    if repository_id:
        sql += " AND s.repository_id = ?"
        params.append(repository_id.strip())

    sql += " ORDER BY f.rank ASC, b.portability_score DESC LIMIT ?;"
    params.append(limit)

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        # Relax to OR match if strict AND returned fewer than 3 hits
        if len(rows) < 3 and len(tokens) > 1:
            params[0] = fts_or
            rows = conn.execute(sql, params).fetchall()

    return {
        "mode": "lexical_only",
        "count": len(rows),
        "query_ms": round((time.perf_counter() - t0) * 1000, 2),
        "hits": [dict(r) for r in rows],
    }


@mcp.tool()
def inspect_brick_contract(brick_id: str) -> Dict[str, Any]:
    """
    Inspect the full structural contract of a brick (signature, docstring, external packages,
    internal call edges, and portability rationale) without loading its implementation body.
    """
    with _get_conn() as conn:
        brick = conn.execute(
            """
            SELECT b.id AS brick_id, b.row_id, b.symbol_name, b.qualified_name, b.kind,
                   b.language, b.signature, b.docstring, b.ai_summary,
                   b.portability_score, b.cyclomatic_complexity,
                   b.start_line, b.end_line,
                   s.repository_id, s.relative_path, s.content_hash
            FROM code_bricks b
            JOIN source_files s ON s.row_id = b.file_id
            WHERE b.id = ? OR CAST(b.row_id AS TEXT) = ?
            LIMIT 1;
            """,
            (brick_id, brick_id),
        ).fetchone()

        if not brick:
            return {"error": f"Brick '{brick_id}' not found."}

        b_dict = dict(brick)
        ext_pkgs = conn.execute(
            """
            SELECT DISTINCT package_name, import_statement
            FROM external_packages
            WHERE brick_id = ? OR file_id = (SELECT file_id FROM code_bricks WHERE id = ?);
            """,
            (b_dict["brick_id"], b_dict["brick_id"]),
        ).fetchall()

        deps = conn.execute(
            """
            SELECT d.dep_type, d.target_brick_id, d.unresolved_symbol,
                   tb.symbol_name AS target_symbol, tb.signature AS target_signature
            FROM brick_dependencies d
            LEFT JOIN code_bricks tb ON tb.id = d.target_brick_id
            WHERE d.source_brick_id = ?;
            """,
            (b_dict["brick_id"],),
        ).fetchall()

    score = float(b_dict.get("portability_score") or 1.0)
    b_dict["external_packages"] = [dict(p) for p in ext_pkgs]
    b_dict["dependencies"] = [dict(d) for d in deps]
    b_dict["portability_rationale"] = {
        "score": score,
        "external_package_count": len(ext_pkgs),
        "internal_dependency_count": sum(1 for d in deps if d["target_brick_id"]),
        "unresolved_symbol_count": sum(1 for d in deps if not d["target_brick_id"]),
        "assessment": "High self-containment" if score >= 0.75 else "Moderate coupling (check sibling deps)",
    }
    return b_dict


@mcp.tool()
def extract_composable_bundle(
    brick_ids: List[str],
    include_internal_deps: bool = True,
    max_dependency_depth: int = 2,
    max_output_chars: int = 24000,
) -> Dict[str, Any]:
    """
    Extract one or more code bricks along with their transitive sibling helper functions/classes
    and required import statements as a bounded, ready-to-adapt bundle for CodBot.
    """
    t0 = time.perf_counter()
    max_dependency_depth = max(0, min(max_dependency_depth, 4))
    visited_ids: List[str] = []
    queue: List[tuple[str, int]] = [(bid, 0) for bid in brick_ids[:10]]
    collected_bricks: List[Dict[str, Any]] = []
    external_imports: set[str] = set()
    unresolved_refs: set[str] = set()
    cycles_detected: List[str] = []

    with _get_conn() as conn:
        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited_ids:
                continue
            visited_ids.append(current_id)

            row = conn.execute(
                """
                SELECT b.id AS brick_id, b.file_id, b.symbol_name, b.qualified_name,
                       b.kind, b.language, b.signature, b.docstring, b.source_code,
                       b.portability_score, b.start_line, b.end_line,
                       s.repository_id, s.relative_path
                FROM code_bricks b
                JOIN source_files s ON s.row_id = b.file_id
                WHERE b.id = ? OR CAST(b.row_id AS TEXT) = ?
                LIMIT 1;
                """,
                (current_id, current_id),
            ).fetchone()

            if not row:
                unresolved_refs.add(current_id)
                continue

            b_data = dict(row)
            collected_bricks.append(b_data)

            # Gather external imports for this brick/file
            pkgs = conn.execute(
                "SELECT import_statement FROM external_packages WHERE brick_id = ? OR file_id = ?;",
                (b_data["brick_id"], b_data["file_id"]),
            ).fetchall()
            for p in pkgs:
                if p["import_statement"]:
                    external_imports.add(p["import_statement"].strip())

            # Traverse internal dependencies if requested
            if include_internal_deps and depth < max_dependency_depth:
                edges = conn.execute(
                    """
                    SELECT target_brick_id, unresolved_symbol
                    FROM brick_dependencies
                    WHERE source_brick_id = ?;
                    """,
                    (b_data["brick_id"],),
                ).fetchall()
                for e in edges:
                    t_id = e["target_brick_id"]
                    if t_id:
                        if t_id in visited_ids:
                            cycles_detected.append(f"{b_data['symbol_name']} -> {t_id}")
                        else:
                            queue.append((t_id, depth + 1))
                    elif e["unresolved_symbol"]:
                        unresolved_refs.add(e["unresolved_symbol"])

    # Assemble deterministic code slice respecting token/character budget
    code_sections: List[str] = []
    if external_imports:
        code_sections.append("# --- Required External Imports ---\n" + "\n".join(sorted(external_imports)))

    used_chars = sum(len(s) for s in code_sections)
    included_manifest: List[Dict[str, Any]] = []

    for b in reversed(collected_bricks):  # Helpers first, primary entrypoints last
        header = (
            f"\n# --- Brick: {b['symbol_name']} ({b['kind']}) | "
            f"Origin: {b['repository_id']}:{b['relative_path']}#L{b['start_line']}-L{b['end_line']} ---\n"
        )
        snippet = header + (b["source_code"] or b["signature"])
        if used_chars + len(snippet) > max_output_chars:
            break
        code_sections.append(snippet)
        used_chars += len(snippet)
        included_manifest.append({
            "brick_id": b["brick_id"],
            "symbol_name": b["symbol_name"],
            "kind": b["kind"],
            "origin": f"{b['repository_id']}:{b['relative_path']}#L{b['start_line']}-L{b['end_line']}",
            "portability_score": b["portability_score"],
        })

    return {
        "validation_status": "not_run",
        "bundle_ms": round((time.perf_counter() - t0) * 1000, 2),
        "included_bricks": included_manifest,
        "external_imports": sorted(external_imports),
        "unresolved_references": sorted(unresolved_refs),
        "cycles_detected": cycles_detected,
        "bundled_source": "\n".join(code_sections),
    }


def main() -> None:
    global _DB_PATH
    parser = argparse.ArgumentParser(description="BrickForge MCP Server")
    parser.add_argument("--db", default="data/brickforge.db", help="Path to BrickForge SQLite catalog")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="MCP transport mode")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for Streamable HTTP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8090, help="Bind port for Streamable HTTP")
    args = parser.parse_args()

    _DB_PATH = Path(args.db).resolve()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()