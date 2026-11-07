"""Unit tests for Python function definition extraction."""

from __future__ import annotations

import hashlib

from brickforge.parsers.python_symbols import PythonSymbolExtractor


class TestPythonFunctionExtraction:
    """Tests verifying function definition extraction."""

    def test_extract_top_level_functions(self):
        code = '''
@retry(attempts=3)
def process_data(items: list[str], timeout: float = 5.0) -> bool:
    """Processes given item list with retry policy."""
    return True

async def stream_events(channel: str):
    """Streams live events."""
    pass
'''
        extractor = PythonSymbolExtractor(code)
        functions = extractor.extract_functions_only()

        assert len(functions) == 2

        f1 = functions[0]
        assert f1.symbol_name == "process_data"
        assert f1.qualified_name == "process_data"
        assert f1.kind == "function"
        assert f1.language == "python"
        assert f1.is_async is False
        assert f1.docstring == "Processes given item list with retry policy."
        assert len(f1.decorators) == 1
        assert "retry(attempts=3)" in f1.decorators[0]
        assert "def process_data(items: list[str], timeout: float)" in f1.signature
        assert "-> bool" in f1.signature
        assert f1.signature_hash == hashlib.sha256(f1.signature.encode("utf-8")).hexdigest()
        assert f1.source_hash == hashlib.sha256(f1.source_code.encode("utf-8")).hexdigest()
        assert f1.start_line == 3
        assert f1.end_line == 5

        f2 = functions[1]
        assert f2.symbol_name == "stream_events"
        assert f2.is_async is True
        assert f2.signature.startswith("async def stream_events(channel: str)")

    def test_extract_nested_functions(self):
        code = '''
def outer_service(port: int):
    """Outer entry point."""
    def _inner_worker(task_id: str) -> None:
        """Inner worker logic."""
        pass
    return _inner_worker
'''
        extractor = PythonSymbolExtractor(code)
        functions = extractor.extract_functions_only()

        assert len(functions) == 2
        outer = functions[0]
        inner = functions[1]

        assert outer.symbol_name == "outer_service"
        assert outer.qualified_name == "outer_service"
        assert outer.parent_name is None
        assert outer.visibility == "public"

        assert inner.symbol_name == "_inner_worker"
        assert inner.qualified_name == "outer_service._inner_worker"
        assert inner.parent_name == "outer_service"
        assert inner.visibility == "private"
        assert inner.docstring == "Inner worker logic."

    def test_extract_signature_variations(self):
        code = '''
def complex_sig(a, *args: int, kw_only: str = "default", **kwargs) -> tuple:
    return ()
'''
        extractor = PythonSymbolExtractor(code)
        functions = extractor.extract_functions_only()
        assert len(functions) == 1
        fn = functions[0]
        assert "*args: int" in fn.signature
        assert "kw_only: str" in fn.signature
        assert "**kwargs" in fn.signature
        assert "-> tuple" in fn.signature

