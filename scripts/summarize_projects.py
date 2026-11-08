"""Script to generate or refresh rich, HTML-free AI project summaries using Ollama.

Uses Ollama (e.g. jetelain/Qwen3.5-9B:latest or qwen2.5-coder:7b) to generate
deep architectural overviews based on READMEs, subfolder 'docs', manifests,
and entrypoint code headers. Automatically saves to data/project_summaries.json.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time

# Ensure brickforge package is on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from brickforge.web.projects import (
    DEFAULT_OLLAMA_MODEL,
    collect_project_context,
    extract_project_ai_intent,
    get_all_projects,
    get_summaries_cache_path,
    load_persisted_summaries,
    query_ollama_project_summary,
    save_persisted_summary,
    strip_html_and_badges,
    synthesize_clean_fallback_summary,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("summarize_projects")


def main():
    parser = argparse.ArgumentParser(description="Generate rich, HTML-free project overviews with Ollama")
    parser.add_argument("--db", type=str, default="data/brickforge.db", help="Path to SQLite catalog database")
    parser.add_argument("--model", type=str, default=DEFAULT_OLLAMA_MODEL, help=f"Ollama model name (default: {DEFAULT_OLLAMA_MODEL})")
    parser.add_argument("--endpoint", type=str, default="http://127.0.0.1:11434", help="Ollama HTTP API endpoint")
    parser.add_argument("--repo", type=str, default=None, help="Filter to specific repository ID")
    parser.add_argument("--project", type=str, default=None, help="Filter to single project name")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of projects to summarize")
    parser.add_argument("--force", action="store_true", help="Force re-generation of existing cached summaries")
    parser.add_argument("--static-only", action="store_true", help="Use multi-source static extractor without calling Ollama")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"[ERROR] Database not found at {db_path.resolve()}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    logger.info("=" * 70)
    logger.info("  BrickForge Project AI Summarizer")
    logger.info(f"  Catalog DB : {db_path.resolve()}")
    logger.info(f"  Model      : {args.model if not args.static_only else 'Static Multi-Source Extractor'}")
    logger.info("=" * 70)

    # Load existing cached summaries
    cached = load_persisted_summaries()
    logger.info(f"[Cache] Loaded {len(cached)} existing project summaries from {get_summaries_cache_path()}")

    # Retrieve all registered projects
    all_projects = get_all_projects(conn)
    logger.info(f"[Catalog] Found {len(all_projects)} total projects in catalog.")

    # Apply filters
    targets = all_projects
    if args.repo:
        targets = [p for p in targets if p["repository_id"] == args.repo.strip()]
    if args.project:
        targets = [p for p in targets if p["symbol_name"].lower() == args.project.strip().lower()]
    if args.limit:
        targets = targets[: args.limit]

    logger.info(f"[Target] Selected {len(targets)} projects to process.\n")

    conn_cursor = conn.cursor()
    conn_cursor.execute("SELECT id, root_path FROM repositories;")
    repo_roots = {row["id"]: row["root_path"] for row in conn_cursor.fetchall()}

    success_count = 0
    skipped_count = 0

    for idx, p in enumerate(targets, start=1):
        p_name = p["symbol_name"]
        repo_id = p["repository_id"]
        repo_root = repo_roots.get(repo_id)
        cache_key = f"{repo_root}:{p_name}"

        # Check if already cached
        if not args.force and cache_key in cached and cached[cache_key]:
            existing_summary = cached[cache_key]
            # If it already looks clean (no HTML tags)
            if "<p" not in existing_summary and "<img" not in existing_summary and len(existing_summary) > 30:
                logger.info(f"[{idx}/{len(targets)}] [Cached] {repo_id}/{p_name}")
                skipped_count += 1
                continue

        logger.info(f"[{idx}/{len(targets)}] [Processing] {repo_id}/{p_name} ...")
        t0 = time.time()

        context = collect_project_context(repo_root, p_name)

        summary = None
        if not args.static_only:
            try:
                summary = query_ollama_project_summary(
                    project_name=p_name,
                    context=context,
                    model=args.model,
                    endpoint=args.endpoint,
                )
            except Exception as e:
                logger.debug(f"Ollama call failed for {p_name}: {e}")

        if not summary:
            summary = synthesize_clean_fallback_summary(p_name, context)

        summary = strip_html_and_badges(summary)
        save_persisted_summary(cache_key, summary)
        elapsed = time.time() - t0

        logger.info(f"    -> Done in {elapsed:.2f}s ({len(summary)} chars): {summary[:120]}...\n")
        success_count += 1

    logger.info("=" * 70)
    logger.info(f"  Summary Complete! Updated: {success_count}, Skipped (Cached): {skipped_count}")
    logger.info(f"  Saved to: {get_summaries_cache_path().resolve()}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()

