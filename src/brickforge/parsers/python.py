"""Python language AST adapter for BrickForge."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import List, Optional, Sequence, Union

from brickforge.parsers.base import (
    BaseLanguageAdapter,
    ExtractedSymbol,
    ParseDiagnostic,
    ParsedFileResult,
)


class PythonAdapter(BaseLanguageAdapter):
    """AST adapter for Python source code using Python's native AST engine."""

    @property
    def language_name(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> Sequence[str]:
        return (".py", ".pyi")

    def parse(
        self,
        source_code: Union[str, bytes],
        file_path: Optional[Union[str, Path]] = None,
    ) -> ParsedFileResult:
        if isinstance(source_code, bytes):
            try:
                code_str = source_code.decode("utf-8")
            except UnicodeDecodeError:
                code_str = source_code.decode("latin-1", errors="replace")
        else:
            code_str = source_code

        lines = code_str.splitlines(keepends=True)
        loc = len(lines)

        result = ParsedFileResult(
            language="python",
            loc=loc,
            parser_name="python_ast",
            parser_version="1.0",
        )

        if not code_str.strip():
            result.parse_status = "ok"
            return result

        try:
            tree = ast.parse(code_str, filename=str(file_path or "<string>"))
        except SyntaxError as e:
            result.parse_status = "failed"
            result.diagnostics.append(
                ParseDiagnostic(
                    severity="error",
                    message=f"SyntaxError: {e.msg}",
                    line=e.lineno,
                    column=e.offset,
                )
            )
            return result

        module_docstring = ast.get_docstring(tree)
        symbols: List[ExtractedSymbol] = []

        self._extract_node_symbols(tree, code_str, lines, symbols, parent_name=None)
        result.symbols = symbols
        result.parse_status = "ok"
        return result

    def _extract_node_symbols(
        self,
        parent_node: ast.AST,
        source_code: str,
        lines: Sequence[str],
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> None:
        for node in getattr(parent_node, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = self._extract_function(node, source_code, lines, parent_name)
                symbols.append(symbol)
                # Recurse for nested functions
                self._extract_node_symbols(node, source_code, lines, symbols, parent_name=symbol.qualified_name)

            elif isinstance(node, ast.ClassDef):
                cls_symbol = self._extract_class(node, source_code, lines, parent_name)
                symbols.append(cls_symbol)
                # Recurse for methods and nested classes
                self._extract_node_symbols(node, source_code, lines, symbols, parent_name=cls_symbol.qualified_name)

    def _extract_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        source_code: str,
        lines: Sequence[str],
        parent_name: Optional[str] = None,
    ) -> ExtractedSymbol:
        is_method = parent_name is not None
        kind = "method" if is_method else "function"
        name = node.name
        qualified_name = f"{parent_name}.{name}" if parent_name else name

        docstring = ast.get_docstring(node)
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        # Byte offsets
        start_byte = getattr(node, "col_offset", 0)
        source_slice = self._get_source_slice(lines, start_line, end_line)

        # Build signature string
        sig = self._format_function_signature(node)
        sig_hash = hashlib.sha256(sig.encode("utf-8")).hexdigest()
        src_hash = hashlib.sha256(source_slice.encode("utf-8")).hexdigest()

        decorators = [self._format_expr(d) for d in getattr(node, "decorator_list", [])]

        return ExtractedSymbol(
            symbol_name=name,
            qualified_name=qualified_name,
            kind=kind,
            language="python",
            signature=sig,
            signature_hash=sig_hash,
            docstring=docstring,
            source_code=source_slice,
            source_hash=src_hash,
            start_byte=start_byte,
            end_byte=start_byte + len(source_slice.encode("utf-8")),
            start_line=start_line,
            end_line=end_line,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            visibility="private" if name.startswith("_") and not name.startswith("__") else "public",
            parent_name=parent_name,
            decorators=decorators,
        )

    def _extract_class(
        self,
        node: ast.ClassDef,
        source_code: str,
        lines: Sequence[str],
        parent_name: Optional[str] = None,
    ) -> ExtractedSymbol:
        name = node.name
        qualified_name = f"{parent_name}.{name}" if parent_name else name

        docstring = ast.get_docstring(node)
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        start_byte = getattr(node, "col_offset", 0)
        source_slice = self._get_source_slice(lines, start_line, end_line)

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
            end_byte=start_byte + len(source_slice.encode("utf-8")),
            start_line=start_line,
            end_line=end_line,
            visibility="private" if name.startswith("_") and not name.startswith("__") else "public",
            parent_name=parent_name,
            decorators=decorators,
            bases=bases,
        )

    def _get_source_slice(self, lines: Sequence[str], start_line: int, end_line: int) -> str:
        """Extract exact line slice from source lines (1-indexed)."""
        if not lines or start_line < 1:
            return ""
        actual_start = start_line - 1
        actual_end = min(end_line, len(lines))
        return "".join(lines[actual_start:actual_end])

    def _format_function_signature(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        args_parts: List[str] = []

        args = node.args
        for arg in args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._format_expr(arg.annotation)}"
            args_parts.append(arg_str)

        if args.vararg:
            v_str = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                v_str += f": {self._format_expr(args.vararg.annotation)}"
            args_parts.append(v_str)

        for arg in args.kwonlyargs:
            k_str = arg.arg
            if arg.annotation:
                k_str += f": {self._format_expr(arg.annotation)}"
            args_parts.append(k_str)

        if args.kwarg:
            kw_str = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kw_str += f": {self._format_expr(args.kwarg.annotation)}"
            args_parts.append(kw_str)

        sig = f"{prefix}{node.name}({', '.join(args_parts)})"
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

