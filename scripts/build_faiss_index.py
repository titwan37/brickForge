"""Script to build or update the FAISS vector index from BrickForge catalog SQLite bricks."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sqlite3
import sys
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from brickforge.search.vector_index import BrickForgeVectorIndex, DEFAULT_INDEX_PATH, DEFAULT_MAPPING_PATH

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("build_faiss_index")


def main():
    parser = argparse.ArgumentParser(description="Build FAISS vector index from code bricks")
    parser.add_argument("--db", type=str, default="data/brickforge.db", help="Path to SQLite catalog database")
    parser.add_argument("--index", type=str, default=str(DEFAULT_INDEX_PATH), help="Destination FAISS index path")
    parser.add_argument("--map", type=str, default=str(DEFAULT_MAPPING_PATH), help="Destination mapping JSON path")
    parser.add_argument("--limit", type=int, default=500, help="Max bricks to embed (for initial batch)")
    parser.add_argument("--model", type=str, default="snowflake-arctic-embed:latest", help="Embedding model name")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return 1

    vec_index = BrickForgeVectorIndex(
        dimension=1024,
        index_file=args.index,
        mapping_file=args.map,
        model_name=args.model,
    )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query bricks with signatures and docstrings
    cursor.execute("""
        SELECT 
            b.id AS brick_id,
            b.symbol_name,
            b.kind,
            b.language,
            b.signature,
            b.docstring,
            s.relative_path,
            r.name AS repository_name,
            b.portability_score
        FROM code_bricks b
        JOIN source_files s ON b.file_id = s.row_id
        JOIN repositories r ON s.repository_id = r.id
        WHERE b.signature IS NOT NULL AND LENGTH(b.signature) > 5
        ORDER BY b.portability_score DESC
        LIMIT ?;
    """, (args.limit,))

    rows = cursor.fetchall()
    conn.close()

    logger.info(f"Loaded {len(rows)} code bricks for vector embedding...")
    added_count = 0
    t_start = time.perf_counter()

    for r in rows:
        text = f"{r['symbol_name']} ({r['kind']} - {r['language']})\nPath: {r['relative_path']}\nSignature: {r['signature']}\nDoc: {r['docstring'] or ''}"
        emb = vec_index.generate_embedding(text)
        if emb is not None:
            vec_index.add_brick(
                {
                    "brick_id": r["brick_id"],
                    "symbol_name": r["symbol_name"],
                    "kind": r["kind"],
                    "language": r["language"],
                    "signature": r["signature"],
                    "docstring": r["docstring"],
                    "relative_path": r["relative_path"],
                    "repository_name": r["repository_name"],
                    "portability_score": r["portability_score"],
                },
                emb,
            )
            added_count += 1
            if added_count % 50 == 0:
                logger.info(f"  Embedded {added_count}/{len(rows)} bricks...")

    vec_index.save()
    elapsed = round(time.perf_counter() - t_start, 2)
    logger.info(f"✅ FAISS index saved: {added_count} vectors indexed in {elapsed}s to {args.index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
