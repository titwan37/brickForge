**Executive Pitch (Short Version)**
An AST-aware, multi-repository code intelligence and component catalog that indexes distributed source code across local drives and repositories into a unified knowledge base. Exposed via a Model Context Protocol (MCP) server, it enables engineers and autonomous AI agents to discover, adapt, and compose proven software building blocks on demand—eliminating redundant coding and cognitive overhead.

---

I was thinking to start a new solution which can catalog all source code classes and functions, I possess across several drives, repositories.

It can constitute a knowledge base, a practicle used functionalities.  

Overtime, it is difficult and impossible for a human to have an overview and to remember everything. That is why I would love to be able to reuse some of those software bricks and components.

We can be assembled together to compose new solutions.

We can transform them and make them available with a MCP server, other agent or software can access and dispose them on demand.

- Generate a project README and naming options
- Draft the AST ingestion and SQLite/Vector schema
- Design the MCP server tool schema and endpoints

---

{
  "tools": [
    {
      "name": "search_code_bricks",
      "description": "Hybrid semantic (vector) and lexical (BM25 + AST filter) search across all indexed repositories to discover reusable classes, functions, and modules.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "Natural language intent or exact symbol/signature query (e.g., 'thread-safe ring buffer' or 'fn parse_hl7')."
          },
          "languages": {
            "type": "array",
            "items": { "type": "string", "enum": ["rust", "python", "typescript", "cpp", "csharp", "go"] },
            "description": "Filter by programming languages."
          },
          "kinds": {
            "type": "array",
            "items": { "type": "string", "enum": ["function", "class", "struct", "trait", "interface"] }
          },
          "min_portability": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.5,
            "description": "Filter out tightly coupled legacy code below this portability threshold."
          },
          "limit": { "type": "integer", "default": 10, "maximum": 50 }
        },
        "required": ["query"]
      }
    },
    {
      "name": "inspect_brick_contract",
      "description": "Retrieve the AST signature, docstring, external package requirements, and internal dependency tree of a specific brick without loading its full implementation body (saves context window).",
      "inputSchema": {
        "type": "object",
        "properties": {
          "brick_id": { "type": "string", "description": "Unique hash ID of the code brick." },
          "dependency_depth": { "type": "integer", "default": 2, "maximum": 5 }
        },
        "required": ["brick_id"]
      }
    },
    {
      "name": "extract_composable_bundle",
      "description": "Extract a code brick along with its transitive internal helper functions/types and required import headers as a self-contained, ready-to-compile code block.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "brick_ids": {
            "type": "array",
            "items": { "type": "string" },
            "description": "One or more brick IDs to bundle together."
          },
          "include_internal_deps": {
            "type": "boolean",
            "default": true,
            "description": "Automatically resolve and inline sibling helper functions/structs referenced in the AST."
          },
          "strip_repo_specifics": {
            "type": "boolean",
            "default": true,
            "description": "Rewrite internal module paths to flat/local scope imports."
          }
        },
        "required": ["brick_ids"]
      }
    },
    {
      "name": "compose_and_adapt_bricks",
      "description": "Synthesize or refactor one or more catalog bricks to fit a target architecture, language version, or interface contract.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "brick_ids": {
            "type": "array",
            "items": { "type": "string" }
          },
          "target_language": {
            "type": "string",
            "description": "Target language (allows cross-language transpilation of logic bricks, e.g., Python to Rust)."
          },
          "integration_spec": {
            "type": "string",
            "description": "Instructions on how the bricks should be wired together or adapted (e.g., 'Expose as an async FastAPI router' or 'Adapt struct to implement serde::Serialize')."
          }
        },
        "required": ["brick_ids", "integration_spec"]
      }
    },
    {
      "name": "trigger_repo_sync",
      "description": "Trigger an incremental Tree-sitter AST crawl and index update on a specific local path or registered repository.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "Absolute local or network path to scan." },
          "compute_embeddings": { "type": "boolean", "default": true }
        },
        "required": ["path"]
      }
    }
  ]
}

---

**Comprehensive Architecture & Concept Description**

**1. Problem Statement**
As personal and organizational codebases scale across multiple drives, archives, and repositories, maintaining cognitive visibility over every written class, utility, and architectural pattern becomes impossible. Valuable, battle-tested logic gets buried in legacy projects, forcing developers and AI coding assistants to repeatedly reinvent solutions from scratch rather than leveraging existing, verified assets.

**2. Proposed Solution**
A sovereign **Code Asset Intelligence & Composable Component Registry** that automatically crawls, parses, and catalogs classes, functions, and modules across distributed storage. Instead of treating code as flat text files, the platform extracts functional signatures, dependencies, and semantic intent to form a searchable library of reusable "software bricks." By exposing this catalog through a **Model Context Protocol (MCP) server**, any external IDE, CLI tool, or autonomous agent can query, retrieve, refactor, and assemble these components into new applications on the fly.

**3. Core Pillars & Capabilities**

- **Distributed AST Ingestion:** Scans heterogeneous drives and Git repositories using language-aware Abstract Syntax Tree (AST) parsing to extract classes, functions, docstrings, type signatures, and dependency graphs as discrete, self-contained units.
- **Hybrid Semantic & Lexical Registry:** Indexes code artifacts by both exact structural signatures (inputs, outputs, dependencies) and natural-language functional descriptions, allowing queries like *"find a thread-safe retry decorator"* or *"retrieve the WebGL camera controller class."*
- **Automated Modularization & Transformation:** Identifies tightly coupled dependencies and isolates target functions or classes into clean, portable building blocks ready for injection into new target environments.
- **Native MCP Server Interface:** Exposes standardized MCP tools and resources (`search_components`, `get_ast_signature`, `extract_brick`, `compose_module`) so LLM agents and orchestrators can autonomously discover and wire existing code into new solutions on demand.

---

**Technical Specification Framing (README / Proposal Style)**

> **Project Concept: Composable Code Intelligence via MCP**
> This system transforms fragmented source code archives into an active, agent-ready component registry. By combining static code analysis with semantic indexing, it catalogs every class and function across local and network drives into a structured knowledge base of reusable software primitives. Through an integrated MCP server, developers and AI agents can dynamically query, adapt, and assemble these verified software bricks to accelerate new system architecture without duplicating past engineering efforts.

---

Here is the complete technical blueprint covering naming candidates, the hybrid storage and AST ingestion schema, the MCP server specification, and a ready-to-use `README.md`.

---

## 1. Project Naming Candidates

| Name | CLI / Crate Slug | Architectural Vibe & Meaning |
| --- | --- | --- |
| **BrickForge** | `brickforge` | Emphasizes extracting raw source code and forging reusable, composable software bricks. |
| **CodeMason** | `codemason` | Focuses on the craft of structural assembly—cutting, indexing, and mortaring proven code blocks together. |
| **ASTVault** | `astvault` | Highlights sovereign, local-first storage backed by strict Abstract Syntax Tree structural parsing. |
| **SynapseBrick** | `synapse-mcp` | Positions the catalog as the neural bridge connecting historical repositories to active AI agents via MCP. |
| **LexiForge** | `lexiforge` | Combines lexical/semantic code indexing with automated component generation and refactoring. |

---

## 2. AST Ingestion Pipeline & Hybrid Storage Schema

To avoid indexing dead code or broken snippets, the ingestion pipeline uses **Tree-sitter** for fast, multi-language AST extraction, **SQLite (with FTS5)** for metadata, exact structural queries, and dependency graphs, and **ChromaDB / `sqlite-vec**` for semantic intent search.

### A. Multi-Language AST Ingestion Pipeline

1. **File Discovery & Hashing:** Crawl target mounts, NAS shares, and Git repositories (respecting `.gitignore`). Compute a SHA-256 hash per file; skip unchanged files on incremental runs.
2. **Tree-sitter Structural Parsing:** Parse source files (`.rs`, `.py`, `.ts`, `.cpp`, `.cs`, `.go`) into concrete syntax trees. Extract top-level and nested symbols (`function_definition`, `class_declaration`, `impl_item`, `struct_item`).
3. **Dependency &Purity Analysis:** Walk child nodes of each symbol to classify imports:

- **Stdlib / External Crates/Packages:** Recorded in `external_deps`.
- **Internal Sibling Calls:** Recorded in `symbol_edges` so extracting a class automatically pulls its required helper functions.
- **Purity Score:** Calculate a `portability_score` (0.0 to 1.0) based on global state mutations, hardcoded paths, and deep coupling.

1. **Semantic Enrichment:** Generate a concise 1–2 sentence functional summary and embedding vector using a local LLM/embedding model (e.g., `qwen2.5-coder` + `snowflake-arctic-embed`), combining the docstring, signature, and AST body.

### B. SQLite Relational, FTS5 & Vector Schema (`schema.sql`)

```sql
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

```

---

## 3. MCP Server Tool, Resource & Prompt Specification

The MCP server exposes deterministic tools for search, structural inspection, dependency-resolved extraction, and adaptation.

### A. MCP Resources (Direct URI Addressing)

- `brick://catalog/stats` — Returns global counts of indexed drives, repositories, languages, and bricks.
- `brick://{brick_id}/source` — Returns raw source code and file origin metadata.
- `brick://{brick_id}/bundle` — Returns the target brick concatenated with all internal helper bricks it depends on.

### B. MCP Tool Definitions (JSON Schema)

```json
{
  "tools": [
    {
      "name": "search_code_bricks",
      "description": "Hybrid semantic (vector) and lexical (BM25 + AST filter) search across all indexed repositories to discover reusable classes, functions, and modules.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "Natural language intent or exact symbol/signature query (e.g., 'thread-safe ring buffer' or 'fn parse_hl7')."
          },
          "languages": {
            "type": "array",
            "items": { "type": "string", "enum": ["rust", "python", "typescript", "cpp", "csharp", "go"] },
            "description": "Filter by programming languages."
          },
          "kinds": {
            "type": "array",
            "items": { "type": "string", "enum": ["function", "class", "struct", "trait", "interface"] }
          },
          "min_portability": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "default": 0.5,
            "description": "Filter out tightly coupled legacy code below this portability threshold."
          },
          "limit": { "type": "integer", "default": 10, "maximum": 50 }
        },
        "required": ["query"]
      }
    },
    {
      "name": "inspect_brick_contract",
      "description": "Retrieve the AST signature, docstring, external package requirements, and internal dependency tree of a specific brick without loading its full implementation body (saves context window).",
      "inputSchema": {
        "type": "object",
        "properties": {
          "brick_id": { "type": "string", "description": "Unique hash ID of the code brick." },
          "dependency_depth": { "type": "integer", "default": 2, "maximum": 5 }
        },
        "required": ["brick_id"]
      }
    },
    {
      "name": "extract_composable_bundle",
      "description": "Extract a code brick along with its transitive internal helper functions/types and required import headers as a self-contained, ready-to-compile code block.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "brick_ids": {
            "type": "array",
            "items": { "type": "string" },
            "description": "One or more brick IDs to bundle together."
          },
          "include_internal_deps": {
            "type": "boolean",
            "default": true,
            "description": "Automatically resolve and inline sibling helper functions/structs referenced in the AST."
          },
          "strip_repo_specifics": {
            "type": "boolean",
            "default": true,
            "description": "Rewrite internal module paths to flat/local scope imports."
          }
        },
        "required": ["brick_ids"]
      }
    },
    {
      "name": "compose_and_adapt_bricks",
      "description": "Synthesize or refactor one or more catalog bricks to fit a target architecture, language version, or interface contract.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "brick_ids": {
            "type": "array",
            "items": { "type": "string" }
          },
          "target_language": {
            "type": "string",
            "description": "Target language (allows cross-language transpilation of logic bricks, e.g., Python to Rust)."
          },
          "integration_spec": {
            "type": "string",
            "description": "Instructions on how the bricks should be wired together or adapted (e.g., 'Expose as an async FastAPI router' or 'Adapt struct to implement serde::Serialize')."
          }
        },
        "required": ["brick_ids", "integration_spec"]
      }
    },
    {
      "name": "trigger_repo_sync",
      "description": "Trigger an incremental Tree-sitter AST crawl and index update on a specific local path or registered repository.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "Absolute local or network path to scan." },
          "compute_embeddings": { "type": "boolean", "default": true }
        },
        "required": ["path"]
      }
    }
  ]
}

```

---

## 4. Complete Project `README.md`

```markdown
# BrickForge (`brickforge-mcp`)

> **Sovereign AST Code Intelligence & Composable Component Registry for AI Agents and Engineers.**

`BrickForge` crawls distributed local drives, NAS archives, and multi-language Git repositories to catalog every class, function, struct, and module into a unified, queryable knowledge base. Exposed via a native **Model Context Protocol (MCP)** server, it empowers developers and autonomous coding agents to discover, extract, and assemble battle-tested "software bricks" on demand—eliminating redundant engineering.

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
# Initialize the local SQLite + Vector catalog
brickforge init --db ~/.brickforge/catalog.db

# Register and crawl source directories across drives
brickforge scan "D:/Projects" "Z:/NAS_Archive/Repositories" \
  --languages rust,python,typescript,cpp \
  --embed-model snowflake-arctic-embed


### 2. CLI Search & Extraction

```bash
# Hybrid semantic + lexical search from terminal
brickforge search "exponential backoff retry with jitter" --lang rust --min-portability 0.7

# Extract a brick and all its required sibling helpers into a standalone file
brickforge extract <brick_id> --bundle-deps --output ./src/utils/retry.rs

```

### 3. Configure MCP Client (`mcp_config.json`)

Add `brickforge-mcp` to your IDE or agent orchestrator configuration:

```json
{
  "mcpServers": {
    "brickforge": {
      "command": "brickforge-mcp",
      "args": [
        "--db", "C:/Users/username/.brickforge/catalog.db",
        "--ollama-url", "[http://127.0.0.1:11434](http://127.0.0.1:11434)"
      ],
      "env": {
        "RUST_LOG": "info"
      }
    }
  }
}

```

---

## Example Agent Workflow

1. **Agent Prompt:** *"Build a telemetry ingestion service in Python that parses HL7 messages and streams them over WebSockets."*
2. **Discovery:** Agent calls `search_code_bricks(query="HL7 parser", languages=["python"])` and `search_code_bricks(query="async websocket broadcaster", languages=["python"])`.
3. **Contract Check:** Agent calls `inspect_brick_contract` on the top two hits to verify input/output types and external dependencies.
4. **Extraction & Composition:** Agent calls `extract_composable_bundle(brick_ids=["b_8f92a", "b_31c04"], include_internal_deps=true)` and wires the two proven modules together in seconds.

---

## Roadmap

- [x] Phase 1: Tree-sitter AST extractor & SQLite FTS5 catalog
- [x] Phase 2: Local Ollama semantic summarization & `sqlite-vec` hybrid ranking
- [ ] Phase 3: Transitive intra-repository call-graph bundler
- [ ] Phase 4: Automated unit-test discovery (link bricks to their existing `#[test]` / `pytest` cases)
- [ ] Phase 5: 3D WebGL dependency cluster explorer

```

```
