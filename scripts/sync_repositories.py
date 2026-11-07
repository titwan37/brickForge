"""Synchronize repository catalog from JSON configuration and trigger incremental scans.

Usage:
    python scripts/sync_repositories.py
    python scripts/sync_repositories.py --config config/repositories.json
    python scripts/sync_repositories.py --repo dev-c
    python scripts/sync_repositories.py --no-scan
    python scripts/sync_repositories.py --force
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional

from brickforge.ingestion.ignore_rules import IgnoreRules
from brickforge.ingestion.pipeline import IngestionPipeline
from brickforge.ingestion.planner import ScanPlanner
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager


def find_config_file(explicit_path: Optional[str] = None) -> Path:
    """Resolve the repositories.json path from explicit argument or standard locations."""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified configuration file not found: {explicit_path}")

    candidates = [
        Path("config/repositories.json"),
        Path("repositories.json"),
        Path(__file__).parent.parent / "config" / "repositories.json",
        Path(__file__).parent.parent / "repositories.json",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    raise FileNotFoundError(
        "Could not find 'repositories.json'. Checked 'config/repositories.json' and 'repositories.json'."
    )


def sync_config(
    config_path: Optional[str] = None,
    scan_after_sync: bool = True,
    target_repo_id: Optional[str] = None,
    force_full_scan: bool = False,
) -> None:
    config_file = find_config_file(config_path)
    print(f"[BrickForge] Loading repository configuration: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    db_rel_or_abs = data.get("catalog_db", "data/brickforge.db")
    db_path = Path(db_rel_or_abs)
    # If path is relative, resolve relative to project root (or config directory)
    if not db_path.is_absolute():
        project_root = config_file.parent.parent if config_file.parent.name == "config" else config_file.parent
        db_path = (project_root / db_path).resolve()

    db_mgr = DatabaseManager(db_path=db_path)
    db_mgr.apply_migrations()

    brick_repo = BrickRepository(db_mgr)
    planner = ScanPlanner(db_mgr)

    repos: List[dict] = data.get("repositories", [])
    if not repos:
        print("[BrickForge] Warning: No repositories defined in configuration.")
        return

    # 1. Register or update repositories in SQLite
    with db_mgr.connection() as conn:
        for repo in repos:
            conn.execute(
                """
                INSERT INTO repositories (
                    id, name, root_path, source_kind, enabled, exclude_globs
                ) VALUES (?, ?, ?, 'directory', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    root_path = excluded.root_path,
                    enabled = excluded.enabled,
                    exclude_globs = excluded.exclude_globs,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    repo["id"],
                    repo["name"],
                    repo["root_path"],
                    1 if repo.get("enabled", True) else 0,
                    json.dumps(repo.get("exclude_globs", [])),
                ),
            )
        conn.commit()

    print(f"[BrickForge] Synced {len(repos)} repositories into catalog: {db_path}\n")

    # 2. Scan repositories
    if not scan_after_sync:
        print("[BrickForge] Scan skipped (--no-scan). Repositories are registered.")
        return

    total_scanned_repos = 0
    total_indexed_symbols = 0

    for repo in repos:
        repo_id = repo["id"]
        if target_repo_id and repo_id != target_repo_id:
            continue

        if not repo.get("enabled", True):
            print(f"[SKIP] '{repo['name']}' ({repo_id}) is disabled in configuration.")
            continue

        root = Path(repo["root_path"])
        if not root.exists():
            print(f"[WARN] Root path inaccessible or offline: '{root}' (Repo: {repo_id})")
            continue

        print(f"============================================================")
        print(f"Scanning Repository: {repo['name']} [{repo_id}]")
        print(f"Path: {root}")
        print(f"============================================================")

        # Configure ignore rules with repo-specific exclude globs
        ignore_rules = IgnoreRules()
        custom_excludes = repo.get("exclude_globs", [])
        if custom_excludes:
            ignore_rules.ignore_patterns.extend(custom_excludes)

        # Plan incremental or forced scan
        plan = planner.plan_repository_scan(
            repo_id,
            root,
            ignore_rules=ignore_rules,
            force_full_scan=force_full_scan,
        )

        print(f"   -> Added: {len(plan.added)}")
        print(f"   -> Changed: {len(plan.changed)}")
        print(f"   -> Unchanged (skipped): {len(plan.unchanged)}")
        print(f"   -> Deleted: {len(plan.deleted)}")

        # Process added and modified files
        pipeline = IngestionPipeline(repo_id, brick_repo, root_path=root)
        repo_symbols = 0
        actions_to_process = plan.added + plan.changed

        for i, action in enumerate(actions_to_process, 1):
            try:
                _, report, brick_ids = pipeline.process_file_on_disk(action.relative_path)
                repo_symbols += len(brick_ids)
                if i % 50 == 0 or i == len(actions_to_process):
                    print(f"   ... processed {i}/{len(actions_to_process)} files ({repo_symbols} bricks indexed)")
            except Exception as ex:
                print(f"   [ERR] Failed indexing {action.relative_path}: {ex}")

        # Reconcile deletions
        if plan.deleted:
            del_count = planner.reconcile_deleted_files(repo_id, plan)
            print(f"   -> Reconciled {del_count} deleted file(s) from catalog")

        planner.finalize_scan_run(
            plan.scan_run_id,
            status="completed",
            symbols_indexed=repo_symbols,
        )

        print(f"   [SUCCESS] Indexed {repo_symbols} code symbols for '{repo['name']}'.\n")
        total_scanned_repos += 1
        total_indexed_symbols += repo_symbols

    print(f"[BrickForge] Finished sync & scan. Repositories scanned: {total_scanned_repos}. Total symbols indexed: {total_indexed_symbols}.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync repositories from JSON configuration into BrickForge catalog.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to repositories.json (defaults to config/repositories.json)",
    )
    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        default=None,
        help="Specific repository ID to scan (e.g. dev-c)",
    )
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="Only register/sync repositories without triggering a scan",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force a full re-scan of files even if unchanged",
    )

    args = parser.parse_args()

    try:
        sync_config(
            config_path=args.config,
            scan_after_sync=not args.no_scan,
            target_repo_id=args.repo,
            force_full_scan=args.force,
        )
        return 0
    except Exception as e:
        print(f"[ERROR] Sync failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())