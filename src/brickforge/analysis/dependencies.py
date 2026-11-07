"""Static dependency, call, and inheritance relationship extraction for Python ASTs."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Union

from brickforge.analysis.imports import ImportStatement
from brickforge.analysis.symbol_index import RepositorySymbolIndex, SymbolLocation
from brickforge.parsers.base import ExtractedSymbol

VALID_DEPENDENCY_TYPES = {
    "calls",
    "uses_type",
    "inherits",
    "implements",
    "imports",
    "decorates",
    "references",
}


@dataclass(frozen=True)
class ExtractedDependency:
    """A statically extracted dependency relationship from a code symbol."""

    dependency_type: str
    target_symbol: str
    confidence: float
    line_number: int
    resolution_status: str = "unresolved"  # 'resolved', 'unresolved', 'external'
    target_brick_id: Optional[str] = None
    callee_expr: Optional[str] = None

    def __post_init__(self) -> None:
        if self.dependency_type not in VALID_DEPENDENCY_TYPES:
            raise ValueError(
                f"Invalid dependency_type '{self.dependency_type}'. Must be one of {VALID_DEPENDENCY_TYPES}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be between 0.0 and 1.0")
        if self.resolution_status not in ("resolved", "unresolved", "external"):
            raise ValueError(f"Invalid resolution_status '{self.resolution_status}'")


class _AstDependencyVisitor(ast.NodeVisitor):
    """AST visitor traversing nodes within a function or class to extract relationships."""

    def __init__(self) -> None:
        self.dependencies: List[ExtractedDependency] = []

    def _get_name(self, node: ast.AST) -> Optional[str]:
        """Convert an AST expression (Name or Attribute) into a dotted string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # 1. Base classes (inheritance)
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name:
                self.dependencies.append(
                    ExtractedDependency(
                        dependency_type="inherits",
                        target_symbol=base_name,
                        confidence=1.0,
                        line_number=base.lineno,
                    )
                )

        # 2. Class decorators
        for dec in node.decorator_list:
            dec_target = self._get_name(dec.func if isinstance(dec, ast.Call) else dec)
            if dec_target:
                self.dependencies.append(
                    ExtractedDependency(
                        dependency_type="decorates",
                        target_symbol=dec_target,
                        confidence=1.0,
                        line_number=dec.lineno,
                    )
                )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        # 1. Decorators
        for dec in node.decorator_list:
            dec_target = self._get_name(dec.func if isinstance(dec, ast.Call) else dec)
            if dec_target:
                self.dependencies.append(
                    ExtractedDependency(
                        dependency_type="decorates",
                        target_symbol=dec_target,
                        confidence=1.0,
                        line_number=dec.lineno,
                    )
                )

        # 2. Type annotations in arguments
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                type_name = self._get_name(arg.annotation)
                if type_name:
                    self.dependencies.append(
                        ExtractedDependency(
                            dependency_type="uses_type",
                            target_symbol=type_name,
                            confidence=1.0,
                            line_number=arg.annotation.lineno,
                        )
                    )

        # 3. Return type annotation
        if node.returns:
            ret_type = self._get_name(node.returns)
            if ret_type:
                self.dependencies.append(
                    ExtractedDependency(
                        dependency_type="uses_type",
                        target_symbol=ret_type,
                        confidence=1.0,
                        line_number=node.returns.lineno,
                    )
                )

        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._get_name(node.func)
        if call_name:
            if "." in call_name:
                # E.g. self.method() -> confidence 0.85; obj.method() -> confidence 0.60
                if call_name.startswith("self.") or call_name.startswith("cls."):
                    confidence = 0.85
                else:
                    confidence = 0.60
            else:
                # Direct statically visible function/constructor call
                confidence = 0.95

            self.dependencies.append(
                ExtractedDependency(
                    dependency_type="calls",
                    target_symbol=call_name,
                    confidence=confidence,
                    line_number=node.lineno,
                    callee_expr=call_name,
                )
            )

        self.generic_visit(node)


class PythonDependencyExtractor:
    """Statically extracts dependency edges from Python code structures."""

    def extract_from_source(self, source_code: str) -> List[ExtractedDependency]:
        """Extract all static dependencies from Python source code string."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []

        visitor = _AstDependencyVisitor()
        visitor.visit(tree)
        return visitor.dependencies

    def extract_from_symbol(self, symbol: ExtractedSymbol) -> List[ExtractedDependency]:
        """Extract static dependencies from an ExtractedSymbol's source code."""
        return self.extract_from_source(symbol.source_code)

    def resolve_dependencies(
        self,
        dependencies: Sequence[ExtractedDependency],
        imports: Sequence[ImportStatement],
        symbol_index: Optional[RepositorySymbolIndex] = None,
        current_file_path: str = "",
    ) -> List[ExtractedDependency]:
        """Classify and resolve dependencies using known imports and repository index."""
        # Map imported symbol names and aliases to their source module/kind
        symbol_to_import: Dict[str, ImportStatement] = {}
        for imp in imports:
            for s in imp.imported_symbols:
                symbol_to_import[s] = imp
            for alias, original in imp.alias_mapping.items():
                symbol_to_import[alias] = imp

        resolved_deps: List[ExtractedDependency] = []

        for dep in dependencies:
            target = dep.target_symbol
            base_sym = target.split(".")[0]

            # 1. Check if base symbol comes from an import
            if base_sym in symbol_to_import:
                imp = symbol_to_import[base_sym]
                if imp.kind in ("stdlib", "third_party"):
                    resolved_deps.append(
                        ExtractedDependency(
                            dependency_type=dep.dependency_type,
                            target_symbol=dep.target_symbol,
                            confidence=dep.confidence,
                            line_number=dep.line_number,
                            resolution_status="external",
                            callee_expr=dep.callee_expr,
                        )
                    )
                    continue

                # Local import: attempt resolution via symbol_index
                if symbol_index and current_file_path:
                    resolved_targets = symbol_index.resolve_import_targets(current_file_path, imp)
                    matched_loc = resolved_targets.get(base_sym)
                    if matched_loc:
                        resolved_deps.append(
                            ExtractedDependency(
                                dependency_type=dep.dependency_type,
                                target_symbol=f"{matched_loc.qualified_name}{target[len(base_sym):]}",
                                confidence=dep.confidence,
                                line_number=dep.line_number,
                                resolution_status="resolved",
                                target_brick_id=f"{matched_loc.relative_path}:{matched_loc.qualified_name}",
                                callee_expr=dep.callee_expr,
                            )
                        )
                        continue

            # 2. Check if it refers to a self/cls method or local symbol
            if target.startswith("self.") or target.startswith("cls."):
                method_name = target.split(".", 1)[1]
                resolved_deps.append(
                    ExtractedDependency(
                        dependency_type=dep.dependency_type,
                        target_symbol=method_name,
                        confidence=dep.confidence,
                        line_number=dep.line_number,
                        resolution_status="unresolved",  # intra-class reference
                        callee_expr=dep.callee_expr,
                    )
                )
                continue

            # Default: unresolved static reference
            resolved_deps.append(dep)

        return resolved_deps

