"""Dependency graph traversal, cycle detection, and bounded budget traversal for code bricks."""

from __future__ import annotations

import sqlite3
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from brickforge.storage.database import DatabaseManager


@dataclass(frozen=True)
class GraphNode:
    """A node in the traversed brick dependency graph."""

    node_id: str
    symbol_name: str
    qualified_name: str
    kind: str
    brick_row_id: Optional[int] = None
    is_external: bool = False
    is_unresolved: bool = False


@dataclass(frozen=True)
class GraphEdge:
    """A directed dependency edge between two graph nodes."""

    source_id: str
    target_id: str
    dependency_type: str
    confidence: float
    resolution_status: str  # 'resolved', 'unresolved', 'external'


@dataclass
class TraversalResult:
    """Complete result of a bounded dependency graph traversal."""

    root_id: str
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    cycles: List[List[str]] = field(default_factory=list)
    budget_exceeded: bool = False

    @property
    def total_nodes(self) -> int:
        return len(self.nodes)

    @property
    def total_edges(self) -> int:
        return len(self.edges)

    @property
    def unresolved_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.is_unresolved)

    @property
    def external_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.is_external)


class DependencyGraphTraverser:
    """Traverses dependency graphs across code bricks with depth and node/edge budget limits."""

    def __init__(self, db: Union[DatabaseManager, sqlite3.Connection]):
        self.db = db

    def _get_connection(self) -> sqlite3.Connection:
        if isinstance(self.db, DatabaseManager):
            return self.db.create_connection()
        return self.db

    def traverse(
        self,
        start_row_id: int,
        direction: str = "outgoing",  # 'outgoing', 'incoming', or 'both'
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> TraversalResult:
        """Traverse the dependency graph starting at `start_row_id` up to `max_depth`."""
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Retrieve starting root brick
            cursor.execute(
                "SELECT row_id, id, symbol_name, qualified_name, kind FROM code_bricks WHERE row_id = ?;",
                (start_row_id,),
            )
            root_row = cursor.fetchone()
            if not root_row:
                raise ValueError(f"Starting brick row_id {start_row_id} does not exist.")

            root_id = str(root_row["row_id"])
            root_node = GraphNode(
                node_id=root_id,
                symbol_name=root_row["symbol_name"],
                qualified_name=root_row["qualified_name"],
                kind=root_row["kind"],
                brick_row_id=root_row["row_id"],
            )

            result = TraversalResult(root_id=root_id)
            result.nodes[root_id] = root_node

            # Queue: (current_row_id, current_depth)
            queue = deque([(start_row_id, 0)])
            visited_edges: Set[Tuple[str, str, str]] = set()

            while queue:
                current_id, depth = queue.popleft()
                if depth >= max_depth:
                    continue

                # Query outgoing edges
                if direction in ("outgoing", "both"):
                    cursor.execute(
                        """
                        SELECT
                            d.dependency_id, d.source_row_id, d.target_row_id,
                            d.unresolved_symbol, d.dependency_type, d.resolution_status,
                            d.confidence,
                            cb.symbol_name, cb.qualified_name, cb.kind
                        FROM brick_dependencies d
                        LEFT JOIN code_bricks cb ON cb.row_id = d.target_row_id
                        WHERE d.source_row_id = ?;
                        """,
                        (current_id,),
                    )
                    for row in cursor.fetchall():
                        if len(result.edges) >= max_edges or len(result.nodes) >= max_nodes:
                            result.budget_exceeded = True
                            break

                        target_row_id = row["target_row_id"]
                        status = row["resolution_status"]

                        if target_row_id is not None:
                            target_id = str(target_row_id)
                            if target_id not in result.nodes:
                                result.nodes[target_id] = GraphNode(
                                    node_id=target_id,
                                    symbol_name=row["symbol_name"] or f"brick_{target_id}",
                                    qualified_name=row["qualified_name"] or f"brick_{target_id}",
                                    kind=row["kind"] or "unknown",
                                    brick_row_id=target_row_id,
                                )
                                queue.append((target_row_id, depth + 1))
                        else:
                            unresolved_sym = row["unresolved_symbol"] or "unknown"
                            target_id = f"sym:{unresolved_sym}"
                            if target_id not in result.nodes:
                                is_ext = status == "external"
                                result.nodes[target_id] = GraphNode(
                                    node_id=target_id,
                                    symbol_name=unresolved_sym.split(".")[-1],
                                    qualified_name=unresolved_sym,
                                    kind="external" if is_ext else "unresolved",
                                    is_external=is_ext,
                                    is_unresolved=not is_ext,
                                )

                        edge_key = (str(current_id), target_id, row["dependency_type"])
                        if edge_key not in visited_edges:
                            visited_edges.add(edge_key)
                            result.edges.append(
                                GraphEdge(
                                    source_id=str(current_id),
                                    target_id=target_id,
                                    dependency_type=row["dependency_type"],
                                    confidence=float(row["confidence"]),
                                    resolution_status=status,
                                )
                            )

                # Query incoming edges
                if direction in ("incoming", "both"):
                    cursor.execute(
                        """
                        SELECT
                            d.dependency_id, d.source_row_id, d.target_row_id,
                            d.dependency_type, d.resolution_status, d.confidence,
                            cb.symbol_name, cb.qualified_name, cb.kind
                        FROM brick_dependencies d
                        JOIN code_bricks cb ON cb.row_id = d.source_row_id
                        WHERE d.target_row_id = ?;
                        """,
                        (current_id,),
                    )
                    for row in cursor.fetchall():
                        if len(result.edges) >= max_edges or len(result.nodes) >= max_nodes:
                            result.budget_exceeded = True
                            break

                        source_row_id = row["source_row_id"]
                        source_id = str(source_row_id)
                        if source_id not in result.nodes:
                            result.nodes[source_id] = GraphNode(
                                node_id=source_id,
                                symbol_name=row["symbol_name"],
                                qualified_name=row["qualified_name"],
                                kind=row["kind"],
                                brick_row_id=source_row_id,
                            )
                            queue.append((source_row_id, depth + 1))

                        edge_key = (source_id, str(current_id), row["dependency_type"])
                        if edge_key not in visited_edges:
                            visited_edges.add(edge_key)
                            result.edges.append(
                                GraphEdge(
                                    source_id=source_id,
                                    target_id=str(current_id),
                                    dependency_type=row["dependency_type"],
                                    confidence=float(row["confidence"]),
                                    resolution_status=row["resolution_status"],
                                )
                            )

            # Cycle detection in traversed graph
            result.cycles = self._find_cycles(result.edges)
            return result
        finally:
            if isinstance(self.db, DatabaseManager):
                conn.close()

    def _find_cycles(self, edges: Sequence[GraphEdge]) -> List[List[str]]:
        """Detect directed cycles in the graph using DFS."""
        adj: Dict[str, List[str]] = {}
        for e in edges:
            adj.setdefault(e.source_id, []).append(e.target_id)

        visited: Set[str] = set()
        on_stack: Set[str] = set()
        path: List[str] = []
        cycles: List[List[str]] = []

        def dfs(node: str) -> None:
            visited.add(node)
            on_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, []):
                if neighbor in on_stack:
                    # Found a cycle!
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited:
                    dfs(neighbor)

            path.pop()
            on_stack.remove(node)

        for n in list(adj.keys()):
            if n not in visited:
                dfs(n)

        return cycles

