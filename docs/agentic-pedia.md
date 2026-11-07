# BrickForge — project design pack

Design pack generated

&#x20;v0.1 · 6 files

I recommend keeping BrickForge as the working name.

The central idea is to build more than a code search engine: a **personal software asset registry** that remembers what you have already built, understands how components work, identifies their dependencies, and makes them reusable by developers and AI agents.

[Guía de CodeGraph: Grafo de conocimiento de código local para agentes de IA](https://images.openai.com/static-rsc-4/i8T_zdkkcGduCO3f7JYM3Ye7uhkNdp5-wSyWkRVg7z7L4763vkNHIi0teIswQBVq2K9m-deWLAMwT5PuOtGDRMlARhUcQbWBD2kRIlogyCmsGVTnKW6WBdtZJ2Bhnm2Gx45REumqo9M5hvAI8YPOSK_cbKNd6o_OgadIeH4KWJc?purpose=inline)

[agentpedia.codes](https://agentpedia.codes/es/blog/codegraph-guide?utm_source=chatgpt.com)

# Discover → Understand → Extract → Compose → Validate

The proposed lifecycle for turning scattered source code into reusable software assets.

## 1. Project README and naming

Completed

Recommended name: BrickForge

| Candidate  | Positioning                                 |
| ---------- | ------------------------------------------- |
| BrickForge | Discover and forge reusable software bricks |
| CodeMason  | Assemble existing components into solutions |
| ASTVault   | Structured AST-aware code archive           |
| CodeAtlas  | Map code across repositories                |
| ReuseGraph | Explore dependencies and component reuse    |
| LexiForge  | Semantic search and code transformation     |

The README includes the vision, product principles, architecture, proposed CLI, roadmap, security notes, and naming alternatives.

Open README.md

## 2. AST ingestion and SQLite/Vector schema

Completed

The proposed ingestion pipeline:

 | ID | Process | Description |  
 | --- | --- | --- |
 | 01 | Source discovery | Drives, NAS, Git working trees |
 | 02 | Incremental scanner | SHA-256, exclusions, change detection |
 | 03 | AST extraction | Tree-sitter symbols, signatures, source spans |
 | 04 | Dependency analysis | Calls, imports, inheritance, unresolved references |
 | 05 | Semantic enrichment | Summaries, tags, embeddings, portability signals |
 | 06 | Knowledge base | SQLite, FTS5 and optional sqlite-vec |

The relational model includes:

- `repositories` and `scan_runs`
- `source_files`
- `code_bricks`
- `brick_dependencies`
- `external_packages`
- `brick_embedding_state`
- `bricks_fts`
- Optional `brick_embeddings`

I separated the vector extension into its own SQL migration so the core database can be initialized without loading sqlite-vec.

Important corrections: the original dependency primary key used an expression unsupported by SQLite. The new version uses a surrogate key and partial unique indexes. FTS5 synchronization triggers are also included, following SQLite's external-content indexing requirements.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.sqlite.org\&sz=32)

SQLite

Files:

- Core SQLite schema
- Optional vector schema
- AST ingestion and storage architecture

## 3. MCP server tools and endpoints

Completed

I have defined eight MCP tools.

| Tool                        | Function                               |
| --------------------------- | -------------------------------------- |
| `get_catalog_stats`         | Catalog statistics and health          |
| `list_repositories`         | List registered source repositories    |
| `sync_repository`           | Trigger an incremental scan            |
| `get_scan_status`           | Follow scan progress                   |
| `search_code_bricks`        | Hybrid semantic and lexical search     |
| `inspect_brick_contract`    | Inspect signature and dependencies     |
| `extract_composable_bundle` | Extract code and internal dependencies |
| `compose_and_adapt_bricks`  | Generate an adaptation proposal        |

The server also exposes resource templates for repository metadata, brick contracts, source code, and dependency graphs.

Transport design

Local integration

stdio

Preferred locally

IDEs and agents launch `brickforge-mcp` as a local process.

Remote integration

Streamable HTTP

`POST /mcp`

Authenticated access for remote agents and software.

Operational endpoints\
`GET /healthz` · `GET /readyz` · optional `GET /metrics`

I have targeted the MCP `2026-07-28` protocol revision, which uses the newer stateless Streamable HTTP design. Client compatibility should be tested before choosing the SDK for implementation.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://blog.modelcontextprotocol.io\&sz=32)

Model Context Protocol Blog+1

Files:

- MCP tool definitions — JSON
- MCP server interface and endpoint design

## 4. Complete project pack

BrickForge project pack

ZIP · README, architecture, SQL schemas, MCP JSON and server design

6 files · approximately 20 KB

&#x20;Download

## 5. One architectural recommendation

I would keep three responsibilities deliberately separate:

1. BrickForge Core — indexing, AST analysis, storage, search and provenance.
2. BrickForge MCP — controlled access to existing software assets.
3. BrickForge Agent — reasoning, selecting bricks, composing solutions, adapting code and validating the result.

This separation is important. The catalog should remain reliable and deterministic even when the AI model or composition strategy changes.

Also, a portability score should remain an explainable heuristic, not a guarantee that code will compile independently. Actual validation belongs in a separate, isolated execution environment.

Suggested next milestone: implement one complete vertical slice with Python: scan a registered directory, index functions and classes, search them, inspect their contracts, and extract one component with its dependencies. That would prove the whole concept before expanding to six languages.

Would a check-in tomorrow to turn this design into a prioritized MVP implementation backlog with atomic tasks and acceptance criteria be useful?

🧱BrickForge MVP planning check-inTap to set up

---

I'll create a dedicated `tasks.json` for BrickForge, using the structure and execution conventions of your uploaded `tasks-transformation.json`.

The backlog will contain 40+ atomic implementation tasks, organized around the five lifecycle phases:

1. Discover — register repositories, scan drives and detect changes.
2. Understand — parse ASTs, identify symbols and build dependency relationships.
3. Extract — retrieve reusable components and their dependencies.
4. Compose — assemble and adapt components to new requirements.
5. Validate — compile, test, inspect and approve generated components.

The first implementation milestone will remain deliberately focused on a working Python vertical slice, rather than attempting multi-language support immediately.

45 tasks created and validated

## Download

tasks.json

45 atomic tasks · JSON · UTF-8

&#x20;Download

## Task distribution

| Lifecycle phase | Tasks |
| --------------- | ----- |
| Discover        | 10    |
| Understand      | 10    |
| Extract         | 8     |
| Compose         | 7     |
| Validate        | 10    |
| Total           | 45    |

## Execution conventions

The file follows your existing task transformation format:

- Stable task IDs: `BRICKFORGE-MVP-001` to `BRICKFORGE-MVP-045`.
- Explicit dependencies between tasks.
- Priorities P0, P1 and P2.
- Allowed file paths.
- Verification and test commands.
- Acceptance criteria.
- Retry and failure policies.
- Initial status: `pending`.

I also validated the JSON structure and checked that all dependency references point to existing tasks.

My recommendation: execute P0 tasks first, with a working Python-only vertical slice as the first release gate. Keep Compose and advanced semantic/vector capabilities extensible rather than making them prerequisites for the first functional catalog.
