# BrickForge — AST ingestion and storage design

This document turns the initial concept into an implementable ingestion pipeline. The first release should optimize for correctness, traceability, and incremental updates before optimizing ranking or cross-language composition.

## 1. Ingestion lifecycle

```text
register root
   -> enumerate candidate files
   -> apply ignore / safety policy
   -> hash file
   -> skip unchanged file OR parse changed file
   -> extract AST symbols and source spans
   -> resolve imports and symbol references
   -> calculate static reuse signals
   -> optionally summarize and embed
   -> commit file + symbols + edges atomically
   -> reconcile deleted files after a successful scan
```

### 1.1 Root registration and discovery

A repository record represents an explicitly registered scan root. It may be a folder, Git working tree, mounted drive directory, or NAS path. Store the canonical root path and user-configured include/exclude rules. Do not recursively crawl arbitrary filesystem paths supplied by MCP callers.

Default exclusions should cover version-control internals, build output, dependency caches, vendored code, generated code, virtual environments, binaries, and secret-bearing files. Support `.gitignore` where applicable, but do not treat it as the only safety boundary. Do not follow symbolic links by default; if enabled, detect loops and ensure resolved targets remain within an allowed root.

### 1.2 Delta scanner

For each candidate file:

1. Identify it by `(repository_id, normalized_relative_path)`.
2. Compute SHA-256 of file bytes and record size, modification time, language, and scan-run ID.
3. If the hash is unchanged and parser/grammar versions are unchanged, skip parsing and embedding.
4. If changed, parse into a temporary result first. Replace the file's current symbol/dependency rows transactionally only after the parse result has passed the configured acceptance policy.
5. If parsing fails, retain diagnostics and the previous good index unless the user explicitly requests replacement with a failed/partial parse.
6. After a successful full scan of a root, mark unseen files as deleted and remove their current symbol rows and vector entries.

A stable file ID is maintained by the database. A content hash identifies a particular file revision. Do not use modification time as the identity or as the only delta signal.

### 1.3 AST extraction

Use Tree-sitter grammars to identify declarations and their exact byte/line ranges. Initial kinds should include function, method, class, struct, trait, interface, enum, module, property, constant, and type alias where the grammar supports them.

For each symbol, store:

- symbol name and qualified name;
- kind, language, visibility, async/generator flags where available;
- normalized signature and signature hash;
- docstring/comment documentation;
- source slice and content hash;
- start/end byte and line positions;
- parent symbol for nested declarations;
- parser name/version and parse status/diagnostics at file level.

Use a deterministic `brick_id` derived from repository identity, relative path, qualified name, kind, and normalized signature. Keep a separate source-content hash. A signature or qualified-name change may produce a new brick identity; provenance should make the old/new relationship discoverable where a rename detector is later added.

Tree-sitter is a syntax parser. It can identify syntactic calls and type references, but it should not be presented as a complete compiler-grade resolver. Record resolution status and confidence. Start with same-file and import-based resolution; add Python, TypeScript, Rust, C/C++, C#, and Go semantic adapters incrementally.

### 1.4 Dependency extraction

Represent edges from a source brick to either a resolved catalog brick or an unresolved symbol. Use a controlled dependency type vocabulary:

- `calls`
- `uses_type`
- `inherits`
- `implements`
- `imports`
- `decorates`
- `references`

Keep external package requirements separately, including ecosystem (pip, npm, cargo, NuGet, system/header, etc.), version constraint when known, and original import statement. Preserve unresolved symbols instead of dropping them: unresolved edges are valuable warnings during extraction.

### 1.5 Reuse / portability signals

`portability_score` should be a transparent heuristic in `[0, 1]`, not a claim of purity or correctness. Suggested factors:

- number and depth of internal dependencies;
- unresolved references;
- external packages and platform-specific APIs;
- global state reads/writes;
- filesystem, network, process, environment, or hardware side effects;
- hard-coded absolute paths and configuration assumptions;
- presence of types/contracts and tests.

Store factor details in JSON so the score can be explained and recalibrated. Avoid treating a low score as “bad code”; a tightly coupled driver or domain service may still be valuable in its original context.

### 1.6 Semantic enrichment

Build a stable embedding document from symbol name, qualified name, signature, documentation, tags, and a concise functional summary. Store the embedding model ID, model version, dimension, and input-content hash. Recompute embeddings only when their input hash or model changes.

Default to local inference (for example, a locally hosted Ollama-compatible model). The sample vector migration uses 1024 dimensions to match the originally proposed embedding setup; change the dimension in a migration if another model is selected. Never silently mix vectors with different dimensions or models in one vector index.

## 2. Storage model

`schema.sql` creates the SQLite relational catalog and FTS5 index. `schema-vector.sql` creates the optional sqlite-vec virtual table after the extension is loaded.

| Table | Purpose |
|---|---|
| `repositories` | Registered roots and their scan policy |
| `scan_runs` | Scan lifecycle, counters, and errors |
| `source_files` | File identity, hash, language, parser status, and provenance |
| `code_bricks` | Current symbol contracts, source slices, metrics, and summaries |
| `brick_dependencies` | Resolved and unresolved symbol relationships |
| `external_packages` | Package/import requirements |
| `brick_embedding_state` | Model and input-hash metadata for vector freshness |
| `bricks_fts` | FTS5 lexical index over symbol metadata |
| `brick_embeddings` | Optional sqlite-vec index, keyed by `code_bricks.row_id` |

### Important implementation details

- `code_bricks.row_id` is an integer primary key used to join FTS5 and sqlite-vec efficiently; `code_bricks.id` is the externally visible deterministic string ID.
- The dependency table uses a surrogate primary key plus partial unique indexes. SQLite does not allow the original `COALESCE(target_brick_id, unresolved_symbol)` expression in a table primary-key declaration.
- The FTS5 table is an external-content table whose indexed columns exist in `code_bricks`. Insert/update/delete triggers keep the FTS index synchronized.
- sqlite-vec is an optional extension and is pre-v1. Pin the extension version and run a startup/CI smoke test. Vector rows use the same integer row ID as the associated `code_bricks` row.
- FTS5 and vector indexes are derived data. They must be rebuildable from the relational catalog and embedding metadata.
- Enable foreign keys on every SQLite connection, not just once in the schema script. Use WAL mode for concurrent readers and a serialized writer/indexer.

## 3. Hybrid search

Search should combine independent evidence rather than trust one ranking channel:

1. Normalize the natural-language query and extract optional exact identifiers.
2. Run FTS5/BM25 search over names, qualified names, signatures, docs, summaries, and tags.
3. If an embedding is available, run vector nearest-neighbor search over the same query representation.
4. Apply hard filters (language, kind, repository, portability minimum, enabled/visible state).
5. Fuse ranks (for example reciprocal-rank fusion) rather than directly combining incompatible raw BM25 and vector distances.
6. Return concise search hits with source provenance, signature, summary, portability factors, and scores. Do not return full source bodies by default.

A search result is a candidate, not a recommendation to execute. The caller should inspect its contract and dependency warnings next.

## 4. Bundle extraction

Given one or more brick IDs:

1. Resolve every requested ID; fail clearly for missing IDs.
2. Traverse internal dependency edges up to a caller-selected depth and hard safety limit.
3. Sort declarations in dependency order where possible; detect cycles and report them.
4. Collect source slices, import statements, external package requirements, and unresolved symbols.
5. Preserve original module paths by default. Rewriting imports or flattening namespaces can cause collisions and should be a separate, explicit adaptation step.
6. Return a bundle manifest with origin repository/file/lines, included IDs, omitted/unresolved dependencies, and caveats.

Do not label a bundle “ready to compile” unless a language-specific exporter has actually run the relevant compiler/build/test checks.

## 5. Validation and quality gates

Every parser adapter should have fixtures for nested declarations, overloads, decorators/attributes, generics, comments/docstrings, unicode, syntax errors, and import styles. Test incremental behavior (unchanged files, changed files, deleted files, renamed files, failed parse) and ensure no stale symbols remain.

Before a bundle is published for reuse, a separate validator should create a disposable workspace, materialize dependencies, run configured format/type/build/test commands, collect output, and report exact commands/results. Never run indexed code in the indexer process.
