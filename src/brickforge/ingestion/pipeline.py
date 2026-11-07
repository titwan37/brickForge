"""Ingestion pipeline orchestrating file reading, parsing, error recovery, and persistence."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from brickforge.analysis.dependencies import ExtractedDependency, PythonDependencyExtractor
from brickforge.analysis.imports import PythonImportAnalyzer
from brickforge.analysis.symbol_index import RepositorySymbolIndex
from brickforge.ingestion.fingerprints import compute_file_id
from brickforge.parsers.base import ExtractedSymbol, ParseDiagnostic
from brickforge.parsers.diagnostics import DiagnosticCollector, DiagnosticReport
from brickforge.parsers.python_symbols import PythonSymbolExtractor
from brickforge.parsers.tree_sitter_runtime import TreeSitterRuntime
from brickforge.storage.brick_repository import BrickRepository

logger = logging.getLogger(__name__)


class RecoverablePythonParser:
    """Parses Python source code with fault-tolerant recovery for malformed files."""

    def __init__(self, tree_sitter_runtime: Optional[TreeSitterRuntime] = None):
        self.ts_runtime = tree_sitter_runtime or TreeSitterRuntime()

    def parse_source(
        self,
        source_code: Union[str, bytes],
        file_path: str = "",
    ) -> Tuple[List[ExtractedSymbol], DiagnosticReport]:
        """Extract valid symbols and collect diagnostics, recovering partially valid files."""
        if isinstance(source_code, bytes):
            try:
                code_str = source_code.decode("utf-8")
            except UnicodeDecodeError:
                code_str = source_code.decode("latin-1", errors="replace")
            code_bytes = source_code
        else:
            code_str = source_code
            code_bytes = source_code.encode("utf-8")

        collector = DiagnosticCollector(file_path=file_path)

        if not code_str.strip():
            return [], collector.create_report(parse_status="ok")

        # 1. Attempt standard AST parsing to see if the file is completely clean
        try:
            import ast
            ast.parse(code_str, filename=file_path or "<string>")
            extractor = PythonSymbolExtractor(code_str)
            symbols = extractor.extract_all()
            return symbols, collector.create_report(parse_status="ok")
        except SyntaxError as e:
            collector.add_error(
                message=f"SyntaxError: {e.msg}",
                line=e.lineno,
                column=e.offset,
            )

        # 2. Recover valid symbols using Tree-sitter if standard AST failed
        symbols: List[ExtractedSymbol] = []
        try:
            tree = self.ts_runtime.parse(code_bytes, "python")
            root = tree.root_node

            # Collect syntax error locations
            error_nodes = self.ts_runtime.collect_error_nodes(root)
            for err in error_nodes:
                collector.add_error(
                    message=f"Tree-sitter parse error near '{code_bytes[err.start_byte:err.end_byte][:40].decode('utf-8', errors='replace')}'",
                    line=err.start_point[0] + 1,
                    column=err.start_point[1] + 1,
                )

            # Extract valid top-level symbols that do not contain errors
            self._extract_recoverable_nodes(root, code_bytes, symbols, parent_name=None)
        except Exception as ex:
            collector.add_error(f"Tree-sitter recovery failure: {ex}")

        if symbols:
            status = "partial"
        else:
            status = "failed"

        return symbols, collector.create_report(parse_status=status)

    def _extract_recoverable_nodes(
        self,
        node: Any,
        code_bytes: bytes,
        symbols: List[ExtractedSymbol],
        parent_name: Optional[str] = None,
    ) -> None:
        """Traverse child nodes and extract valid functions and classes."""
        for child in node.children:
            if child.type == "function_definition" and not child.has_error:
                name_node = child.child_by_field_name("name")
                if not name_node:
                    continue
                name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                qual_name = f"{parent_name}.{name}" if parent_name else name
                start_byte = child.start_byte
                end_byte = child.end_byte
                sub_code = code_bytes[start_byte:end_byte].decode("utf-8", errors="replace")
                sig_line = sub_code.splitlines()[0] if sub_code else f"def {name}():"

                sym = ExtractedSymbol(
                    symbol_name=name,
                    qualified_name=qual_name,
                    kind="method" if parent_name else "function",
                    language="python",
                    signature=sig_line,
                    signature_hash=hashlib.sha256(sig_line.encode("utf-8")).hexdigest(),
                    docstring=None,
                    source_code=sub_code,
                    source_hash=hashlib.sha256(sub_code.encode("utf-8")).hexdigest(),
                    start_byte=start_byte,
                    end_byte=end_byte,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    parent_name=parent_name,
                )
                symbols.append(sym)

            elif child.type == "class_definition" and not child.has_error:
                name_node = child.child_by_field_name("name")
                if not name_node:
                    continue
                name = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
                qual_name = f"{parent_name}.{name}" if parent_name else name
                start_byte = child.start_byte
                end_byte = child.end_byte
                sub_code = code_bytes[start_byte:end_byte].decode("utf-8", errors="replace")
                sig_line = sub_code.splitlines()[0] if sub_code else f"class {name}:"

                sym = ExtractedSymbol(
                    symbol_name=name,
                    qualified_name=qual_name,
                    kind="class",
                    language="python",
                    signature=sig_line,
                    signature_hash=hashlib.sha256(sig_line.encode("utf-8")).hexdigest(),
                    docstring=None,
                    source_code=sub_code,
                    source_hash=hashlib.sha256(sub_code.encode("utf-8")).hexdigest(),
                    start_byte=start_byte,
                    end_byte=end_byte,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    parent_name=parent_name,
                )
                symbols.append(sym)

                # Extract methods inside class body
                body = child.child_by_field_name("body")
                if body:
                    self._extract_recoverable_nodes(body, code_bytes, symbols, parent_name=qual_name)


class IngestionPipeline:
    """Processes source files through parsing, diagnostic collection, and persistence."""

    def __init__(
        self,
        repository_id: str,
        brick_repository: BrickRepository,
        root_path: Union[str, Path] = "",
        symbol_index: Optional[RepositorySymbolIndex] = None,
    ):
        self.repository_id = repository_id
        self.brick_repo = brick_repository
        self.root_path = Path(root_path) if root_path else None
        self.symbol_index = symbol_index or RepositorySymbolIndex()
        self.parser = RecoverablePythonParser()
        self.dep_extractor = PythonDependencyExtractor()
        self.import_analyzer = PythonImportAnalyzer()

    def process_file_content(
        self,
        relative_path: str,
        content: Union[str, bytes],
        file_hash: Optional[str] = None,
        modified_ns: Optional[int] = None,
    ) -> Tuple[int, DiagnosticReport, List[int]]:
        """Process a single file's content in memory without executing code.

        Returns:
            Tuple of (source_file_row_id, diagnostic_report, list_of_brick_row_ids)
        """
        norm_path = relative_path.replace("\\", "/").strip().lstrip("/")
        if isinstance(content, str):
            code_str = content
            code_bytes = content.encode("utf-8")
        else:
            code_bytes = content
            try:
                code_str = content.decode("utf-8")
            except UnicodeDecodeError:
                code_str = content.decode("latin-1", errors="replace")

        if not file_hash:
            file_hash = hashlib.sha256(code_bytes).hexdigest()

        loc = len(code_str.splitlines())
        byte_size = len(code_bytes)

        # Check if file is supported
        if not norm_path.endswith((".py", ".pyi")):
            report = DiagnosticReport(file_path=norm_path, parse_status="unsupported")
            file_row_id = self.brick_repo.upsert_source_file(
                repository_id=self.repository_id,
                relative_path=norm_path,
                file_hash=file_hash,
                language="unknown",
                byte_size=byte_size,
                loc=loc,
                modified_ns=modified_ns,
                parse_status="unsupported",
                parse_diagnostics=report.to_json(),
            )
            return file_row_id, report, []

        # Parse with error recovery
        symbols, report = self.parser.parse_source(code_str, file_path=norm_path)

        # Save source file record
        file_row_id = self.brick_repo.upsert_source_file(
            repository_id=self.repository_id,
            relative_path=norm_path,
            file_hash=file_hash,
            language="python",
            byte_size=byte_size,
            loc=loc,
            modified_ns=modified_ns,
            parser_name="tree_sitter_python" if report.parse_status == "partial" else "python_ast",
            parser_version="1.0",
            parse_status=report.parse_status,
            parse_diagnostics=report.to_json(),
        )

        # Register symbols in symbol index
        self.symbol_index.register_file_symbols(norm_path, symbols)

        # Persist valid bricks
        brick_row_ids: List[int] = []
        name_to_brick_row: Dict[str, int] = {}

        for sym in symbols:
            parent_id = name_to_brick_row.get(sym.parent_name) if sym.parent_name else None
            brick_row = self.brick_repo.upsert_brick(
                file_row_id=file_row_id,
                symbol=sym,
                parent_row_id=parent_id,
            )
            brick_row_ids.append(brick_row)
            name_to_brick_row[sym.qualified_name] = brick_row

        return file_row_id, report, brick_row_ids

    def process_file_on_disk(self, relative_path: str) -> Tuple[int, DiagnosticReport, List[int]]:
        """Read file from disk safely (read-only, no execution) and process."""
        if not self.root_path:
            raise ValueError("root_path must be configured to process files on disk.")

        full_path = self.root_path / relative_path
        if not full_path.is_file():
            raise FileNotFoundError(f"Source file not found: {full_path}")

        st = full_path.stat()
        content = full_path.read_bytes()
        return self.process_file_content(
            relative_path=relative_path,
            content=content,
            modified_ns=st.st_mtime_ns,
        )
