"""FAISS vector indexing and hybrid dense + lexical retrieval for BrickForge.

Provides:
- In-process or persistent FAISS FlatIP (cosine distance via inner product with L2 normalization).
- Dual-node embedding generator (Ollama on NITRO or localhost fallback).
- Hybrid search merging SQLite FTS5 (BM25) and FAISS dense vector similarity with Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import faiss
import httpx
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_INDEX_PATH = Path("data/brickforge_faiss.index")
DEFAULT_MAPPING_PATH = Path("data/brickforge_faiss_map.json")
DEFAULT_EMBED_MODEL = "snowflake-arctic-embed:latest"
NITRO_OLLAMA_URL = os.getenv("NITRO_OLLAMA_URL", "http://NITRO-AN51755:11434")
LOCAL_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


class BrickForgeVectorIndex:
    """Manages dense vector representations of code bricks and documentation using FAISS."""

    def __init__(
        self,
        dimension: int = 1024,
        index_file: Optional[Union[str, Path]] = DEFAULT_INDEX_PATH,
        mapping_file: Optional[Union[str, Path]] = DEFAULT_MAPPING_PATH,
        model_name: str = DEFAULT_EMBED_MODEL,
    ):
        self.dimension = dimension
        self.index_file = Path(index_file) if index_file else None
        self.mapping_file = Path(mapping_file) if mapping_file else None
        self.model_name = model_name
        self.id_to_brick: List[Dict[str, Any]] = []
        self.index: faiss.Index = faiss.IndexFlatIP(self.dimension)
        self.load()

    def load(self) -> bool:
        """Load index and ID mappings from disk if they exist."""
        if self.index_file and self.index_file.exists() and self.mapping_file and self.mapping_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                with open(self.mapping_file, "r", encoding="utf-8") as f:
                    self.id_to_brick = json.load(f)
                return True
            except Exception as e:
                logger.warning(f"Failed to load FAISS index from disk: {e}")
        return False

    def save(self) -> None:
        """Persist index and brick ID mapping table to disk."""
        if self.index_file:
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(self.index_file))
        if self.mapping_file:
            self.mapping_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.mapping_file, "w", encoding="utf-8") as f:
                json.dump(self.id_to_brick, f)

    def generate_embedding(self, text: str, timeout_sec: float = 6.0) -> Optional[np.ndarray]:
        """Fetch embedding from remote Nitro node first, then local host fallback."""
        payload = {"model": self.model_name, "prompt": text[:2048]}
        endpoints = [NITRO_OLLAMA_URL, LOCAL_OLLAMA_URL]

        for ep in endpoints:
            try:
                with httpx.Client(timeout=httpx.Timeout(timeout_sec, connect=1.0)) as client:
                    res = client.post(f"{ep}/api/embeddings", json=payload)
                    if res.status_code == 200:
                        vec = res.json().get("embedding")
                        if vec:
                            arr = np.array(vec, dtype=np.float32)
                            norm = np.linalg.norm(arr)
                            if norm > 0:
                                arr = arr / norm
                            return arr
            except Exception:
                continue
        return None

    def append_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        save_after: bool = True,
    ) -> bool:
        """Online update: Embed a new document or code fact and append it immediately into the FAISS index."""
        emb = self.generate_embedding(text)
        if emb is None:
            return False

        meta = dict(metadata or {})
        meta["brick_id"] = doc_id
        meta["timestamp"] = time.time()
        meta["text_preview"] = text[:300]

        self.add_brick(meta, emb)
        if save_after:
            self.save()
        return True

    def batch_append_vectors(
        self,
        items: List[Dict[str, Any]],
        save_after: bool = True,
    ) -> int:
        """Append pre-computed vectors and metadata in bulk with normalization."""
        if not items:
            return 0

        vectors = []
        new_metas = []
        for it in items:
            raw_v = it.get("vector")
            if raw_v is not None:
                arr = np.array(raw_v, dtype=np.float32)
                norm = np.linalg.norm(arr)
                if norm > 0:
                    arr = arr / norm
                vectors.append(arr)
                meta = dict(it.get("metadata", {}))
                meta["brick_id"] = it.get("doc_id") or meta.get("brick_id", f"doc_{len(self.id_to_brick) + len(new_metas)}")
                new_metas.append(meta)

        if not vectors:
            return 0

        mat = np.ascontiguousarray(np.stack(vectors), dtype=np.float32)
        self.index.add(mat)
        self.id_to_brick.extend(new_metas)
        if save_after:
            self.save()
        return len(vectors)

    def search_similar(
        self,
        query: str,
        top_k: int = 5,
        query_vector: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """Dense similarity search returning nearest code bricks with cosine similarity scores."""
        if self.index.ntotal == 0:
            return []

        q_vec = query_vector if query_vector is not None else self.generate_embedding(query)
        if q_vec is None:
            return []

        q_2d = np.ascontiguousarray(q_vec.reshape(1, -1), dtype=np.float32)
        distances, indices = self.index.search(q_2d, min(top_k, self.index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx < len(self.id_to_brick):
                meta = dict(self.id_to_brick[idx])
                meta["similarity_score"] = round(float(dist), 4)
                results.append(meta)
        return results

    def hybrid_search(
        self,
        db_path: Union[str, Path],
        query: str,
        limit: int = 5,
        dense_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion (RRF) combining lexical FTS5 (BM25) and dense FAISS vectors."""
        # 1. Lexical search via FTS5
        lexical_hits = []
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            fts_sql = """
            SELECT 
                b.id AS brick_id,
                b.symbol_name,
                b.qualified_name,
                b.kind,
                b.language,
                b.signature,
                b.docstring,
                b.source_code,
                b.portability_score,
                s.relative_path,
                r.name AS repository_name,
                f.rank
            FROM bricks_fts f
            JOIN code_bricks b ON f.rowid = b.row_id
            JOIN source_files s ON b.file_id = s.row_id
            JOIN repositories r ON s.repository_id = r.id
            WHERE bricks_fts MATCH ?
            ORDER BY f.rank ASC
            LIMIT 25;
            """
            clean_q = " OR ".join(f'"{t}"*' for t in query.split() if len(t) >= 2)
            if clean_q:
                cursor.execute(fts_sql, (clean_q,))
                lexical_hits = [dict(r) for r in cursor.fetchall()]
            conn.close()
        except Exception as e:
            logger.debug(f"Lexical search skipped/failed: {e}")

        # 2. Dense search via FAISS
        dense_hits = self.search_similar(query, top_k=25)

        # 3. Reciprocal Rank Fusion (RRF) scoring
        combined_scores: Dict[str, float] = {}
        brick_data: Dict[str, Dict[str, Any]] = {}

        for rank, hit in enumerate(lexical_hits):
            bid = hit["brick_id"]
            combined_scores[bid] = combined_scores.get(bid, 0.0) + (1.0 - dense_weight) * (1.0 / (rrf_k + rank + 1))
            brick_data[bid] = hit

        for rank, hit in enumerate(dense_hits):
            bid = hit["brick_id"]
            combined_scores[bid] = combined_scores.get(bid, 0.0) + dense_weight * (1.0 / (rrf_k + rank + 1))
            if bid not in brick_data:
                brick_data[bid] = hit

        sorted_bids = sorted(combined_scores.keys(), key=lambda b: combined_scores[b], reverse=True)
        final_results = []
        for bid in sorted_bids[:limit]:
            item = dict(brick_data[bid])
            item["rrf_score"] = round(combined_scores[bid], 5)
            final_results.append(item)

        return final_results
