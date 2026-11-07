"""Dependency-aware source code bundling and extraction for code bricks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from brickforge.analysis.graph import DependencyGraphTraverser, TraversalResult
from brickforge.storage.database import DatabaseManager


@dataclass
class ExtractionBundle:
    """A self-contained source code bundle extracted for a target brick."""

    target_brick_id: str
    target_symbol_name: str
    bundled_source: str
    import_headers: List[str] = field(default_factory=list)
    included_brick_ids: List[str] = field(default_factory=list)
    external_packages: List[str] = field(default_factory=list)
    unresolved_dependencies: List[str] = field(default_factory=list)
    omitted_dependencies: List[str] = field(default_factory=list)


class SourceBundler:
    """Assembles a target brick and its internal dependency helpers into a coherent source bundle."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.db = db
        self.traverser = DependencyGraphTraverser(db)

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    def bundle_brick(
        self,
        brick_row_id: int,
        max_depth: int = 3,
        include_helpers: bool = True,
    ) -> ExtractionBundle:
        """Extract target brick and internal helpers, synthesizing imports and reporting gaps."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Fetch target brick
            cursor.execute("SELECT * FROM code_bricks WHERE row_id = ?;", (brick_row_id,))
            target_row = cursor.fetchone()
            if not target_row:
                raise ValueError(f"Brick with row_id {brick_row_id} not found.")

            target_brick_id = target_row["id"]
            target_symbol = target_row["symbol_name"]

            # 2. Traverse dependencies
            included_rows: List[sqlite3.Row] = [target_row]
            included_ids: Set[int] = {brick_row_id}
            unresolved: List[str] = []
            omitted: List[str] = []

            if include_helpers:
                trav_res: TraversalResult = self.traverser.traverse(
                    start_row_id=brick_row_id,
                    direction="outgoing",
                    max_depth=max_depth,
                )

                for node_id, node in trav_res.nodes.items():
                    if node.brick_row_id and node.brick_row_id != brick_row_id:
                        cursor.execute("SELECT * FROM code_bricks WHERE row_id = ?;", (node.brick_row_id,))
                        helper_row = cursor.fetchone()
                        if helper_row and node.brick_row_id not in included_ids:
                            included_rows.append(helper_row)
                            included_ids.add(node.brick_row_id)
                    elif node.is_unresolved:
                        unresolved.append(node.qualified_name)

                if trav_res.budget_exceeded:
                    omitted.append("Traversal exceeded node/edge budget; some transitive helpers omitted.")

            # 3. Collect external package imports
            placeholders = ",".join("?" * len(included_ids))
            cursor.execute(
                f"""
                SELECT DISTINCT package_name, import_statement
                FROM external_packages
                WHERE brick_row_id IN ({placeholders});
                """,
                list(included_ids),
            )
            pkg_rows = cursor.fetchall()
            import_headers: List[str] = []
            external_pkgs: List[str] = []

            for prow in pkg_rows:
                external_pkgs.append(prow["package_name"])
                stmt = prow["import_statement"].strip()
                if stmt and stmt not in import_headers:
                    import_headers.append(stmt)

            # 4. Order bricks: helpers first, then target brick
            # (Helpers appear before the target brick that uses them)
            helpers = [r for r in included_rows if r["row_id"] != brick_row_id]
            # Sort helpers by start_line or row_id
            helpers.sort(key=lambda r: (r["start_line"], r["row_id"]))

            source_blocks: List[str] = []
            if import_headers:
                source_blocks.append("\n".join(sorted(import_headers)))

            for h in helpers:
                source_blocks.append(h["source_code"].strip())

            source_blocks.append(target_row["source_code"].strip())

            bundled_code = "\n\n\n".join(source_blocks) + "\n"

            return ExtractionBundle(
                target_brick_id=target_brick_id,
                target_symbol_name=target_symbol,
                bundled_source=bundled_code,
                import_headers=import_headers,
                included_brick_ids=[r["id"] for r in included_rows],
                external_packages=list(set(external_pkgs)),
                unresolved_dependencies=unresolved,
                omitted_dependencies=omitted,
            )
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

