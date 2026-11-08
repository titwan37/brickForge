"""BrickForge Command Line Interface."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the brickforge CLI."""
    parser = argparse.ArgumentParser(
        prog="brickforge",
        description="BrickForge: Sovereign AST Code Intelligence & Composable Component Registry",
    )
    parser.add_argument("--version", action="version", version="brickforge 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize the local SQLite catalog")
    init_parser.add_argument("--db", type=str, default=None, help="Database path")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan and index registered repositories")
    scan_parser.add_argument("paths", nargs="*", help="Paths to scan")
    scan_parser.add_argument("--languages", type=str, default=None, help="Comma-separated language list")

    # search
    search_parser = subparsers.add_parser("search", help="Search code bricks")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--lang", type=str, default=None, help="Language filter")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Launch the web catalog explorer")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
    serve_parser.add_argument("--db", type=str, default=None, help="Path to database")
    serve_parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "serve":
        import threading
        import webbrowser
        import uvicorn
        from brickforge.web.app import create_app

        url = f"http://{args.host}:{args.port}"
        print(f"Starting BrickForge Web Catalog Explorer at {url}...")
        if not args.no_browser:
            threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        app = create_app(db_path=args.db)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

