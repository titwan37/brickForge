# BrickForge (`brickforge`)

> **Sovereign AST Code Intelligence & Composable Component Registry for AI Agents and Engineers.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: MVP Complete](https://img.shields.io/badge/status-MVP%20Complete-brightgreen.svg)]()

---

## 🎯 Vision & Value Proposition

In modern software organizations, code components, utility functions, schemas, and algorithms are often fragmented across multiple micro-repositories or mono-repo silos. **BrickForge** acts as an autonomous indexing forge:
- **Discovers and Indexes**: Statically parses and registers reusable code modules ("Bricks") across local repositories into an authoritative SQLite catalog.
- **Extracts Contracts**: Captures type-annotated signatures, docstrings, parameters, return types, and pure-function invariants without running the source code.
- **Resolves Dependency Graphs**: Traverses calls and inheritance hierarchies to assemble self-contained source bundles with rewritten imports and provenance manifests.
- **Composes & Adapts**: Generates adaptation proposals for target environments with unified diffs, licensing reports, and review workflows.
- **Validates in Isolation**: Automatically tests extracted bundles using syntax compilation, dependency checks, and unit test harnesses.
- **Agent Integration**: Exposes a Model Context Protocol (MCP) server for seamless discovery by AI coding agents (Antigravity, Claude Code, Cursor, Copilot).

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph StorageLayer["💾 Storage & Persistence"]
        DB[("SQLite Catalog (WAL mode)<br/>bricks, dependencies, FTS5 index")]
    end

    subgraph IngestionEngine["⚙️ Phase 1 & 2: Ingestion & Understanding"]
        Discovery["File Discovery & Walker<br/>src/brickforge/ingestion/discovery.py"]
        Ignore["Security & Ignore Filter<br/>src/brickforge/ingestion/ignore_rules.py"]
        Planner["Incremental Scan Planner<br/>src/brickforge/ingestion/planner.py"]
        Parser["AST & Tree-Sitter Parser<br/>src/brickforge/parsers/"]
        Analysis["Imports & Dependencies<br/>src/brickforge/analysis/"]
    end

    subgraph ServiceEngine["🔍 Phase 3 & 4: Search, Extraction & Composition"]
        Search["FTS5 & Lexical Search<br/>src/brickforge/search/"]
        Contracts["Contract Inspection<br/>src/brickforge/contracts.py"]
        Bundler["Source Bundler & Rewriter<br/>src/brickforge/extraction/"]
        Composition["Composition & Adaptation<br/>src/brickforge/composition/"]
        Validation["Isolated Validation Runner<br/>src/brickforge/validation/"]
    end

    Discovery --> Ignore --> Planner --> Parser --> Analysis --> DB
    DB --> Search --> Contracts --> Bundler --> Composition --> Validation
```

---

## 📂 Repository Layout

```text
c:\Dev\brickForge
├── docs/                  # Documentation & operational guides
│   ├── quickstart.md      # Getting started, CLI, Python API, and database ops
│   ├── security.md        # Security boundaries, traversal checks, and execution guarantees
│   ├── ARCHITECTURE.md    # Detailed architectural specifications
│   └── DESIGN_PACK.md     # Engineering lifecycle and roadmap
├── src/brickforge/        # Primary Python source package
│   ├── analysis/          # Call graphs, dependencies, and symbol indexing
│   ├── composition/       # Composition models, adaptation service, and approval workflow
│   ├── extraction/        # Bundling, import rewriter, manifest, and output formatters
│   ├── ingestion/         # Discovery, fingerprints, path sanitization, and scan planner
│   ├── parsers/           # Python AST and Tree-Sitter error recovery runtime
│   ├── search/            # SQLite FTS5 search service and query models
│   ├── storage/           # SQLite migrations, connection manager, and brick repository
│   ├── validation/        # Isolated test runners, syntax checking, and validation reports
│   └── cli.py             # CLI commands (init, scan, search)
├── tasks/                 # Task tracking manifests (tasks.json)
├── tests/                 # Automated test suite
│   ├── unit/              # Fast unit test coverage
│   ├── integration/       # Database, FTS, and persistence integration tests
│   ├── e2e/               # End-to-end vertical slice & incremental indexing tests
│   ├── security/          # Filesystem boundary, symlink, and traversal security tests
│   └── performance/       # Ingestion throughput and search latency baseline tests
└── pyproject.toml         # Packaging specification
```

---

## 🚀 Quickstart

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/titwan37/brickForge.git
cd brickForge

# Install editable package
python -m pip install -e .
```

Verify installation:
```bash
python -m brickforge --help
```

### 2. Basic Operations

```bash
# Initialize local SQLite catalog and search tables
python -m brickforge init

# Scan a local repository
python -m brickforge scan --repo-path /path/to/my-repo --repo-id my-repo

# Search for components in the catalog
python -m brickforge search "calculate_total"
```

For detailed CLI and Python API examples, see [docs/quickstart.md](file:///C:/Dev/brickForge/docs/quickstart.md).

---

## 🔒 Security Model

BrickForge adheres to strict security invariants:
1. **Never Executes Scanned Code**: All parsing and analysis is strictly static via `ast.parse` and tree-sitter.
2. **Filesystem Boundaries**: Enforces `safe_path_canonicalization` to block parent traversal (`../`) and external symlink escape.
3. **Sensitive File Filtering**: Automatically ignores `.git`, `.env`, `.venv`, `node_modules`, and credentials.
4. **Allowlisted Exports**: Composed code is only exported to explicitly permitted destination paths.
5. **Subprocess Isolation**: Validation runs in isolated subprocesses with enforced timeouts.

For complete details, see [docs/security.md](file:///C:/Dev/brickForge/docs/security.md).

---

## 🧪 Running Tests

Always execute tests using the Python module invocation:

```bash
# Run all unit tests
python -m pytest tests/unit/

# Run integration tests
python -m pytest tests/integration/

# Run end-to-end tests
python -m pytest tests/e2e/

# Run security boundary tests
python -m pytest tests/security/

# Run performance baseline tests
python -m pytest tests/performance/

# Run full test suite
python -m pytest
```

---

## 📜 License
MIT License. Crafted for resilient autonomous software development.
