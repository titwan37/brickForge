-- 0002_fts.sql: FTS5 search index synchronization and optimization

-- Ensure triggers exist and rebuild FTS table against code_bricks
INSERT INTO bricks_fts(bricks_fts) VALUES('rebuild');

