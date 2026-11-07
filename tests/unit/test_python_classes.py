"""Unit tests for Python class and method definition extraction."""

from __future__ import annotations

import hashlib

from brickforge.parsers.python_symbols import PythonSymbolExtractor


class TestPythonClassExtraction:
    """Tests verifying class and method definition extraction."""

    def test_extract_classes_and_bases(self):
        code = '''
@dataclass
class AbstractStore(BaseStore, Mapping[str, Any]):
    """Abstract storage contract."""
    pass
'''
        extractor = PythonSymbolExtractor(code)
        classes = extractor.extract_classes_only()

        assert len(classes) == 1
        cls = classes[0]
        assert cls.symbol_name == "AbstractStore"
        assert cls.qualified_name == "AbstractStore"
        assert cls.kind == "class"
        assert cls.docstring == "Abstract storage contract."
        assert len(cls.bases) == 2
        assert "BaseStore" in cls.bases
        assert "Mapping[str, Any]" in cls.bases
        assert len(cls.decorators) == 1
        assert cls.decorators[0] == "dataclass"
        assert cls.signature == "class AbstractStore(BaseStore, Mapping[str, Any])"
        assert cls.start_line == 3
        assert cls.end_line == 5

    def test_extract_methods_linked_to_class(self):
        code = '''
class CacheManager:
    """In-memory cache manager."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl

    @classmethod
    def from_env(cls) -> CacheManager:
        return cls()

    @staticmethod
    def hash_key(raw: str) -> str:
        return raw.strip()

    def get(self, key: str) -> Optional[bytes]:
        """Fetch cached item."""
        return None
'''
        extractor = PythonSymbolExtractor(code)
        symbols = extractor.extract_all()

        # 1 class + 4 methods
        assert len(symbols) == 5

        cls = [s for s in symbols if s.kind == "class"][0]
        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 4

        # Verify all methods have parent_name pointing to class
        for m in methods:
            assert m.parent_name == "CacheManager"
            assert m.qualified_name.startswith("CacheManager.")

        init_m = [m for m in methods if m.symbol_name == "__init__"][0]
        assert "def __init__(self, ttl: int)" in init_m.signature

        cls_m = [m for m in methods if m.symbol_name == "from_env"][0]
        assert len(cls_m.decorators) == 1
        assert cls_m.decorators[0] == "classmethod"

        get_m = [m for m in methods if m.symbol_name == "get"][0]
        assert get_m.docstring == "Fetch cached item."

    def test_nested_classes(self):
        code = '''
class Outer:
    class Inner:
        def inner_method(self):
            pass
'''
        extractor = PythonSymbolExtractor(code)
        symbols = extractor.extract_all()

        assert len(symbols) == 3
        outer = [s for s in symbols if s.symbol_name == "Outer"][0]
        inner = [s for s in symbols if s.symbol_name == "Inner"][0]
        method = [s for s in symbols if s.symbol_name == "inner_method"][0]

        assert outer.parent_name is None
        assert inner.parent_name == "Outer"
        assert inner.qualified_name == "Outer.Inner"
        assert method.parent_name == "Outer.Inner"
        assert method.qualified_name == "Outer.Inner.inner_method"

