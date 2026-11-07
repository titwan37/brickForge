# BrickForge

> **A local-first, AST-aware registry for discovering, understanding, and reusing software components.**

BrickForge turns source code scattered across drives, NAS locations, and Git repositories into a searchable knowledge base of reusable software building blocks — functions, methods, classes, structs, interfaces, modules, and their dependencies.

It combines language-aware parsing, structural metadata, dependency analysis, lexical search, and local semantic embeddings. An MCP server makes the catalog available to IDEs and AI agents, so they can discover existing implementations before creating new ones, inspect their contracts, retrieve dependency-aware bundles, and propose adaptations for new solutions.

## Why it exists

Useful software accumulates across years of projects. Parsers, algorithms, hardware wrappers, UI components, adapters, test helpers, and integration code become difficult to remember and rediscover. Searching by filename or exact symbol name is not enough when the question is functional — for example, “Have I already written a retry policy with jitter?”

BrickForge addresses this as a **software asset knowledge base**, not just a code search index. It preserves where a component came from, what it does, what it needs, how it relates to other symbols, and how confidently it can be reused.

## Core capabilities

- **Distributed source discovery:** register local folders, mounted drives, NAS shares, and Git working trees.
- **Incremental indexing:** hash files and avoid reparsing unchanged content.
- **AST-aware cataloging:** extract symbols, signatures, documentation, source spans, and parent-child relationships using Tree-sitter grammars.
- **Dependency mapping:** record calls, type references, inheritance, and imports, including unresolved references and confidence.
- **Hybrid discovery:** combine SQLite FTS5 lexical search with vector similarity and structured filters.
- **Reuse assessment:** expose explainable portability signals, dependency depth, package requirements, and source provenance.
- **Dependency-aware extraction:** retrieve a selected brick and its resolved internal dependencies with an import manifest.
- **Agent access:** expose search, inspection, extraction, synchronization, and optional composition tools through MCP.
- **Local-first operation:** keep source code, metadata, and embeddings on the host by default. Remote model or MCP configurations are opt-in and must be treated as data egress.

## Product principles

1. **Provenance before abstraction.** Every brick remains traceable to its repository, file, revision, and source span.
2. **AST boundaries before arbitrary chunks.** Search and extraction operate on functions, methods, classes, and other language structures.
3. **Inspect before extracting.** Agents should retrieve signatures and dependency summaries before loading implementation bodies.
4. **Reusability is a signal, not a guarantee.** Portability scores are heuristics with explainable factors; bundles still need compilation and tests.
5. **Never silently rewrite source repositories.** Indexing is read-only. Composition produces a proposal or artifacts in a separate workspace; it does not mutate indexed source by default.
6. **Local by default, explicit about egress.** Local embeddings are the default. Any cloud model, remote MCP endpoint, or external source integration must be configured consciously.

## Architecture

```text
 Local drives / NAS / Git working trees
                 |
                 v
       Root registry + file scanner
       - include/exclude rules
       - .gitignore support
       - SHA-256 delta detection
                 |
                 v
        Tree-sitter ingestion engine
       - syntax tree + source spans
       - symbols + signatures + docs
       - references + imports + packages
                 |
                 v
       Analysis and enrichment layer
       - dependency graph
       - complexity / portability signals
       - optional local summary + embeddings
                 |
                 v
       SQLite catalog (WAL)
       - relational metadata + graph edges
       - FTS5 lexical index
       - sqlite-vec vector index (optional extension)
                 |
                 v
            BrickForge MCP
       - stdio for local clients
       - Streamable HTTP for remote clients
                 |
                 v
       IDEs / coding agents / workflows
       discover -> inspect -> extract -> adapt -> validate
```

The MCP endpoint is an interface to the catalog. It is not itself a guarantee that returned code is portable or safe to execute. Adaptation and validation are separate steps.

## Naming options

| Name | CLI / package slug | Positioning |
|---|---|---|
| **BrickForge** *(recommended)* | `brickforge` / `brickforge-mcp` | A workshop for finding and assembling reusable software bricks. Strong fit for the product metaphor. |
| CodeMason | `codemason` | Emphasizes assembling components into larger solutions. |
| ASTVault | `astvault` | Emphasizes a structured, local code archive and AST-based retrieval. |
| CodeAtlas | `codeatlas` | Emphasizes mapping code distributed across repositories. |
| ReuseGraph | `reusegraph` | Emphasizes dependency relationships and component reuse. |
| LexiForge | `lexiforge` | Emphasizes lexical/semantic search and transformation. |

**Recommendation:** keep **BrickForge** as the working name. Before publishing, check package registries, domains, and trademark databases; this proposal does not establish name availability.

## Supported languages

Initial parser targets from the concept are Python, Rust, TypeScript/JavaScript, C/C++, C#, and Go. Actual support should be declared per installed Tree-sitter grammar and tested against representative syntax fixtures. A parser can extract syntax without necessarily resolving every cross-file symbol: deeper semantic resolution should be added incrementally with language-specific adapters or compiler/LSP data.

## Repository layout (proposed)

```text
brickforge/
  README.md
  pyproject.toml
  src/brickforge/
    cli/                 # init, add-root, scan, search, extract
    scanner/             # roots, ignore rules, hashing, file inventory
    parsers/             # Tree-sitter language adapters
    analysis/            # symbol resolution, dependencies, metrics
    embeddings/           # local embedding providers + model metadata
    storage/              # SQLite repositories, migrations, FTS, vectors
    search/               # lexical + vector fusion and filters
    extraction/           # dependency closure + bundle manifests
    composition/          # optional LLM-assisted adaptation
    mcp/                  # MCP tools, resources, transports
  migrations/
    schema.sql
    schema-vector.sql
  tests/
    fixtures/             # small representative projects per language
    test_incremental_scan.py
    test_symbol_identity.py
    test_dependency_closure.py
    test_search.py
    test_mcp_contracts.py
```

## Quick start (proposed CLI)

The following commands describe the intended interface; they are not executable until the CLI is implemented.

```bash
# Create the catalog
brickforge init --db ~/.brickforge/catalog.db

# Register explicit roots (registration is a local administrative action)
brickforge add-root "D:/Projects" --name projects
brickforge add-root "Z:/NAS_Archive/Repositories" --name archive

# Run an incremental scan
brickforge scan --all --languages python,rust,typescript,cpp,csharp,go

# Search by intent or symbol
brickforge search "exponential backoff retry with jitter" --language python

# Inspect and extract a selected component
brickforge inspect <brick_id> --dependency-depth 2
brickforge extract <brick_id> --include-deps --output ./reuse_bundle/

# Launch the local MCP server
brickforge mcp --transport stdio --db ~/.brickforge/catalog.db
```

## MCP workflow

1. An agent calls `search_code_bricks` with a natural-language need or exact symbol.
2. It calls `inspect_brick_contract` to review signatures, dependencies, package requirements, provenance, and reuse signals.
3. It calls `extract_composable_bundle` only after choosing candidates.
4. It may call `compose_and_adapt_bricks` to request an adaptation proposal or generated candidate code.
5. The consumer compiles and tests the result in its own controlled workspace before integration.

The server should expose only registered repositories. Remote MCP clients must not be allowed to submit arbitrary filesystem paths for scanning or extraction.

## Roadmap

### Phase 0 — Reliable local catalog
- [ ] CLI initialization and registered-root management
- [ ] Incremental scanner, ignore rules, and deleted-file detection
- [ ] Python parser vertical slice, then additional Tree-sitter grammars
- [ ] Stable symbol IDs, source provenance, and parse diagnostics
- [ ] SQLite schema, migrations, and FTS5 search

### Phase 1 — Useful discovery
- [ ] Dependency edges with resolution confidence
- [ ] Explainable portability signals
- [ ] Local summaries and embeddings with model/version metadata
- [ ] Hybrid lexical/vector ranking and filters

### Phase 2 — Safe reuse
- [ ] Dependency closure and import manifest generation
- [ ] Bundle export with provenance and unresolved-dependency report
- [ ] Unit-test and package-manifest association
- [ ] Compile/test validation profiles in a disposable workspace

### Phase 3 — Agent interface
- [ ] MCP tools and resources
- [ ] stdio integration and Streamable HTTP transport
- [ ] Authentication, origin checks, and repository allow-list enforcement
- [ ] Optional local-model composition tool

### Phase 4 — Exploration and quality
- [ ] Duplicate / near-duplicate detection
- [ ] Dependency graph explorer
- [ ] Usage and quality signals (tests, recent successful use, build status)
- [ ] Language-specific semantic resolvers

## Security and privacy notes

- Treat all indexed source as potentially sensitive. Store the database on an encrypted or access-controlled volume where appropriate.
- Exclude secrets/configuration files and common generated/vendor directories by default; support user-defined exclusions and size limits.
- Do not expose arbitrary paths through MCP. Register roots locally and authorize repository IDs on the server.
- Bind local HTTP deployments to loopback unless authentication and network exposure are deliberately configured.
- Validate HTTP `Origin` values, authenticate remote clients, and limit resource reads and bundle sizes.
- Do not execute extracted source as part of indexing. Run validation only in a disposable, sandboxed workspace with explicit policy.
- Use local summarization/embedding models for the default sovereign configuration. Be explicit when a remote provider is selected.

## Design status

This repository pack is a **technical proposal**, not a claim that the CLI, parsers, embeddings, or MCP server already exist. `schema.sql` is the core SQLite schema; `schema-vector.sql` is the optional sqlite-vec extension schema. The MCP manifest is a project-level contract draft to implement and test against the selected MCP SDK.
