PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Indexed Roots (Drives, NAS mounts, local Git repos)
CREATE TABLE repositories (
    id TEXT PRIMARY KEY,              -- UUIDv5 of normalized root path
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    vcs_branch TEXT,
    last_indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Source Files (Incremental hash tracking)
CREATE TABLE source_files (
    id TEXT PRIMARY KEY,              -- SHA-256 of repo_id + relative_path
    repo_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    language TEXT NOT NULL,           -- 'rust', 'python', 'typescript', 'cpp', 'csharp'
    file_hash TEXT NOT NULL,          -- SHA-256 of file content
    loc INTEGER NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo_id, relative_path)
);

-- 3. Extracted Software Bricks (Classes, Functions, Structs, Traits)
CREATE TABLE code_bricks (
    id TEXT PRIMARY KEY,              -- Deterministic hash: file_id + qualified_name + signature
    file_id TEXT NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    symbol_name TEXT NOT NULL,        -- e.g., 'RetryPolicy'
    qualified_name TEXT NOT NULL,     -- e.g., 'net::http::RetryPolicy'
    kind TEXT NOT NULL,               -- 'function', 'class', 'struct', 'trait', 'interface', 'module'
    language TEXT NOT NULL,
    signature TEXT NOT NULL,          -- Full typed signature without implementation body
    docstring TEXT,
    source_code TEXT NOT NULL,        -- Raw AST slice
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    cyclomatic_complexity INTEGER DEFAULT 1,
    portability_score REAL DEFAULT 1.0, -- 1.0 = pure/self-contained, 0.0 = heavily coupled
    ai_summary TEXT,                  -- LLM-generated functional summary
    tags JSON                         -- e.g., '["async", "io", "retry", "webgl"]'
);

-- 4. Internal Dependency Graph (Brick-to-Brick call & type references)
CREATE TABLE brick_dependencies (
    source_brick_id TEXT NOT NULL REFERENCES code_bricks(id) ON DELETE CASCADE,
    target_brick_id TEXT REFERENCES code_bricks(id) ON DELETE SET NULL,
    unresolved_symbol TEXT,           -- Populated if target is external or dynamic
    dep_type TEXT NOT NULL,           -- 'calls', 'inherits', 'uses_type', 'imports'
    PRIMARY KEY (source_brick_id, COALESCE(target_brick_id, unresolved_symbol), dep_type)
);

-- 5. External Package Dependencies (Cargo, pip, npm, system headers)
CREATE TABLE external_packages (
    brick_id TEXT NOT NULL REFERENCES code_bricks(id) ON DELETE CASCADE,
    package_name TEXT NOT NULL,       -- e.g., 'tokio', 'pydantic', 'three'
    import_statement TEXT NOT NULL,   -- Exact import line required
    PRIMARY KEY (brick_id, import_statement)
);

-- 6. Lexical Full-Text Search (BM25 over names, signatures, docstrings, summaries)
CREATE VIRTUAL TABLE bricks_fts USING fts5(
    brick_id UNINDEXED,
    symbol_name,
    qualified_name,
    signature,
    docstring,
    ai_summary,
    tags,
    content='code_bricks',
    content_rowid='rowid'
);

-- 7. Vector Embeddings Table (via sqlite-vec or mirrored in ChromaDB)
CREATE VIRTUAL TABLE bricks_vec USING vec0(
    brick_id TEXT PRIMARY KEY,
    embedding FLOAT[1024]             -- Matches snowflake-arctic-embed / bge-large dimension
);