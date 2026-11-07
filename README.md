# brickForge
An AST-aware, multi-repository code intelligence and component catalog that indexes distributed source code across local drives and repositories into a unified knowledge base.

# BrickForge (`brickforge-mcp`)

> **Sovereign AST Code Intelligence & Composable Component Registry for AI Agents and Engineers.**

`BrickForge` crawls distributed local drives, NAS archives, and multi-language Git repositories to catalog every class, function, struct, and module into a unified, queryable knowledge base. Exposed via a native **Model Context Protocol (MCP)** server, it empowers developers and autonomous coding agents to discover, extract, and assemble battle-tested "software bricks" on demand—eliminating redundant engineering.


## BrickForge MVP planning check-in

Prepare and deliver a prioritized MVP implementation backlog for the BrickForge project. 

Use the conversation's BrickForge design: a local-first AST-aware catalog of reusable code across registered local drives, NAS locations and Git repositories; incremental scanning and hashing; Tree-sitter extraction; SQLite relational metadata and dependency edges; FTS5 lexical search; optional sqlite-vec semantic search; and an MCP interface for catalog stats, repository listing/sync, scan status, brick search, contract inspection, dependency-aware extraction, and guarded adaptation proposals. 

Keep Core, MCP server and agent responsibilities separate. Start with one complete Python vertical slice: register and scan a directory, index functions/classes, search, inspect contracts, and extract a component with dependencies. Produce (1) a short MVP scope and explicit non-goals, (2) a prioritized backlog grouped into epics, (3) atomic implementation tasks with IDs, dependencies, and concrete acceptance criteria, (4) a validation/test plan including incremental re-indexing, parser errors, dependency resolution, FTS search, MCP contract tests, and safe filesystem boundaries, (5) key risks and decisions still open, and (6) a suggested sequence of milestones. 

Distinguish source-grounded decisions from recommendations; do not claim code has been implemented or tested. Keep tasks independently actionable and avoid expanding to multiple languages before the Python slice works.

---

## Why BrickForge?

Over years of engineering across dozens of projects, valuable algorithms, hardware wrappers, parsers, and UI components get scattered across drives and forgotten. Traditional tools fall short:

- **`grep` / `ripgrep`** requires remembering exact variable or function names.
- **Standard RAG** chunks files blindly by token count, severing AST boundaries and losing import dependencies.

**BrickForge** indexes code at the **Abstract Syntax Tree (AST)** level. It understands exact type signatures, calculates portability scores, maps transitive sibling dependencies, and pairs lexical search with local vector embeddings.

---

## System Architecture

```

+-------------------------------------------------------------------------+
|                   DISTRIBUTED SOURCE REPOSITORIES                       |
|       Local Drives (C:/, D:/)   |   NAS Shares   |   Git Archives       |
+---------------------------------+---------------------------------------+
|
v
+-------------------------------------------------------------------------+
|                     AST INGESTION & ANALYSIS ENGINE                     |
|  1. SHA-256 Delta Scanner (skips unchanged files)                       |
|  2. Tree-sitter Multi-Language Parser (Rust, Python, TS/JS, C++, C#)    |
|  3. Call-Graph & Purity Analyzer (Portability Score + Sibling Links)    |
|  4. Local Semantic Summarizer (Ollama + Arctic-Embed / BGE)             |
+---------------------------------+---------------------------------------+
|
v
+-------------------------------------------------------------------------+
|                        HYBRID STORAGE LAYER                             |
|  +---------------------------+  +------------------+  +--------------+  |
|  | SQLite Relational & Graph |  |   SQLite FTS5    |  |  sqlite-vec  |  |
|  | (AST Nodes, Call Edges)   |  | (BM25 Signatures)|  | (Embeddings) |  |
|  +---------------------------+  +------------------+  +--------------+  |
+---------------------------------+---------------------------------------+
|
v
+-------------------------------------------------------------------------+
|                      BRICKFORGE MCP SERVER (STDIO / SSE)                |
|  Tools: search_code_bricks | inspect_brick_contract                     |
|         extract_composable_bundle | compose_and_adapt_bricks            |
+---------------------------------+---------------------------------------+
|
v
+-------------------------------------------------------------------------+
|                    CONSUMERS & ORCHESTRATORS                            |
|     IDEs (VS Code / Cursor / Antigravity)  |  Custom Multi-Agent Bots   |
+-------------------------------------------------------------------------+

```

---

## Key Features

- **Multi-Language Tree-sitter Parsing:** Native AST extraction for Rust, Python, TypeScript/JavaScript, C/C++, C#, and Go.
- **Dependency-Resolved Extraction:** Requesting a class automatically resolves and bundles private helper functions, custom structs, and required `use`/`import` headers from the same module.
- **Portability Scoring:** Automatically ranks code bricks by how self-contained they are (penalizing global state mutations and deep monolith coupling).
- **100% Local & Sovereign:** Runs entirely on local hardware using SQLite (`WAL` mode + `FTS5` + `sqlite-vec`) and local Ollama models. Zero source code ever leaves your LAN.
- **Token-Efficient MCP Workflow:** Agents inspect lightweight signatures first (`inspect_brick_contract`) and pull full source implementations (`extract_composable_bundle`) only after selecting the right brick.

---

## Quick Start

### 1. Initialize & Index Repositories

```bash
### Initialize the local SQLite + Vector catalog
brickforge init --db ~/.brickforge/catalog.db

### Register and crawl source directories across drives
brickforge scan "D:/Projects" "Z:/NAS_Archive/Repositories" \
  --languages rust,python,typescript,cpp \
  --embed-model snowflake-arctic-embed

```

