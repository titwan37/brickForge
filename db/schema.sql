-- BrickForge core relational catalog + FTS5 index
-- Requires SQLite with FTS5 enabled. Load schema-vector.sql separately after
-- loading the sqlite-vec extension. Enable foreign_keys on EVERY connection.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS repositories (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    root_path       TEXT NOT NULL UNIQUE,
    source_kind     TEXT NOT NULL DEFAULT 'directory'
                    CHECK (source_kind IN ('directory', 'git_worktree', 'nas_share', 'archive')),
    vcs_remote      TEXT,
    vcs_ref         TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    include_globs   TEXT NOT NULL DEFAULT '[]',
    exclude_globs   TEXT NOT NULL DEFAULT '[]',
    follow_symlinks INTEGER NOT NULL DEFAULT 0 CHECK (follow_symlinks IN (0, 1)),
    last_scan_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id                TEXT PRIMARY KEY,
    repository_id     TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'running'
                      CHECK (status IN ('running', 'completed', 'completed_with_errors', 'failed', 'cancelled')),
    started_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at       TEXT,
    files_seen        INTEGER NOT NULL DEFAULT 0,
    files_changed     INTEGER NOT NULL DEFAULT 0,
    files_skipped     INTEGER NOT NULL DEFAULT 0,
    files_deleted     INTEGER NOT NULL DEFAULT 0,
    symbols_indexed   INTEGER NOT NULL DEFAULT 0,
    errors_count      INTEGER NOT NULL DEFAULT 0,
    error_summary     TEXT
);
CREATE INDEX IF NOT EXISTS idx_scan_runs_repo_started
    ON scan_runs(repository_id, started_at DESC);

CREATE TABLE IF NOT EXISTS source_files (
    row_id           INTEGER PRIMARY KEY,
    id               TEXT NOT NULL UNIQUE,
    repository_id    TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    relative_path    TEXT NOT NULL,
    language         TEXT NOT NULL,
    file_hash        TEXT NOT NULL,
    byte_size        INTEGER NOT NULL DEFAULT 0 CHECK (byte_size >= 0),
    loc              INTEGER NOT NULL DEFAULT 0 CHECK (loc >= 0),
    modified_ns      INTEGER,
    parser_name      TEXT,
    parser_version   TEXT,
    parse_status     TEXT NOT NULL DEFAULT 'pending'
                     CHECK (parse_status IN ('pending', 'ok', 'partial', 'failed', 'unsupported')),
    parse_diagnostics TEXT,
    last_seen_run_id TEXT REFERENCES scan_runs(id) ON DELETE SET NULL,
    indexed_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repository_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_source_files_repo_language
    ON source_files(repository_id, language);
CREATE INDEX IF NOT EXISTS idx_source_files_hash
    ON source_files(file_hash);

CREATE TABLE IF NOT EXISTS code_bricks (
    row_id                 INTEGER PRIMARY KEY,
    id                     TEXT NOT NULL UNIQUE,
    file_id                INTEGER NOT NULL REFERENCES source_files(row_id) ON DELETE CASCADE,
    parent_row_id          INTEGER REFERENCES code_bricks(row_id) ON DELETE CASCADE,
    symbol_name            TEXT NOT NULL,
    qualified_name         TEXT NOT NULL,
    kind                   TEXT NOT NULL CHECK (kind IN (
                               'function', 'method', 'class', 'struct', 'trait',
                               'interface', 'enum', 'module', 'property',
                               'constant', 'type_alias'
                           )),
    language               TEXT NOT NULL,
    visibility             TEXT,
    signature              TEXT NOT NULL DEFAULT '',
    signature_hash         TEXT NOT NULL,
    docstring              TEXT,
    source_code            TEXT NOT NULL,
    source_hash            TEXT NOT NULL,
    start_byte             INTEGER NOT NULL DEFAULT 0,
    end_byte               INTEGER NOT NULL DEFAULT 0,
    start_line             INTEGER NOT NULL,
    end_line               INTEGER NOT NULL,
    is_async               INTEGER NOT NULL DEFAULT 0 CHECK (is_async IN (0, 1)),
    cyclomatic_complexity  INTEGER NOT NULL DEFAULT 1 CHECK (cyclomatic_complexity >= 0),
    portability_score      REAL NOT NULL DEFAULT 0.5 CHECK (portability_score >= 0.0 AND portability_score <= 1.0),
    portability_factors    TEXT NOT NULL DEFAULT '{}',
    ai_summary             TEXT,
    tags                   TEXT NOT NULL DEFAULT '[]',
    indexed_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_byte >= start_byte),
    CHECK (end_line >= start_line),
    UNIQUE(file_id, qualified_name, kind, signature_hash)
);
CREATE INDEX IF NOT EXISTS idx_bricks_file ON code_bricks(file_id);
CREATE INDEX IF NOT EXISTS idx_bricks_name ON code_bricks(symbol_name);
CREATE INDEX IF NOT EXISTS idx_bricks_qualified_name ON code_bricks(qualified_name);
CREATE INDEX IF NOT EXISTS idx_bricks_kind_language ON code_bricks(kind, language);
CREATE INDEX IF NOT EXISTS idx_bricks_portability ON code_bricks(portability_score DESC);
CREATE INDEX IF NOT EXISTS idx_bricks_parent ON code_bricks(parent_row_id);

-- Each dependency row is either resolved to a catalog brick or retains an
-- unresolved symbol. The CHECK and partial unique indexes avoid expression
-- primary keys, which SQLite does not support.
CREATE TABLE IF NOT EXISTS brick_dependencies (
    dependency_id       INTEGER PRIMARY KEY,
    source_row_id       INTEGER NOT NULL REFERENCES code_bricks(row_id) ON DELETE CASCADE,
    target_row_id       INTEGER REFERENCES code_bricks(row_id) ON DELETE CASCADE,
    unresolved_symbol   TEXT,
    dependency_type     TEXT NOT NULL CHECK (dependency_type IN (
                            'calls', 'uses_type', 'inherits', 'implements',
                            'imports', 'decorates', 'references'
                        )),
    resolution_status   TEXT NOT NULL DEFAULT 'unresolved'
                        CHECK (resolution_status IN ('resolved', 'unresolved', 'external')),
    confidence          REAL NOT NULL DEFAULT 0.5 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    CHECK (
      (target_row_id IS NOT NULL AND unresolved_symbol IS NULL AND resolution_status = 'resolved')
      OR
      (target_row_id IS NULL AND unresolved_symbol IS NOT NULL AND resolution_status IN ('unresolved', 'external'))
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_brick_dep_resolved
    ON brick_dependencies(source_row_id, target_row_id, dependency_type)
    WHERE target_row_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_brick_dep_unresolved
    ON brick_dependencies(source_row_id, unresolved_symbol, dependency_type)
    WHERE target_row_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_brick_deps_target ON brick_dependencies(target_row_id);

CREATE TABLE IF NOT EXISTS external_packages (
    package_id          INTEGER PRIMARY KEY,
    brick_row_id        INTEGER NOT NULL REFERENCES code_bricks(row_id) ON DELETE CASCADE,
    ecosystem           TEXT NOT NULL,
    package_name        TEXT NOT NULL,
    version_constraint  TEXT,
    import_statement    TEXT NOT NULL DEFAULT '',
    UNIQUE(brick_row_id, ecosystem, package_name, import_statement)
);
CREATE INDEX IF NOT EXISTS idx_external_packages_name
    ON external_packages(ecosystem, package_name);

-- Tracks which text/model produced the vector currently stored at rowid=brick_row_id.
-- It remains useful even when sqlite-vec is not installed.
CREATE TABLE IF NOT EXISTS brick_embedding_state (
    brick_row_id       INTEGER PRIMARY KEY REFERENCES code_bricks(row_id) ON DELETE CASCADE,
    model_id           TEXT NOT NULL,
    model_version      TEXT,
    embedding_dimension INTEGER NOT NULL CHECK (embedding_dimension > 0),
    input_hash         TEXT NOT NULL,
    embedded_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- External-content FTS5 table. Its indexed columns are columns on code_bricks;
-- content_rowid maps FTS rows to code_bricks.row_id.
CREATE VIRTUAL TABLE IF NOT EXISTS bricks_fts USING fts5(
    symbol_name,
    qualified_name,
    signature,
    docstring,
    ai_summary,
    tags,
    content='code_bricks',
    content_rowid='row_id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS code_bricks_ai AFTER INSERT ON code_bricks BEGIN
    INSERT INTO bricks_fts(rowid, symbol_name, qualified_name, signature, docstring, ai_summary, tags)
    VALUES (new.row_id, new.symbol_name, new.qualified_name, new.signature, new.docstring, new.ai_summary, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS code_bricks_ad AFTER DELETE ON code_bricks BEGIN
    INSERT INTO bricks_fts(bricks_fts, rowid, symbol_name, qualified_name, signature, docstring, ai_summary, tags)
    VALUES ('delete', old.row_id, old.symbol_name, old.qualified_name, old.signature, old.docstring, old.ai_summary, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS code_bricks_au AFTER UPDATE ON code_bricks BEGIN
    INSERT INTO bricks_fts(bricks_fts, rowid, symbol_name, qualified_name, signature, docstring, ai_summary, tags)
    VALUES ('delete', old.row_id, old.symbol_name, old.qualified_name, old.signature, old.docstring, old.ai_summary, old.tags);
    INSERT INTO bricks_fts(rowid, symbol_name, qualified_name, signature, docstring, ai_summary, tags)
    VALUES (new.row_id, new.symbol_name, new.qualified_name, new.signature, new.docstring, new.ai_summary, new.tags);
END;

-- Required once after importing pre-existing code_bricks rows into an existing DB:
-- INSERT INTO bricks_fts(bricks_fts) VALUES ('rebuild');
