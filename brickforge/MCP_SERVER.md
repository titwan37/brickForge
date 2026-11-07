# BrickForge MCP server — interface and endpoint design

## 1. Scope

The MCP server exposes the catalog to IDEs, coding agents, and other software. It should remain a thin, permission-aware adapter over the storage/search/extraction services. It should not crawl arbitrary paths, execute source code, or silently modify registered repositories.

The manifest in `mcp-tools.json` is the draft project contract for tools, output schemas, resources, and transports. Implement the definitions with the selected MCP SDK and validate them through an MCP client integration test.

## 2. Transports and endpoints

### Local transport: stdio

Proposed invocation:

```bash
brickforge-mcp --db ~/.brickforge/catalog.db --transport stdio
```

The MCP client launches the server as a subprocess. Standard input/output are reserved for MCP messages; write logs and diagnostics to standard error only.

### Remote transport: Streamable HTTP

Proposed endpoint:

```text
POST https://<configured-host>/mcp
```

Use the current MCP Streamable HTTP transport, not the legacy HTTP+SSE transport. The current `2026-07-28` revision describes a single MCP endpoint, POST-based requests, and request-scoped JSON or SSE responses; it removes the old GET stream endpoint and protocol-level sessions. Implement the revision's required protocol/method/tool headers (including `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name`) as specified by the selected SDK. Because client and SDK adoption can vary, pin the target protocol/SDK version and add compatibility tests for every supported client.

### Optional operational endpoints (not MCP protocol methods)

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/healthz` | Process liveness only |
| `GET` | `/readyz` | Readiness: database open, migrations current, required extensions loaded |
| `GET` | `/metrics` | Optional local operational metrics; disable or protect on remote deployments |

These are ordinary operational HTTP routes. MCP operations still go through `/mcp`.

## 3. MCP tools

| Tool | Responsibility | Side effects |
|---|---|---|
| `get_catalog_stats` | Counts, languages, index health | Read only |
| `list_repositories` | List registered roots by safe public metadata | Read only |
| `sync_repository` | Queue an incremental scan for a registered repository ID | Writes catalog/index data; does not modify source files |
| `get_scan_status` | Poll a scan run | Read only |
| `search_code_bricks` | Hybrid search with language/kind/repository filters | Read only |
| `inspect_brick_contract` | Contract, provenance, dependencies, external packages, reuse factors | Read only |
| `extract_composable_bundle` | Dependency closure, imports, source slices, unresolved dependency report | Read only; bounded output |
| `compose_and_adapt_bricks` | Optional local-model composition/adaptation proposal | No source-repository writes; validation not run by default |

The input and output JSON Schemas are defined in `mcp-tools.json`. Keep tool names stable once clients depend on them; add optional parameters rather than changing meanings silently.

### Why repository registration is not an MCP tool

Root registration is an administrative operation that grants the indexer access to local or network paths. Keep it in the local CLI or trusted desktop UI (`brickforge add-root ...`). Remote agents receive only repository IDs from `list_repositories` and can request scans for those IDs. This is a deliberate least-privilege boundary.

### Why composition is separate from extraction

Extraction is deterministic retrieval of existing code plus resolved dependencies. Composition may involve an LLM, changes interfaces, introduces new code, and needs validation. Keep it optional and clearly label the result as a proposal. Never say “compiled”, “tested”, or “ready to ship” unless an isolated validator has actually run and returned evidence.

## 4. Resources

- `brick://catalog/stats` — overall catalog health and counts.
- `brick://repositories/{repository_id}` — safe repository metadata.
- `brick://bricks/{brick_id}/contract` — lightweight contract and provenance.
- `brick://bricks/{brick_id}/source` — exact selected source slice.
- `brick://bricks/{brick_id}/dependencies` — resolved/unresolved edges.

Use tools for parameterized search and dependency bundle extraction. Resources are best for direct reads of a known item.

## 5. Tool behavior contracts

### Search

- Return compact hits, never full implementation bodies by default.
- Use hybrid rank fusion when both FTS5 and vectors are available; fall back to lexical search when vector extension/model is unavailable.
- Include repository label, relative path, line range, signature, portability score, and unresolved dependency count.
- Distinguish `lexical_only`, `vector_only`, and `hybrid` modes in output.

### Inspection

- Return the function/class contract without implementation body.
- Include origin and source hash so consumers can trace the indexed content.
- Explain portability factors; a scalar score without its rationale is insufficient.

### Extraction

- Enforce maximum brick count, dependency depth, and output byte/token budget.
- Include resolved dependencies in deterministic order where possible; report cycles.
- Preserve original imports/module paths by default.
- Return external package requirements and unresolved references separately.
- Mark validation as `not_run` until an external validation stage has executed.

### Composition

- Require an explicit integration specification and selected brick IDs.
- Prefer local generation backend; clearly show which model/provider was used.
- Return assumptions, generated candidate artifacts, adaptation notes, and a validation plan.
- Do not write to indexed repositories. Any future “apply patch” capability should be a separate, explicit tool with preview, destination allow-list, and user approval.

### Synchronization

- Accept `repository_id`, never a raw path.
- Run in a background job queue if a scan can exceed a short MCP request window; return `scan_run_id` and expose `get_scan_status`.
- Do not delete previously indexed symbols when a parser fails. Reconcile deletions only after a successful complete scan.

## 6. Security controls

1. Bind local HTTP deployments to `127.0.0.1` by default.
2. Validate HTTP `Origin` values to mitigate DNS rebinding; do not use wildcard origins for privileged local services.
3. Require authentication for remote connections and authorize each repository ID and tool operation.
4. Apply per-client rate limits, scan concurrency limits, maximum result sizes, and extraction budgets.
5. Redact absolute root paths from ordinary tool responses; return repository labels and relative paths.
6. Do not accept filesystem paths, shell commands, or arbitrary output destinations from remote MCP callers.
7. Treat source code and generated code as untrusted content. Do not execute it in the MCP process.
8. Keep secrets/configuration exclusions in the scanner, while still allowing explicit, reviewed overrides in local configuration.

## 7. Suggested implementation sequence

1. Implement `get_catalog_stats`, `list_repositories`, `search_code_bricks`, and `inspect_brick_contract` against a seeded SQLite catalog.
2. Add stdio transport and test with a real MCP host.
3. Implement scan queue/status and expose `sync_repository`.
4. Implement bounded dependency closure and bundle manifest.
5. Add Streamable HTTP with auth and Origin checks.
6. Add optional local-model composition.
7. Add sandboxed validation as a separate service/tool after extraction is reliable.

## 8. Protocol references

The target protocol revision in this draft is `2026-07-28`. Check client/SDK compatibility before adopting it in production:

- [MCP 2026-07-28 specification announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [MCP TypeScript SDK v2 documentation](https://ts.sdk.modelcontextprotocol.io/v2/)
- [MCP transport documentation (2025-11-25 revision)](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/basic/transports.mdx)
- [SQLite FTS5 external-content table and trigger guidance](https://www.sqlite.org/fts5.html)
- [sqlite-vec project and current pre-v1 status](https://github.com/asg017/sqlite-vec)
