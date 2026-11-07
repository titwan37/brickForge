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

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

