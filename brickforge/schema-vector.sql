-- Optional vector index. Load the sqlite-vec extension before executing this file.
-- The sample uses 1024 dimensions to match the initial BrickForge proposal.
-- If the embedding model changes dimension, create a migration and rebuild vectors.
-- sqlite-vec is pre-v1: pin the extension version and test its behavior in CI.

CREATE VIRTUAL TABLE IF NOT EXISTS brick_embeddings USING vec0(
    embedding FLOAT[1024]
);

-- Insert/update vectors with rowid = code_bricks.row_id:
-- INSERT INTO brick_embeddings(rowid, embedding) VALUES (?, ?);
-- The matching metadata row belongs in brick_embedding_state.
-- Delete vector rows explicitly when a brick is deleted or re-created:
-- DELETE FROM brick_embeddings WHERE rowid = ?;

-- Example nearest-neighbor query (bind a 1024-dimensional vector at ?):
-- SELECT b.id, b.symbol_name, v.distance
-- FROM brick_embeddings AS v
-- JOIN code_bricks AS b ON b.row_id = v.rowid
-- WHERE v.embedding MATCH ?
-- ORDER BY v.distance
-- LIMIT ?;
