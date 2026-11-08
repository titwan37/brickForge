"""Launch the BrickForge Web Catalog Explorer interface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import threading
import webbrowser

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import uvicorn

from brickforge.web.app import create_app

console = Console()


def get_db_stats(db_path: Path) -> tuple[int, int]:
    """Retrieve quick brick and repository count if database exists."""
    if not db_path.exists():
        return 0, 0
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        total_bricks = cursor.execute("SELECT COUNT(*) FROM code_bricks;").fetchone()[0]
        total_repos = cursor.execute("SELECT COUNT(*) FROM repositories;").fetchone()[0]
        conn.close()
        return total_bricks, total_repos
    except Exception:
        return 0, 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch the BrickForge Web Catalog Explorer interface.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind server to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to serve on.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/brickforge.db",
        help="Path to the SQLite catalog database.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically launch web browser on startup.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for frontend/backend development.",
    )

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    db_path = (project_root / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)

    total_bricks, total_repos = get_db_stats(db_path)

    url = f"http://{args.host}:{args.port}"
    docs_url = f"{url}/docs"

    banner_text = Text()
    banner_text.append("🧱 BrickForge Catalog Web Explorer\n", style="bold cyan")
    banner_text.append(f"• Catalog URL:     {url}\n", style="bold green")
    banner_text.append(f"• OpenAPI Docs:    {docs_url}\n", style="dim")
    banner_text.append(f"• Database:        {db_path}\n", style="dim")
    banner_text.append(f"• Indexed Bricks:  {total_bricks:,} bricks across {total_repos} repositories\n", style="bold yellow")
    banner_text.append("Press Ctrl+C to stop the web server.", style="italic slate")

    console.print()
    console.print(Panel(banner_text, border_style="cyan", title="[bold white]BrickForge Sovereign UI[/bold white]"))
    console.print()

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app = create_app(db_path=db_path)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())

