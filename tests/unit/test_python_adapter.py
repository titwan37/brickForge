"""Unit tests for the Python AST language adapter."""

from __future__ import annotations

import pytest

from brickforge.parsers.python import PythonAdapter


class TestPythonAdapter:
    """Tests for PythonAdapter parsing and symbol extraction."""

    @pytest.fixture
    def adapter(self) -> PythonAdapter:
        return PythonAdapter()

    def test_can_handle(self, adapter: PythonAdapter):
        assert adapter.can_handle("main.py") is True
        assert adapter.can_handle("types.pyi") is True
        assert adapter.can_handle("script.PY") is True
        assert adapter.can_handle("lib.rs") is False
        assert adapter.can_handle("app.ts") is False

    def test_parse_functions(self, adapter: PythonAdapter):
        code = '''
@decorator_one
@decorator_two("param")
def calculate_metrics(data: list[int], factor: float = 1.0) -> dict[str, float]:
    """Calculates summary statistics."""
    return {"mean": sum(data) / len(data)}

async def fetch_remote(url: str) -> bytes:
    """Fetch remote content asynchronously."""
    return b""
'''
        result = adapter.parse(code)
        assert result.parse_status == "ok"
        assert len(result.symbols) == 2

        fn1 = result.symbols[0]
        assert fn1.symbol_name == "calculate_metrics"
        assert fn1.qualified_name == "calculate_metrics"
        assert fn1.kind == "function"
        assert fn1.language == "python"
        assert fn1.docstring == "Calculates summary statistics."
        assert fn1.is_async is False
        assert fn1.start_line == 4
        assert fn1.end_line == 6
        assert len(fn1.decorators) == 2
        assert fn1.decorators[0] == "decorator_one"
        assert "def calculate_metrics(data: list[int], factor: float)" in fn1.signature
        assert "-> dict[str, float]" in fn1.signature

        fn2 = result.symbols[1]
        assert fn2.symbol_name == "fetch_remote"
        assert fn2.is_async is True
        assert fn2.signature.startswith("async def fetch_remote")

    def test_parse_class_and_methods(self, adapter: PythonAdapter):
        code = '''
class BaseService:
    pass

class DataPipeline(BaseService, Generic[T]):
    """Data processing pipeline."""

    def __init__(self, name: str):
        self.name = name

    def execute(self, record: dict) -> bool:
        """Executes a single record."""
        return True
'''
        result = adapter.parse(code)
        assert result.parse_status == "ok"
        # Symbols: BaseService, DataPipeline, DataPipeline.__init__, DataPipeline.execute
        assert len(result.symbols) == 4

        cls = [s for s in result.symbols if s.symbol_name == "DataPipeline"][0]
        assert cls.kind == "class"
        assert cls.docstring == "Data processing pipeline."
        assert "BaseService" in cls.bases
        assert "Generic[T]" in cls.bases
        assert cls.signature == "class DataPipeline(BaseService, Generic[T])"

        methods = [s for s in result.symbols if s.kind == "method"]
        assert len(methods) == 2
        exec_method = [m for m in methods if m.symbol_name == "execute"][0]
        assert exec_method.qualified_name == "DataPipeline.execute"
        assert exec_method.parent_name == "DataPipeline"
        assert exec_method.docstring == "Executes a single record."

    def test_nested_functions(self, adapter: PythonAdapter):
        code = '''
def outer_fn(x: int):
    def inner_helper(y: int):
        return y * 2
    return inner_helper(x)
'''
        result = adapter.parse(code)
        assert len(result.symbols) == 2
        outer = result.symbols[0]
        inner = result.symbols[1]

        assert outer.symbol_name == "outer_fn"
        assert outer.kind == "function"
        assert inner.symbol_name == "inner_helper"
        assert inner.qualified_name == "outer_fn.inner_helper"
        assert inner.parent_name == "outer_fn"

    def test_syntax_error_diagnostics(self, adapter: PythonAdapter):
        bad_code = "def broken_syntax(:\n    pass\n"
        result = adapter.parse(bad_code)

        assert result.parse_status == "failed"
        assert len(result.symbols) == 0
        assert len(result.diagnostics) == 1

        diag = result.diagnostics[0]
        assert diag.severity == "error"
        assert "SyntaxError" in diag.message
        assert diag.line == 1

    def test_empty_source(self, adapter: PythonAdapter):
        result = adapter.parse("")
        assert result.parse_status == "ok"
        assert len(result.symbols) == 0

    def test_bytes_source(self, adapter: PythonAdapter):
        code_bytes = b"def from_bytes(): return 42"
        result = adapter.parse(code_bytes)
        assert result.parse_status == "ok"
        assert len(result.symbols) == 1
        assert result.symbols[0].symbol_name == "from_bytes"

