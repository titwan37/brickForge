"""Unit tests for Python import and package analysis."""

from __future__ import annotations

import pytest

from brickforge.analysis.imports import ImportStatement, PythonImportAnalyzer


class TestImportAnalysis:
    """Tests verifying import statement extraction and classification."""

    def test_extract_and_classify_stdlib(self):
        code = '''
import os
import sys as system
from pathlib import Path, PurePath as PP
'''
        analyzer = PythonImportAnalyzer()
        imports = analyzer.extract_imports(code)

        assert len(imports) == 3

        imp_os = imports[0]
        assert imp_os.module == "os"
        assert imp_os.kind == "stdlib"
        assert imp_os.is_relative is False

        imp_sys = imports[1]
        assert imp_sys.module == "sys"
        assert imp_sys.kind == "stdlib"
        assert imp_sys.alias_mapping == {"system": "sys"}

        imp_path = imports[2]
        assert imp_path.module == "pathlib"
        assert imp_path.kind == "stdlib"
        assert "Path" in imp_path.imported_symbols
        assert "PurePath" in imp_path.imported_symbols
        assert imp_path.alias_mapping == {"PP": "PurePath"}

    def test_extract_and_classify_relative_local(self):
        code = '''
from .models import CodeBrick
from ..analysis.graph import traverse_graph
from . import base_utils
'''
        analyzer = PythonImportAnalyzer()
        imports = analyzer.extract_imports(code)

        assert len(imports) == 3
        for imp in imports:
            assert imp.kind == "local"
            assert imp.is_relative is True

        assert imports[0].relative_level == 1
        assert imports[1].relative_level == 2
        assert "traverse_graph" in imports[1].imported_symbols

    def test_extract_and_classify_third_party(self):
        code = '''
import pydantic
from fastapi import FastAPI, HTTPException
import tree_sitter
'''
        analyzer = PythonImportAnalyzer(known_local_modules={"brickforge"})
        imports = analyzer.extract_imports(code)

        assert len(imports) == 3
        for imp in imports:
            assert imp.kind == "third_party"

        external = analyzer.get_external_packages(imports)
        assert external == ["fastapi", "pydantic", "tree_sitter"]

    def test_known_local_modules_override(self):
        code = '''
import brickforge
from brickforge.models import ScanRun
'''
        analyzer = PythonImportAnalyzer(known_local_modules={"brickforge"})
        imports = analyzer.extract_imports(code)

        assert len(imports) == 2
        assert imports[0].kind == "local"
        assert imports[1].kind == "local"
        assert analyzer.get_external_packages(imports) == []

    def test_syntax_error_returns_empty(self):
        bad_code = "from import where what;"
        analyzer = PythonImportAnalyzer()
        assert analyzer.extract_imports(bad_code) == []

