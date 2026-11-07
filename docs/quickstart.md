# BrickForge MVP Quickstart & Operations Guide

BrickForge is a sovereign AST-aware code intelligence and composable component registry designed for AI agents and engineering teams. It parses and indexes local repositories into a structured, searchable SQLite database with full contract extraction, dependency resolution, safe bundling, and isolated validation.

---

## 1. Installation & Environment

### Prerequisites
- Python 3.10+ (tested on Python 3.12, 3.13, and 3.14)
- Git (optional, for repository tracking)

### Setup
```bash
# Clone the repository
git clone https://github.com/titwan37/brickForge.git
cd brickForge

# Install editable package with core dependencies
python -m pip install -e .

# Or install with dev & testing dependencies
python -m pip install -e ".[dev]"
```

Verify installation:
```bash
python -m brickforge --help
```

---

## 2. CLI Operations

### Initialize the SQLite Catalog
Creates the database schema, SQLite WAL mode, and FTS5 search tables:
```bash
python -m brickforge init
# Options:
#   --db-path PATH    Custom path for sqlite catalog (default: brickforge.db)
```

### Scan and Index Repositories
Scans registered repository roots, extracts AST symbols, records dependencies, and populates the FTS5 index:
```bash
python -m brickforge scan --repo-path /path/to/my-repo --repo-id my-repo
```

### Search the Brick Catalog
Search functions, classes, and methods across all indexed code:
```bash
python -m brickforge search "calculate_total"
```

---

## 3. Python API Usage

### Repository Registration & Scan Planning
```python
from pathlib import Path
from brickforge.storage.database import DatabaseManager
from brickforge.storage.brick_repository import BrickRepository
from brickforge.ingestion.planner import ScanPlanner
from brickforge.ingestion.pipeline import IngestionPipeline

db_mgr = DatabaseManager(db_path=Path("brickforge.db"))
db_mgr.apply_migrations()

# Register repository
with db_mgr.connection() as conn:
    conn.execute(
        "INSERT OR IGNORE INTO repositories (id, name, root_path) VALUES (?, ?, ?);",
        ("core-utils", "Core Utilities", str(Path("./my-repo").resolve())),
    )
    conn.commit()

# Plan incremental scan
planner = ScanPlanner(db_mgr)
plan = planner.plan_repository_scan("core-utils", Path("./my-repo"))

print(f"Files to add: {len(plan.added)}, changed: {len(plan.changed)}, skipped: {len(plan.unchanged)}")

# Ingest added & changed files
brick_repo = BrickRepository(db_mgr)
pipeline = IngestionPipeline("core-utils", brick_repo, root_path=Path("./my-repo"))

for action in plan.added + plan.changed:
    pipeline.process_file_on_disk(action.relative_path)

planner.finalize_scan_run(plan.scan_run_id, status="completed")
```

### Catalog Search & Contract Inspection
```python
from brickforge.search.service import CatalogSearchService, CatalogQuery
from brickforge.contracts import BrickContract

search_service = CatalogSearchService(db_mgr)
results = search_service.search(CatalogQuery(query="hash_password", limit=5))

for hit in results:
    print(f"Brick ID: {hit.brick_id}")
    print(f"Symbol: {hit.symbol_name} ({hit.kind}) in {hit.relative_path}")
    
    # Load contract
    contract = BrickContract.from_brick(hit.brick)
    print(f"Signature: {contract.signature}")
    print(f"Parameters: {contract.parameters}")
    print(f"Return type: {contract.return_type}")
    print(f"Docstring: {contract.docstring}")
```

### Dependency Traversal & Bundling
```python
from brickforge.analysis.graph import DependencyGraphService
from brickforge.extraction.bundler import ExtractionBundler

# Resolve dependencies
graph_service = DependencyGraphService(db_mgr)
target_brick_id = results[0].brick_id
resolved_brick_ids = graph_service.get_transitive_dependencies(target_brick_id)

# Create self-contained source bundle
bundler = ExtractionBundler(brick_repo)
bundle = bundler.bundle(target_brick_id=target_brick_id, max_depth=5)

print(bundle.bundled_source)
print(f"External package dependencies: {bundle.external_packages}")
```

### Isolated Validation
```python
from brickforge.validation.runner import IsolatedValidationRunner
from brickforge.validation.report import ValidationReport

runner = IsolatedValidationRunner(timeout_seconds=15)
report: ValidationReport = runner.validate_source_bundle(bundle.bundled_source)

print(f"Validation status: {report.status}")
print(f"Compile check: {report.checks.get('python_syntax')}")
```

---

## 4. Database Operations & Backups

BrickForge stores all indexed metadata, symbols, dependency edges, and FTS5 indices in SQLite.

### Online Safe Backup
Because BrickForge uses SQLite WAL (Write-Ahead Logging) mode, you can safely perform online non-blocking backups without stopping active indexing:

```python
import sqlite3

def backup_catalog(source_db_path: str, backup_dest_path: str):
    src = sqlite3.connect(source_db_path)
    dst = sqlite3.connect(backup_dest_path)
    with dst:
        src.backup(dst, pages=100)
    src.close()
    dst.close()

backup_catalog("brickforge.db", "brickforge_backup.db")
```

### Database Optimization (Vacuum & Prune)
To reclaim disk space after large repository deletions or updates:
```python
with db_mgr.connection() as conn:
    conn.execute("VACUUM;")
```

---

## 5. Known Limitations (MVP Scope)

1. **Language Focus**: The MVP focuses on Python 3 (`.py`, `.pyi`) as the primary language tier, utilizing both standard `ast` and tree-sitter error recovery. Additional languages (TypeScript, Go, Rust) use regex/heuristic language adapters in MVP.
2. **Dynamic Metaprogramming**: Symbols created purely dynamically at runtime via `setattr`, `globals()`, or `eval` cannot be captured statically.
3. **Complex Type Inference**: Parameter and return types are extracted from AST type annotations and docstrings. Deep cross-module symbolic type inference is planned for v2.
4. **Environment Isolation**: The validation runner validates syntax, imports, and self-contained tests. Isolated container/virtualenv sandbox creation is supported via subprocess boundaries.

