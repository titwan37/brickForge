"""Unit tests for static repository symbol indexing and import resolution."""

import hashlib
from pathlib import Path
import pytest

from brickforge.analysis.imports import ImportStatement
from brickforge.analysis.symbol_index import RepositorySymbolIndex, SymbolLocation
from brickforge.parsers.base import ExtractedSymbol


def _make_symbol(
    name: str,
    qual_name: str,
    kind: str,
    start_line: int,
    end_line: int,
) -> ExtractedSymbol:
    code = f"def {name}(): pass" if kind == "function" else f"class {name}: pass"
    return ExtractedSymbol(
        symbol_name=name,
        qualified_name=qual_name,
        kind=kind,
        language="python",
        signature=f"{kind} {name}",
        signature_hash=hashlib.sha256(name.encode()).hexdigest(),
        docstring=None,
        source_code=code,
        source_hash=hashlib.sha256(code.encode()).hexdigest(),
        start_byte=0,
        end_byte=len(code),
        start_line=start_line,
        end_line=end_line,
    )


def test_path_to_module_name():
    index = RepositorySymbolIndex()

    assert index.path_to_module_name("src/brickforge/parsers/python.py") == "brickforge.parsers.python"
    assert index.path_to_module_name("lib/utils/helpers.py") == "utils.helpers"
    assert index.path_to_module_name("pkg/__init__.py") == "pkg"
    assert index.path_to_module_name("src/pkg/__init__.pyi") == "pkg"
    assert index.path_to_module_name("foo/bar/baz.py") == "foo.bar.baz"
    assert index.path_to_module_name(Path("src/brickforge/models/scan.py")) == "brickforge.models.scan"


def test_register_and_lookup_symbols():
    index = RepositorySymbolIndex()
    symbols = [
        _make_symbol("BaseParser", "BaseParser", "class", 10, 50),
        _make_symbol("parse", "BaseParser.parse", "method", 15, 25),
    ]

    mod = index.register_file_symbols("src/brickforge/parsers/base.py", symbols)
    assert mod == "brickforge.parsers.base"

    loc = index.lookup_symbol_in_module("brickforge.parsers.base", "BaseParser")
    assert loc is not None
    assert loc.symbol_name == "BaseParser"
    assert loc.qualified_name == "brickforge.parsers.base.BaseParser"
    assert loc.relative_path == "src/brickforge/parsers/base.py"
    assert loc.kind == "class"
    assert loc.start_line == 10
    assert loc.end_line == 50


def test_resolve_relative_module():
    index = RepositorySymbolIndex()
    # level 1: current package directory
    resolved = index.resolve_relative_module("brickforge.parsers.python", relative_level=1, target_suffix="base")
    assert resolved == "brickforge.parsers.base"

    # level 2: parent package
    resolved = index.resolve_relative_module("brickforge.parsers.python", relative_level=2, target_suffix="models")
    assert resolved == "brickforge.models"

    # level 1: package itself without suffix
    resolved = index.resolve_relative_module("brickforge.parsers.python", relative_level=1, target_suffix="")
    assert resolved == "brickforge.parsers"


def test_resolve_import_targets():
    index = RepositorySymbolIndex()

    # Register module A
    symbols_a = [_make_symbol("ExtractedSymbol", "ExtractedSymbol", "class", 5, 20)]
    index.register_file_symbols("src/brickforge/parsers/base.py", symbols_a)

    # Register module B
    symbols_b = [_make_symbol("PythonParser", "PythonParser", "class", 10, 60)]
    index.register_file_symbols("src/brickforge/parsers/python.py", symbols_b)

    # Test resolving absolute import from module B
    stmt_abs = ImportStatement(
        raw_statement="from brickforge.parsers.base import ExtractedSymbol, NonExistent",
        module="brickforge.parsers.base",
        imported_symbols=["ExtractedSymbol", "NonExistent"],
        line=2,
    )
    res_abs = index.resolve_import_targets("src/brickforge/parsers/python.py", stmt_abs)
    assert res_abs["ExtractedSymbol"] is not None
    assert res_abs["ExtractedSymbol"].qualified_name == "brickforge.parsers.base.ExtractedSymbol"
    assert res_abs["NonExistent"] is None

    # Test resolving relative import from module B
    stmt_rel = ImportStatement(
        raw_statement="from .base import ExtractedSymbol",
        module="base",
        imported_symbols=["ExtractedSymbol"],
        is_relative=True,
        relative_level=1,
        line=3,
    )
    res_rel = index.resolve_import_targets("src/brickforge/parsers/python.py", stmt_rel)
    assert res_rel["ExtractedSymbol"] is not None
    assert res_rel["ExtractedSymbol"].relative_path == "src/brickforge/parsers/base.py"

    # Test submodule resolution
    stmt_sub = ImportStatement(
        raw_statement="from brickforge import parsers",
        module="brickforge",
        imported_symbols=["parsers"],
        line=4,
    )
    res_sub = index.resolve_import_targets("src/brickforge/main.py", stmt_sub)
    assert res_sub["parsers"] is not None
    assert res_sub["parsers"].kind == "module"
    assert res_sub["parsers"].relative_path == "src/brickforge/parsers"
