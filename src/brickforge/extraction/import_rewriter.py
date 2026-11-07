"""Optional repository import normalization and rewriting for extracted code bundles."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class ImportRewriteRecord:
    """Record of an individual import rewrite performed during extraction."""

    line_number: int
    original_statement: str
    rewritten_statement: Optional[str]
    reason: str


@dataclass
class RewriteResult:
    """Result of an import rewrite operation."""

    rewritten_code: str
    rewrites: List[ImportRewriteRecord] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return len(self.rewrites) > 0


class ImportRewriter:
    """Rewrites imports in extracted Python code to adapt to new target environments."""

    def __init__(
        self,
        prefix_mappings: Optional[Dict[str, str]] = None,
        bundled_symbols: Optional[Set[str]] = None,
        flatten_relative: bool = False,
    ):
        # E.g. {"old_repo.services": "app.services"}
        self.prefix_mappings = dict(prefix_mappings or {})
        self.bundled_symbols = set(bundled_symbols or ())
        self.flatten_relative = flatten_relative

    def rewrite(self, source_code: str) -> RewriteResult:
        """Process source code, applying prefix remappings, local pruning, and relative flattening."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # If not valid syntax, return original unchanged
            return RewriteResult(rewritten_code=source_code, rewrites=[])

        lines = source_code.splitlines()
        rewrites: List[ImportRewriteRecord] = []
        lines_to_modify: Dict[int, Optional[str]] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    orig_name = alias.name
                    for old_pfx, new_pfx in self.prefix_mappings.items():
                        if orig_name == old_pfx or orig_name.startswith(f"{old_pfx}."):
                            new_name = orig_name.replace(old_pfx, new_pfx, 1)
                            as_clause = f" as {alias.asname}" if alias.asname else ""
                            orig_stmt = lines[node.lineno - 1]
                            new_stmt = f"import {new_name}{as_clause}"
                            lines_to_modify[node.lineno - 1] = new_stmt
                            rewrites.append(
                                ImportRewriteRecord(
                                    line_number=node.lineno,
                                    original_statement=orig_stmt.strip(),
                                    rewritten_statement=new_stmt,
                                    reason=f"prefix_remapped: {old_pfx} -> {new_pfx}",
                                )
                            )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                orig_stmt = lines[node.lineno - 1]

                # 1. Check if symbols are bundled locally in the same file
                remaining_symbols = [
                    name for name in node.names if name.name not in self.bundled_symbols
                ]
                if not remaining_symbols:
                    # All imported symbols from this statement are already bundled locally
                    lines_to_modify[node.lineno - 1] = None  # delete line
                    rewrites.append(
                        ImportRewriteRecord(
                            line_number=node.lineno,
                            original_statement=orig_stmt.strip(),
                            rewritten_statement=None,
                            reason="symbols_bundled_locally",
                        )
                    )
                    continue
                elif len(remaining_symbols) < len(node.names):
                    # Some symbols were pruned
                    sym_strs = [
                        f"{a.name} as {a.asname}" if a.asname else a.name
                        for a in remaining_symbols
                    ]
                    dots = "." * (node.level or 0)
                    new_stmt = f"from {dots}{module} import {', '.join(sym_strs)}"
                    lines_to_modify[node.lineno - 1] = new_stmt
                    rewrites.append(
                        ImportRewriteRecord(
                            line_number=node.lineno,
                            original_statement=orig_stmt.strip(),
                            rewritten_statement=new_stmt,
                            reason="pruned_bundled_symbols",
                        )
                    )

                # 2. Check prefix remapping
                for old_pfx, new_pfx in self.prefix_mappings.items():
                    if module == old_pfx or module.startswith(f"{old_pfx}."):
                        new_mod = module.replace(old_pfx, new_pfx, 1)
                        sym_strs = [
                            f"{a.name} as {a.asname}" if a.asname else a.name
                            for a in node.names
                        ]
                        dots = "." * (node.level or 0)
                        new_stmt = f"from {dots}{new_mod} import {', '.join(sym_strs)}"
                        lines_to_modify[node.lineno - 1] = new_stmt
                        rewrites.append(
                            ImportRewriteRecord(
                                line_number=node.lineno,
                                original_statement=orig_stmt.strip(),
                                rewritten_statement=new_stmt,
                                reason=f"prefix_remapped: {old_pfx} -> {new_pfx}",
                            )
                        )

                # 3. Flatten deep relative imports e.g. from ..foo import bar -> from .foo import bar
                if self.flatten_relative and node.level > 1:
                    sym_strs = [
                        f"{a.name} as {a.asname}" if a.asname else a.name
                        for a in node.names
                    ]
                    new_stmt = f"from .{module} import {', '.join(sym_strs)}" if module else f"from . import {', '.join(sym_strs)}"
                    lines_to_modify[node.lineno - 1] = new_stmt
                    rewrites.append(
                        ImportRewriteRecord(
                            line_number=node.lineno,
                            original_statement=orig_stmt.strip(),
                            rewritten_statement=new_stmt,
                            reason="flattened_relative",
                        )
                    )

        if not rewrites:
            return RewriteResult(rewritten_code=source_code, rewrites=[])

        # Rebuild output code lines
        new_lines: List[str] = []
        for idx, line in enumerate(lines):
            if idx in lines_to_modify:
                modified = lines_to_modify[idx]
                if modified is not None:
                    new_lines.append(modified)
            else:
                new_lines.append(line)

        output = "\n".join(new_lines)
        if source_code.endswith("\n") and not output.endswith("\n"):
            output += "\n"

        return RewriteResult(
            rewritten_code=output,
            rewrites=rewrites,
        )
