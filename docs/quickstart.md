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

---

Analyzed repositories.json:L1-103
Analyzed sync_repositories.py:L1-83
Analyzed planner.py:L95-160
Analyzed ignore_rules.py:L25-50
Analyzed database.py:L15-50
Edited sync_repositories.py
Edited repositories.json
Ran test sync_repositories with --no-scan
Ran test sync_repositories help
Analyzed pushtoGit.bat:L1-15
Ran run unit tests
Checked task Run unit tests

### Review of `config/repositories.json` & `scripts/sync_repositories.py`

Both files have been reviewed and refined to work seamlessly together.

---

### 1. Review of `config/repositories.json`

**Status**: **Valid & Production Ready**

- **Structure**: Clean, valid JSON structure with 8 repository roots across `C:`, `L:`, `G:`, OneDrive, and Visual Studio versions.
- **Path Escaping**: All Windows backslashes (`\\`) are correctly escaped.
- **Exclusion Rules**: 
  - Standard development artifacts are excluded (`.git`, `.venv`, `node_modules`).
  - Visual Studio build directories (`bin/`, `obj/`, `.vs/`, `Debug/`, `Release/`, `ipch/`) and compiler metadata (`*.sdf`, `*.suo`) are filtered out.
  - Added protections for `dev-c`: excludes database binaries (`*.db`, `*.sqlite`, `**/data/**`) and pytest cache (`**/.pytest_cache/**`), preventing internal database files from being indexed as code.

---

### 2. Review of `scripts/sync_repositories.py`

**Status**: **Enhanced & Tested**

The script has been updated with several key improvements:
1. **Automatic Path Resolution**: Automatically checks `config/repositories.json` by default (as well as `repositories.json` in the root).
2. **Custom Ignore Enforcement**: Directly injects the `exclude_globs` configured for each repository into `IgnoreRules` during scan planning.
3. **Database Migration & Auto-Creation**: Applies migrations and creates `data/brickforge.db` if it doesn't already exist.
4. **CLI Argument Parser (`argparse`)**:
   - `--config PATH`: Specify a custom config file.
   - `--repo ID`: Scan only a single repository (e.g. `--repo dev-c` or `--repo vs-2019`).
   - `--no-scan`: Sync and register the repositories in the database without immediately triggering a full scan.
   - `--force`: Force re-indexing of unchanged files.
5. **Safe Inaccessible Path Handling**: If a cloud drive (`L:\My Drive` or `G:\My Drive`) or disconnected drive is not accessible, it logs a clear `[WARN]` and proceeds with the other repositories rather than crashing.

---

### 3. How to Use

Open your terminal in `c:\Dev\brickForge`:

#### Option A: Register Repositories Without Scanning Immediately
Quickly syncs your 8 repository definitions into the SQLite catalog:
```powershell
python scripts/sync_repositories.py --no-scan
```
*Output:*
```text
[BrickForge] Loading repository configuration: C:\Dev\brickForge\config\repositories.json
[BrickForge] Synced 8 repositories into catalog: C:\Dev\brickForge\data\brickforge.db
[BrickForge] Scan skipped (--no-scan). Repositories are registered.
```

#### Option B: Scan a Single Repository
If you want to test indexing on a specific repository first (e.g. `dev-c`):
```powershell
python scripts/sync_repositories.py --repo dev-c
```

#### Option C: Full Sync and Scan of All Enabled Repositories
Scans all 8 repositories, discovers AST symbols, and indexes them into the catalog:
```powershell
python scripts/sync_repositories.py
```

#### Option D: Force a Complete Re-index
Bypasses the SHA-256 cache and forces all files to be re-parsed:
```powershell
python scripts/sync_repositories.py --force
```

---

### 4. Searching Your Indexed Repositories

Once scanned, you can query your newly built code catalog:

```powershell
# Search using the BrickForge CLI
python -m brickforge search "your_function_or_class_name"
```

Or query via Python:
```python
from pathlib import Path
from brickforge.storage.database import DatabaseManager
from brickforge.search.service import CatalogSearchService, CatalogQuery

db_mgr = DatabaseManager(db_path=Path("data/brickforge.db"))
search = CatalogSearchService(db_mgr)

# Search across all 8 repositories
hits = search.search(CatalogQuery(query="UserService", limit=10))
for hit in hits:
    print(f"{hit.symbol_name} ({hit.kind}) in [{hit.repository_id}] {hit.relative_path}")
```