"""Dedicated extractor for Python functions, methods, and classes.

Extracts symbols with exact source spans, signatures, docstrings, decorators,
and deterministic hashes, supporting both top-level and nested declarations.
"""

from __future__ import annotations

import ast
import hashlib
from typing import List, Optional, Sequence, Union

from brickforge.parsers.base import ExtractedSymbol


class PythonSymbolExtractor:
    """Extracts function, method, and class symbols from Python source code."""

    def __init__(self, source_code: Union[str, bytes]) -> None:
        if isinstance(source_code, bytes):
            try:
                self.source_code = source_code.decode("utf-8")
            except UnicodeDecodeError:
                self.source_code = source_code.decode("latin-1", errors="replace")
        else:
            self.source_code = source_code

        self.lines: Sequence[str] = self.source_code.splitlines(keepends=True)
        self.code_bytes: bytes = self.source_code.encode("utf-8")
        self._tree: Optional[ast.AST] = None
        self._parse()

    def _parse(self) -> None:
        try:
            self._tree = ast.parse(self.source_code)
        except SyntaxError:
            self._tree = None

    def extract_all(self) -> List[ExtractedSymbol]:
        """Extract all functions, classes, and methods."""
        if not self._tree:
            return []
        symbols: List[ExtractedSymbol] = []
        self._extract_from_body(self._tree.body, symbols, parent_name=None)
        return symbols

    def extract_functions_only(self) -> List[ExtractedSymbol]:
        """Extract only functions and methods (excluding class declarations)."""
        return [s for s in self.extract_all() if s.kind in ("function", "method")]

    def extract_classes_only(self) -> List[ExtractedSymbol]:
        """Extract only class declarations."""
        return [s for s in self.extract_all() if s.kind == "class"]

    def _extract_from_body(
        self,
        body: Sequence[ast.AST],
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = self._build_function_symbol(node, parent_name)
                symbols.append(sym)
                # Recurse for nested functions or inner classes
                self._extract_from_body(node.body, symbols, parent_name=sym.qualified_name)

            elif isinstance(node, ast.ClassDef):
                sym = self._build_class_symbol(node, parent_name)
                symbols.append(sym)
                # Recurse for class methods and nested classes
                self._extract_from_body(node.body, symbols, parent_name=sym.qualified_name)

    def _build_function_symbol(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        parent_name: Optional[str] = None,
    ) -> ExtractedSymbol:
        is_method = parent_name is not None
        kind = "method" if is_method else "function"
        name = node.name
        qualified_name = f"{parent_name}.{name}" if parent_name else name

        docstring = ast.get_docstring(node)
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        source_slice = self._slice_lines(start_line, end_line)
        start_byte, end_byte = self._calc_byte_offsets(start_line, end_line, getattr(node, "col_offset", 0))

        signature = self._format_function_signature(node)
        sig_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        src_hash = hashlib.sha256(source_slice.encode("utf-8")).hexdigest()

        decorators = [self._format_expr(d) for d in getattr(node, "decorator_list", [])]

        return ExtractedSymbol(
            symbol_name=name,
            qualified_name=qualified_name,
            kind=kind,
            language="python",
            signature=signature,
            signature_hash=sig_hash,
            docstring=docstring,
            source_code=source_slice,
            source_hash=src_hash,
            start_byte=start_byte,
            end_byte=end_byte,
            start_line=start_line,
            end_line=end_line,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            visibility="private" if name.startswith("_") and not name.startswith("__") else "public",
            parent_name=parent_name,
            decorators=decorators,
        )

    def _build_class_symbol(
        self,
        node: ast.ClassDef,
        parent_name: Optional[str] = None,
    ) -> ExtractedSymbol:
        name = node.name
        qualified_name = f"{parent_name}.{name}" if parent_name else name

        docstring = ast.get_docstring(node)
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        source_slice = self._slice_lines(start_line, end_line)
        start_byte, end_byte = self._calc_byte_offsets(start_line, end_line, getattr(node, "col_offset", 0))

        bases = [self._format_expr(b) for b in getattr(node, "bases", [])]
        sig = f"class {name}"
        if bases:
            sig += f"({', '.join(bases)})"

        sig_hash = hashlib.sha256(sig.encode("utf-8")).hexdigest()
        src_hash = hashlib.sha256(source_slice.encode("utf-8")).hexdigest()
        decorators = [self._format_expr(d) for d in getattr(node, "decorator_list", [])]

        return ExtractedSymbol(
            symbol_name=name,
            qualified_name=qualified_name,
            kind="class",
            language="python",
            signature=sig,
            signature_hash=sig_hash,
            docstring=docstring,
            source_code=source_slice,
            source_hash=src_hash,
            start_byte=start_byte,
            end_byte=end_byte,
            start_line=start_line,
            end_line=end_line,
            visibility="private" if name.startswith("_") and not name.startswith("__") else "public",
            parent_name=parent_name,
            decorators=decorators,
            bases=bases,
        )

    def _slice_lines(self, start_line: int, end_line: int) -> str:
        if not self.lines or start_line < 1:
            return ""
        return "".join(self.lines[start_line - 1 : min(end_line, len(self.lines))])

    def _calc_byte_offsets(self, start_line: int, end_line: int, col_offset: int) -> tuple[int, int]:
        # Compute accurate 0-based byte offset across UTF-8 content
        if start_line < 1:
            return (0, 0)
        prefix_bytes = "".join(self.lines[: start_line - 1]).encode("utf-8")
        start_byte = len(prefix_bytes) + col_offset

        slice_bytes = "".join(self.lines[start_line - 1 : min(end_line, len(self.lines))]).encode("utf-8")
        end_byte = start_byte + len(slice_bytes)
        return (start_byte, end_byte)

    def _format_function_signature(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        params: List[str] = []

        args = node.args
        for arg in args.args:
            p = arg.arg
            if arg.annotation:
                p += f": {self._format_expr(arg.annotation)}"
            params.append(p)

        if args.vararg:
            v = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                v += f": {self._format_expr(args.vararg.annotation)}"
            params.append(v)

        for arg in args.kwonlyargs:
            k = arg.arg
            if arg.annotation:
                k += f": {self._format_expr(arg.annotation)}"
            params.append(k)

        if args.kwarg:
            kw = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kw += f": {self._format_expr(args.kwarg.annotation)}"
            params.append(kw)

        sig = f"{prefix}{node.name}({', '.join(params)})"
        if getattr(node, "returns", None):
            sig += f" -> {self._format_expr(node.returns)}"
        return sig

    def _format_expr(self, expr: Optional[ast.AST]) -> str:
        if expr is None:
            return ""
        try:
            return ast.unparse(expr)
        except Exception:
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Attribute):
                return f"{self._format_expr(expr.value)}.{expr.attr}"
            if isinstance(expr, ast.Constant):
                return repr(expr.value)
            return "?"

