"""Multi-language symbol extractor using Tree-sitter grammars.

Supports C#, TypeScript, TSX, JavaScript, C++, C, Go, Rust, and Java.
Extracts classes, interfaces, structs, enums, functions, and methods
with type signatures, line spans, docstrings, and complexity metrics.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, List, Optional, Tuple

from brickforge.parsers.base import ExtractedSymbol
from brickforge.parsers.diagnostics import DiagnosticCollector, DiagnosticReport
from brickforge.parsers.tree_sitter_runtime import TreeSitterRuntime

logger = logging.getLogger(__name__)


LANGUAGE_GRAMMAR_MAP = {
    "csharp": "csharp",
    "typescript": "typescript",
    "typescript-react": "tsx",
    "javascript": "javascript",
    "cpp": "cpp",
    "c": "c",
    "go": "go",
    "rust": "rust",
    "java": "java",
}


class MultiLanguageSymbolExtractor:
    """Extracts symbols from source files across non-Python languages using Tree-sitter."""

    def __init__(self, ts_runtime: Optional[TreeSitterRuntime] = None):
        self.ts_runtime = ts_runtime or TreeSitterRuntime()

    def can_extract(self, language: str) -> bool:
        """Check if Tree-sitter has a loaded grammar for this language."""
        grammar = LANGUAGE_GRAMMAR_MAP.get(language.lower(), language.lower())
        return self.ts_runtime.is_language_available(grammar)

    def extract_symbols(
        self,
        code_bytes: bytes,
        language: str,
        file_path: str = "",
    ) -> Tuple[List[ExtractedSymbol], DiagnosticReport]:
        """Parse source code with the appropriate Tree-sitter grammar and extract symbols."""
        grammar_name = LANGUAGE_GRAMMAR_MAP.get(language.lower(), language.lower())
        collector = DiagnosticCollector(file_path=file_path)

        if not self.ts_runtime.is_language_available(grammar_name):
            collector.add_warning(f"No Tree-sitter grammar registered for '{grammar_name}'")
            return [], collector.create_report(parse_status="unsupported")

        try:
            tree = self.ts_runtime.parse(code_bytes, grammar_name)
        except Exception as e:
            collector.add_error(f"Tree-sitter parse failure for {language}: {e}")
            return [], collector.create_report(parse_status="failed")

        root = tree.root_node
        error_nodes = self.ts_runtime.collect_error_nodes(root)
        for err in error_nodes[:10]:
            collector.add_error(
                message=f"Syntax error at L{err.start_point[0] + 1}:C{err.start_point[1] + 1}",
                line=err.start_point[0] + 1,
                column=err.start_point[1] + 1,
            )

        symbols: List[ExtractedSymbol] = []
        try:
            if grammar_name in ("csharp", "cs"):
                self._extract_csharp(root, code_bytes, symbols, parent_name=None)
            elif grammar_name in ("typescript", "tsx", "javascript"):
                self._extract_ts_js(root, code_bytes, language, symbols, parent_name=None)
            elif grammar_name in ("cpp", "c"):
                self._extract_cpp(root, code_bytes, language, symbols, parent_name=None)
            elif grammar_name == "go":
                self._extract_go(root, code_bytes, symbols, parent_name=None)
            elif grammar_name == "rust":
                self._extract_rust(root, code_bytes, symbols, parent_name=None)
            elif grammar_name == "java":
                self._extract_java(root, code_bytes, symbols, parent_name=None)
            else:
                self._extract_generic(root, code_bytes, language, symbols, parent_name=None)
        except Exception as ex:
            logger.warning("Error during %s AST symbol extraction: %s", language, ex)
            collector.add_error(f"Symbol extraction error: {ex}")

        status = "ok"
        if error_nodes and symbols:
            status = "partial"
        elif error_nodes and not symbols:
            status = "failed"

        return symbols, collector.create_report(parse_status=status)

    # -------------------------------------------------------------------------
    # C# Symbol Extraction
    # -------------------------------------------------------------------------
    def _extract_csharp(
        self,
        node: Any,
        code_bytes: bytes,
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> None:
        ntype = node.type
        kind: Optional[str] = None

        if ntype in ("class_declaration", "record_declaration"):
            kind = "class"
        elif ntype == "struct_declaration":
            kind = "struct"
        elif ntype == "interface_declaration":
            kind = "interface"
        elif ntype == "enum_declaration":
            kind = "enum"
        elif ntype in ("method_declaration", "constructor_declaration"):
            kind = "method" if parent_name else "function"
        elif ntype == "property_declaration":
            kind = "property"

        if kind:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                qual_name = f"{parent_name}.{name}" if parent_name else name
                sub_bytes = code_bytes[node.start_byte:node.end_byte]
                sub_code = sub_bytes.decode("utf-8", errors="replace")
                sig_line = sub_code.splitlines()[0].strip() if sub_code else f"{kind} {name}"

                # Extract modifiers & docstrings
                is_async = "async" in sig_line
                visibility = "public" if "public" in sig_line else ("private" if "private" in sig_line else ("protected" if "protected" in sig_line else ("internal" if "internal" in sig_line else None)))
                docstring = self._extract_preceding_docstring(node, code_bytes)

                sym = ExtractedSymbol(
                    symbol_name=name,
                    qualified_name=qual_name,
                    kind=kind,
                    language="csharp",
                    signature=sig_line,
                    signature_hash=hashlib.sha256(sig_line.encode("utf-8")).hexdigest(),
                    docstring=docstring,
                    source_code=sub_code,
                    source_hash=hashlib.sha256(sub_code.encode("utf-8")).hexdigest(),
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    is_async=is_async,
                    visibility=visibility,
                    parent_name=parent_name,
                )
                symbols.append(sym)

                # For container kinds (class, struct, interface), inspect children with this qual_name as parent
                if kind in ("class", "struct", "interface"):
                    body = node.child_by_field_name("body") or node
                    for child in body.children:
                        self._extract_csharp(child, code_bytes, symbols, parent_name=qual_name)
                    return

        # Otherwise continue traversal down child nodes
        for child in node.children:
            self._extract_csharp(child, code_bytes, symbols, parent_name=parent_name)

    # -------------------------------------------------------------------------
    # TypeScript / TSX / JavaScript Symbol Extraction
    # -------------------------------------------------------------------------
    def _extract_ts_js(
        self,
        node: Any,
        code_bytes: bytes,
        language: str,
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> None:
        ntype = node.type
        kind: Optional[str] = None

        if ntype == "class_declaration":
            kind = "class"
        elif ntype == "interface_declaration":
            kind = "interface"
        elif ntype == "type_alias_declaration":
            kind = "type_alias"
        elif ntype == "enum_declaration":
            kind = "enum"
        elif ntype in ("function_declaration", "generator_function_declaration"):
            kind = "function"
        elif ntype in ("method_definition", "method_signature"):
            kind = "method" if parent_name else "function"

        # Check for const/let arrow functions: const myFunc = () => {}
        if ntype == "lexical_declaration":
            for decl in node.children:
                if decl.type == "variable_declarator":
                    val_node = decl.child_by_field_name("value")
                    if val_node and val_node.type in ("arrow_function", "function_expression"):
                        name_node = decl.child_by_field_name("name")
                        if name_node:
                            self._record_symbol(
                                node=decl,
                                name_node=name_node,
                                kind="function",
                                language=language,
                                code_bytes=code_bytes,
                                symbols=symbols,
                                parent_name=parent_name,
                            )
            return

        if kind:
            name_node = node.child_by_field_name("name")
            if name_node:
                qual_name = self._record_symbol(
                    node=node,
                    name_node=name_node,
                    kind=kind,
                    language=language,
                    code_bytes=code_bytes,
                    symbols=symbols,
                    parent_name=parent_name,
                )

                if kind in ("class", "interface"):
                    body = node.child_by_field_name("body") or node
                    for child in body.children:
                        self._extract_ts_js(child, code_bytes, language, symbols, parent_name=qual_name)
                    return

        for child in node.children:
            self._extract_ts_js(child, code_bytes, language, symbols, parent_name=parent_name)

    # -------------------------------------------------------------------------
    # C / C++ Symbol Extraction
    # -------------------------------------------------------------------------
    def _extract_cpp(
        self,
        node: Any,
        code_bytes: bytes,
        language: str,
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> None:
        ntype = node.type
        kind: Optional[str] = None

        if ntype in ("class_specifier", "struct_specifier"):
            kind = "class" if "class" in ntype else "struct"
            name_node = node.child_by_field_name("name")
            if name_node:
                qual_name = self._record_symbol(
                    node=node,
                    name_node=name_node,
                    kind=kind,
                    language=language,
                    code_bytes=code_bytes,
                    symbols=symbols,
                    parent_name=parent_name,
                )
                body = node.child_by_field_name("body") or node
                for child in body.children:
                    self._extract_cpp(child, code_bytes, language, symbols, parent_name=qual_name)
                return

        elif ntype == "function_definition":
            # In C/C++, function declarator holds the name
            decl = node.child_by_field_name("declarator")
            name_node = None
            if decl:
                if decl.type == "function_declarator":
                    name_node = decl.child_by_field_name("declarator")
                else:
                    name_node = decl
            if name_node:
                self._record_symbol(
                    node=node,
                    name_node=name_node,
                    kind="method" if parent_name else "function",
                    language=language,
                    code_bytes=code_bytes,
                    symbols=symbols,
                    parent_name=parent_name,
                )
                return

        for child in node.children:
            self._extract_cpp(child, code_bytes, language, symbols, parent_name=parent_name)

    # -------------------------------------------------------------------------
    # Go, Rust, Java & Generic Fallbacks
    # -------------------------------------------------------------------------
    def _extract_go(self, node: Any, code_bytes: bytes, symbols: List[ExtractedSymbol], parent_name: Optional[str]) -> None:
        if node.type in ("function_declaration", "method_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node:
                self._record_symbol(node, name_node, "function" if node.type == "function_declaration" else "method", "go", code_bytes, symbols, parent_name)
                return
        for child in node.children:
            self._extract_go(child, code_bytes, symbols, parent_name)

    def _extract_rust(self, node: Any, code_bytes: bytes, symbols: List[ExtractedSymbol], parent_name: Optional[str]) -> None:
        if node.type in ("struct_item", "enum_item", "trait_item", "function_item"):
            kind = "struct" if "struct" in node.type else ("enum" if "enum" in node.type else ("trait" if "trait" in node.type else "function"))
            name_node = node.child_by_field_name("name")
            if name_node:
                self._record_symbol(node, name_node, kind, "rust", code_bytes, symbols, parent_name)
                return
        for child in node.children:
            self._extract_rust(child, code_bytes, symbols, parent_name)

    def _extract_java(self, node: Any, code_bytes: bytes, symbols: List[ExtractedSymbol], parent_name: Optional[str]) -> None:
        if node.type in ("class_declaration", "interface_declaration", "enum_declaration", "method_declaration", "constructor_declaration"):
            kind = "class" if "class" in node.type else ("interface" if "interface" in node.type else ("enum" if "enum" in node.type else "method"))
            name_node = node.child_by_field_name("name")
            if name_node:
                qual = self._record_symbol(node, name_node, kind, "java", code_bytes, symbols, parent_name)
                if kind in ("class", "interface"):
                    body = node.child_by_field_name("body") or node
                    for child in body.children:
                        self._extract_java(child, code_bytes, symbols, qual)
                    return
        for child in node.children:
            self._extract_java(child, code_bytes, symbols, parent_name)

    def _extract_generic(self, node: Any, code_bytes: bytes, language: str, symbols: List[ExtractedSymbol], parent_name: Optional[str]) -> None:
        for child in node.children:
            self._extract_generic(child, code_bytes, language, symbols, parent_name)

    # -------------------------------------------------------------------------
    # Helper to create ExtractedSymbol
    # -------------------------------------------------------------------------
    def _record_symbol(
        self,
        node: Any,
        name_node: Any,
        kind: str,
        language: str,
        code_bytes: bytes,
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> str:
        name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace").strip()
        qual_name = f"{parent_name}.{name}" if parent_name else name
        sub_bytes = code_bytes[node.start_byte:node.end_byte]
        sub_code = sub_bytes.decode("utf-8", errors="replace")
        sig_line = sub_code.splitlines()[0].strip() if sub_code else f"{kind} {name}"

        is_async = "async" in sig_line
        visibility = "public" if "public" in sig_line or "export" in sig_line else ("private" if "private" in sig_line else None)
        docstring = self._extract_preceding_docstring(node, code_bytes)

        sym = ExtractedSymbol(
            symbol_name=name,
            qualified_name=qual_name,
            kind=kind,
            language=language,
            signature=sig_line,
            signature_hash=hashlib.sha256(sig_line.encode("utf-8")).hexdigest(),
            docstring=docstring,
            source_code=sub_code,
            source_hash=hashlib.sha256(sub_code.encode("utf-8")).hexdigest(),
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            is_async=is_async,
            visibility=visibility,
            parent_name=parent_name,
        )
        symbols.append(sym)
        return qual_name

    def _extract_preceding_docstring(self, node: Any, code_bytes: bytes) -> Optional[str]:
        """Collect all preceding consecutive comment siblings (e.g. multiple /// lines or /** */)."""
        comments = []
        curr = node.prev_sibling
        while curr and curr.type in ("comment", "block_comment"):
            c_text = code_bytes[curr.start_byte:curr.end_byte].decode("utf-8", errors="replace").strip()
            comments.append(c_text)
            curr = curr.prev_sibling

        if not comments:
            return None

        # Reverse since we collected backwards
        comments.reverse()
        full_comment = "\n".join(comments)

        lines = []
        for l in full_comment.splitlines():
            clean_l = l.strip().lstrip("/*").rstrip("*/").lstrip("/").strip()
            clean_l = clean_l.replace("<summary>", "").replace("</summary>", "").strip()
            if clean_l:
                lines.append(clean_l)
        if lines:
            return "\n".join(lines)
        return None