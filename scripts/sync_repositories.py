"""Synchronize repository catalog from JSON configuration with Rich console logging and execution log recording.

Usage:
    python scripts/sync_repositories.py
    python scripts/sync_repositories.py --config config/repositories.json
    python scripts/sync_repositories.py --repo dev-c
    python scripts/sync_repositories.py --no-scan
    python scripts/sync_repositories.py --force
    python scripts/sync_repositories.py --log-file logs/custom_run.log
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from brickforge.ingestion.ignore_rules import IgnoreRules
from brickforge.ingestion.pipeline import IngestionPipeline
from brickforge.ingestion.planner import ScanPlanner
from brickforge.storage.brick_repository import BrickRepository
from brickforge.storage.database import DatabaseManager
from brickforge.search.vector_index import BrickForgeVectorIndex

# Enable record=True so the complete formatted text can be exported to execution log files
console = Console(record=True)


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


def resolve_log_path(explicit_log_path: Optional[str] = None) -> Path:
    """Compute default execution log path (logs/YYYY-MM-DD_exe.log) or resolve explicit path."""
    project_root = Path(__file__).parent.parent
    if explicit_log_path:
        log_path = Path(explicit_log_path)
        if not log_path.is_absolute():
            log_path = (project_root / log_path).resolve()
        return log_path

    today_str = datetime.now().strftime("%Y-%m-%d")
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"{today_str}_exe.log"


def save_execution_log(log_path: Path, console_instance: Console) -> None:
    """Export the plain-text console session to an execution log file."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        session_text = console_instance.export_text()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = f"\n{'=' * 80}\n[BrickForge Execution Log: {timestamp}]\n{'=' * 80}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(header)
            f.write(session_text)
            f.write("\n")
    except Exception as ex:
        print(f"[BrickForge] Warning: Failed to write execution log to {log_path}: {ex}", file=sys.stderr)


def print_banner(db_path: Path, config_file: Path, log_path: Path) -> None:
    """Render startup banner."""
    content = Text()
    content.append("🧱 BrickForge ", style="bold cyan")
    content.append("Sovereign AST Code Intelligence & Catalog Sync\n", style="bold white")
    content.append("Config: ", style="dim")
    content.append(str(config_file), style="yellow")
    content.append("\nDatabase: ", style="dim")
    content.append(str(db_path), style="green")
    content.append("\nExecution Log: ", style="dim")
    content.append(str(log_path), style="magenta")

    console.print(Panel(content, box=box.ROUNDED, border_style="cyan", padding=(0, 2)))


def render_repository_table(repos: List[Dict[str, Any]]) -> None:
    """Render table of configured repositories."""
    table = Table(
        title="[bold white]Registered Source Repositories[/bold white]",
        box=box.SIMPLE_HEAVY,
        header_style="bold magenta",
        title_justify="left",
    )
    table.add_column("Repo ID", style="bold cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Root Path", style="dim")
    table.add_column("Configured", justify="center")
    table.add_column("Disk Accessible", justify="center")

    for r in repos:
        path = Path(r["root_path"])
        is_accessible = path.exists()
        is_enabled = r.get("enabled", True)

        status_text = "[bold green]ENABLED[/bold green]" if is_enabled else "[dim yellow]DISABLED[/dim yellow]"
        access_text = (
            "[bold green]✔ ONLINE[/bold green]"
            if is_accessible
            else "[bold red]✖ OFFLINE / UNREACHABLE[/bold red]"
        )

        table.add_row(
            r["id"],
            r["name"],
            str(r["root_path"]),
            status_text,
            access_text,
        )

    console.print(table)
    console.print()


def sync_config(
    config_path: Optional[str] = None,
    scan_after_sync: bool = True,
    target_repo_id: Optional[str] = None,
    force_full_scan: bool = False,
    log_file_path: Optional[str] = None,
    sync_vectors: bool = True,
) -> None:
    config_file = find_config_file(config_path)
    log_path = resolve_log_path(log_file_path)

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    db_rel_or_abs = data.get("catalog_db", "data/brickforge.db")
    db_path = Path(db_rel_or_abs)
    if not db_path.is_absolute():
        project_root = (
            config_file.parent.parent
            if config_file.parent.name == "config"
            else config_file.parent
        )
        db_path = (project_root / db_path).resolve()

    print_banner(db_path, config_file, log_path)

    db_mgr = DatabaseManager(db_path=db_path)
    db_mgr.apply_migrations()

    brick_repo = BrickRepository(db_mgr)
    planner = ScanPlanner(db_mgr)

    repos: List[dict] = data.get("repositories", [])
    if not repos:
        console.print("[bold red]Warning: No repositories defined in configuration.[/bold red]")
        return

    # 1. Register or update repositories in SQLite
    with db_mgr.connection() as conn:
        for repo in repos:
            # Check if root_path is already registered under an older/renamed ID (e.g. dev-c -> c-dev)
            existing = conn.execute(
                "SELECT id FROM repositories WHERE root_path = ?;",
                (repo["root_path"],),
            ).fetchone()

            if existing and existing[0] != repo["id"]:
                old_id = existing[0]
                new_id = repo["id"]
                console.print(
                    f"[bold cyan]Migrating renamed repository ID:[/bold cyan] "
                    f"[yellow]{old_id}[/yellow] ➔ [green]{new_id}[/green]"
                )
                conn.execute("PRAGMA foreign_keys = OFF;")
                conn.execute("UPDATE source_files SET repository_id = ? WHERE repository_id = ?;", (new_id, old_id))
                conn.execute("UPDATE scan_runs SET repository_id = ? WHERE repository_id = ?;", (new_id, old_id))
                conn.execute("UPDATE repositories SET id = ? WHERE id = ?;", (new_id, old_id))
                conn.execute("PRAGMA foreign_keys = ON;")

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

    render_repository_table(repos)

    if not scan_after_sync:
        console.print("[bold green]✔ Catalog schema and repositories synced successfully.[/bold green] Scan skipped (--no-scan).\n")
        return

    # Summary tracking
    summary_results: List[Dict[str, Any]] = []

    for repo in repos:
        repo_id = repo["id"]
        repo_name = repo["name"]

        if target_repo_id and repo_id != target_repo_id:
            continue

        if not repo.get("enabled", True):
            summary_results.append({
                "id": repo_id,
                "name": repo_name,
                "status": "[dim yellow]SKIPPED (Disabled)[/dim yellow]",
                "added": 0,
                "changed": 0,
                "unchanged": 0,
                "symbols": 0,
                "duration": 0.0,
            })
            continue

        root = Path(repo["root_path"])
        if not root.exists():
            console.print(f"[bold red]✖ Skipping '{repo_name}' [{repo_id}]: Root path '{root}' is inaccessible.[/bold red]\n")
            summary_results.append({
                "id": repo_id,
                "name": repo_name,
                "status": "[bold red]OFFLINE / ERROR[/bold red]",
                "added": 0,
                "changed": 0,
                "unchanged": 0,
                "symbols": 0,
                "duration": 0.0,
            })
            continue

        console.print(Panel(
            f"[bold cyan]Scanning Repository:[/bold cyan] [bold white]{repo_name}[/bold white] [dim]({repo_id})[/dim]\n"
            f"[dim]Root:[/dim] [white]{root}[/white]",
            border_style="blue",
            box=box.ROUNDED,
        ))

        # Build repository ignore rules
        ignore_rules = IgnoreRules()
        custom_excludes = repo.get("exclude_globs", [])
        if custom_excludes:
            ignore_rules.ignore_patterns.extend(custom_excludes)

        t_repo_start = time.perf_counter()

        # Phase A: Discovery with live spinner
        discovered_files = 0
        with Progress(
            SpinnerColumn("dots", style="bold cyan"),
            TextColumn("[bold cyan]Scanning filesystem & planning delta...[/bold cyan]"),
            TextColumn("[dim]({task.fields[count]} files evaluated)[/dim]"),
            console=console,
            transient=True,
        ) as discovery_progress:
            task_d = discovery_progress.add_task("discovery", count=0)

            def on_file(count: int, rel: str):
                discovery_progress.update(task_d, count=count)

            plan = planner.plan_repository_scan(
                repo_id,
                root,
                ignore_rules=ignore_rules,
                force_full_scan=force_full_scan,
                progress_callback=on_file,
            )

        # Plan Summary Box
        delta_table = Table(box=box.MINIMAL, show_header=False)
        delta_table.add_column("Type", style="bold")
        delta_table.add_column("Count", justify="right")

        delta_table.add_row("[bold green]✚ Added (new):[/bold green]", f"[bold green]{len(plan.added)}[/bold green]")
        delta_table.add_row("[bold yellow]↺ Changed (modified):[/bold yellow]", f"[bold yellow]{len(plan.changed)}[/bold yellow]")
        delta_table.add_row("[dim blue]― Unchanged (skipped):[/dim blue]", f"[dim blue]{len(plan.unchanged)}[/dim blue]")
        delta_table.add_row("[bold red]✖ Deleted (removed):[/bold red]", f"[bold red]{len(plan.deleted)}[/bold red]")
        console.print(delta_table)

        # Phase B: File Ingestion & AST Extraction with Rich Progress Bar
        actions_to_process = plan.added + plan.changed
        pipeline = IngestionPipeline(repo_id, brick_repo, root_path=root)
        repo_symbols = 0

        if actions_to_process:
            console.print()
            with Progress(
                TextColumn("[bold magenta]{task.description}[/bold magenta]"),
                BarColumn(bar_width=40, style="cyan", complete_style="bold green"),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("[dim]{task.fields[current_file]}[/dim]"),
                console=console,
            ) as ingest_progress:
                ingest_task = ingest_progress.add_task(
                    "Parsing AST & Indexing",
                    total=len(actions_to_process),
                    current_file="",
                )

                for action in actions_to_process:
                    short_path = action.relative_path
                    if len(short_path) > 35:
                        short_path = "..." + short_path[-32:]

                    ingest_progress.update(ingest_task, current_file=short_path)

                    try:
                        _, report, brick_ids = pipeline.process_file_on_disk(action.relative_path)
                        repo_symbols += len(brick_ids)
                    except Exception as ex:
                        console.print(f"   [bold red]✖ Error indexing {action.relative_path}:[/bold red] {ex}")

                    ingest_progress.advance(ingest_task)

            console.print(f"   [bold green]✔ Extraction complete:[/bold green] Indexed [bold cyan]{repo_symbols}[/bold cyan] code symbols/bricks.")
            if repo_symbols == 0:
                console.print("   [dim]ℹ 0 code bricks extracted (Note: BrickForge MVP AST extractor currently indexes Python .py/.pyi files).[/dim]")
        else:
            console.print("   [dim green]✔ No file modifications detected (cache is up-to-date).[/dim green]")

        # Phase C: Reconcile Deletions
        if plan.deleted:
            del_count = planner.reconcile_deleted_files(repo_id, plan)
            console.print(f"   [bold yellow]↺ Reconciled {del_count} deleted file(s) from catalog.[/bold yellow]")

        planner.finalize_scan_run(
            plan.scan_run_id,
            status="completed",
            symbols_indexed=repo_symbols,
        )

        t_repo_end = time.perf_counter()
        duration = t_repo_end - t_repo_start

        console.print(f"   [dim]Scan finished in {duration:.2f}s[/dim]\n")

        summary_results.append({
            "id": repo_id,
            "name": repo_name,
            "status": "[bold green]COMPLETED[/bold green]",
            "added": len(plan.added),
            "changed": len(plan.changed),
            "unchanged": len(plan.unchanged),
            "symbols": repo_symbols,
            "duration": duration,
        })

    # Render Final Ingestion Summary Table
    console.print()
    summary_table = Table(
        title="[bold white]🏁 Ingestion Run Summary[/bold white]",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_justify="left",
    )
    summary_table.add_column("Repository", style="bold white")
    summary_table.add_column("Status", justify="center")
    summary_table.add_column("New Files", justify="right", style="green")
    summary_table.add_column("Modified", justify="right", style="yellow")
    summary_table.add_column("Unchanged", justify="right", style="dim")
    summary_table.add_column("Bricks Indexed", justify="right", style="bold cyan")
    summary_table.add_column("Duration", justify="right", style="dim white")

    total_added = sum(s["added"] for s in summary_results)
    total_changed = sum(s["changed"] for s in summary_results)
    total_symbols = sum(s["symbols"] for s in summary_results)
    total_time = sum(s["duration"] for s in summary_results)

    for s in summary_results:
        summary_table.add_row(
            f"{s['name']} [dim]({s['id']})[/dim]",
            s["status"],
            str(s["added"]),
            str(s["changed"]),
            str(s["unchanged"]),
            str(s["symbols"]),
            f"{s['duration']:.2f}s",
        )

    summary_table.add_section()
    summary_table.add_row(
        "[bold white]Total[/bold white]",
        "[bold green]OK[/bold green]",
        f"[bold green]{total_added}[/bold green]",
        f"[bold yellow]{total_changed}[/bold yellow]",
        "-",
        f"[bold cyan]{total_symbols}[/bold cyan]",
        f"[bold white]{total_time:.2f}s[/bold white]",
    )

    console.print(summary_table)
    console.print(f"[bold green]Catalog is ready for search & agent queries![/bold green] (Database: [dim]{db_path}[/dim])")
    console.print(f"[bold cyan]📄 Execution log saved to:[/bold cyan] [dim]{log_path}[/dim]\n")

    # Phase F: Auto-update FAISS dense vector index for newly indexed symbols if requested
    if sync_vectors and total_symbols > 0:
        console.print("[bold cyan]🔄 Running Phase F Vector Synchronization (Incremental FAISS Update)...[/bold cyan]")
        try:
            vec_index = BrickForgeVectorIndex()
            with db_mgr.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        b.id AS brick_id,
                        b.symbol_name,
                        b.kind,
                        b.language,
                        b.signature,
                        b.docstring,
                        s.relative_path,
                        r.name AS repository_name,
                        b.portability_score
                    FROM code_bricks b
                    JOIN source_files s ON b.file_id = s.row_id
                    JOIN repositories r ON s.repository_id = r.id
                    WHERE b.signature IS NOT NULL AND LENGTH(b.signature) > 5
                    ORDER BY b.row_id DESC
                    LIMIT 200;
                """)
                recent_bricks = cursor.fetchall()

            indexed_ids = set(b.get("brick_id") for b in vec_index.id_to_brick)
            appended_count = 0
            for r in recent_bricks:
                bid = r[0]
                if bid not in indexed_ids:
                    text_blob = f"{r[1]} ({r[2]} - {r[3]})\nPath: {r[6]}\nSignature: {r[4]}\nDoc: {r[5] or ''}"
                    if vec_index.append_document(doc_id=bid, text=text_blob, metadata={
                        "symbol_name": r[1],
                        "kind": r[2],
                        "language": r[3],
                        "signature": r[4],
                        "relative_path": r[6],
                        "repository_name": r[7],
                        "portability_score": r[8],
                    }, save_after=False):
                        appended_count += 1
                        indexed_ids.add(bid)

            if appended_count > 0:
                vec_index.save()
                console.print(f"   [bold green]✔ Vector sync complete:[/bold green] Appended [bold cyan]{appended_count}[/bold cyan] new vector embeddings to FAISS.\n")
            else:
                console.print("   [dim green]✔ FAISS vector index is up to date.[/dim green]\n")
        except Exception as ve:
            console.print(f"   [dim yellow]⚠ Vector sync skipped/deferred: {ve}[/dim yellow]\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync repositories from JSON configuration into BrickForge catalog with Rich console logging and execution log recording.",
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
    parser.add_argument(
        "--no-vectors",
        action="store_true",
        help="Skip automatic incremental vector updates to FAISS",
    )
    parser.add_argument(
        "--log-file",
        "-l",
        type=str,
        default=None,
        help="Custom destination path for execution log file (defaults to logs/YYYY-MM-DD_exe.log)",
    )

    args = parser.parse_args()
    log_path = resolve_log_path(args.log_file)

    try:
        sync_config(
            config_path=args.config,
            scan_after_sync=not args.no_scan,
            target_repo_id=args.repo,
            force_full_scan=args.force,
            log_file_path=args.log_file,
            sync_vectors=not args.no_vectors,
        )
        return 0
    except KeyboardInterrupt:
        console.print("\n[bold red]✖ Ingestion cancelled by user (Ctrl+C).[/bold red]")
        return 130
    except Exception as e:
        console.print(f"\n[bold red]✖ Sync failed:[/bold red] {e}")
        return 1
    finally:
        save_execution_log(log_path, console)


if __name__ == "__main__":
    sys.exit(main())
