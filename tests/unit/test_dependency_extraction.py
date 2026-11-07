"""Unit tests for AST dependency, call, and inheritance relationship extraction."""

import hashlib
import pytest

from brickforge.analysis.dependencies import (
    ExtractedDependency,
    PythonDependencyExtractor,
    VALID_DEPENDENCY_TYPES,
)
from brickforge.analysis.imports import ImportStatement
from brickforge.analysis.symbol_index import RepositorySymbolIndex
from brickforge.parsers.base import ExtractedSymbol


def _make_symbol(name: str, code: str) -> ExtractedSymbol:
    return ExtractedSymbol(
        symbol_name=name,
        qualified_name=name,
        kind="class" if "class " in code else "function",
        language="python",
        signature=name,
        signature_hash=hashlib.sha256(name.encode()).hexdigest(),
        docstring=None,
        source_code=code,
        source_hash=hashlib.sha256(code.encode()).hexdigest(),
        start_byte=0,
        end_byte=len(code),
        start_line=1,
        end_line=len(code.splitlines()),
    )


def test_dependency_dataclass_validation():
    # Valid
    dep = ExtractedDependency(
        dependency_type="calls",
        target_symbol="calc",
        confidence=0.9,
        line_number=1,
    )
    assert dep.resolution_status == "unresolved"

    # Invalid type
    with pytest.raises(ValueError, match="Invalid dependency_type"):
        ExtractedDependency(
            dependency_type="invalid_type",
            target_symbol="calc",
            confidence=0.9,
            line_number=1,
        )

    # Invalid confidence
    with pytest.raises(ValueError, match="Confidence"):
        ExtractedDependency(
            dependency_type="calls",
            target_symbol="calc",
            confidence=1.5,
            line_number=1,
        )


def test_extract_inheritance_and_decorators():
    extractor = PythonDependencyExtractor()
    code = """
@dataclass
class Dog(Animal, Serializable):
    @property
    def name(self) -> str:
        return self._name
"""
    deps = extractor.extract_from_source(code)

    types = [d.dependency_type for d in deps]
    assert "inherits" in types
    assert "decorates" in types
    assert "uses_type" in types

    inherits_targets = [d.target_symbol for d in deps if d.dependency_type == "inherits"]
    assert "Animal" in inherits_targets
    assert "Serializable" in inherits_targets

    decorates_targets = [d.target_symbol for d in deps if d.dependency_type == "decorates"]
    assert "dataclass" in decorates_targets
    assert "property" in decorates_targets

    type_targets = [d.target_symbol for d in deps if d.dependency_type == "uses_type"]
    assert "str" in type_targets


def test_extract_function_calls():
    extractor = PythonDependencyExtractor()
    code = """
def process(data: Payload) -> Result:
    logger.info("processing")
    res = compute(data)
    self.save(res)
    return res
"""
    deps = extractor.extract_from_source(code)

    calls = [d for d in deps if d.dependency_type == "calls"]
    call_targets = {c.target_symbol: c for c in calls}

    assert "compute" in call_targets
    assert call_targets["compute"].confidence == 0.95

    assert "self.save" in call_targets
    assert call_targets["self.save"].confidence == 0.85

    assert "logger.info" in call_targets
    assert call_targets["logger.info"].confidence == 0.60


def test_resolve_dependencies_external_and_local():
    extractor = PythonDependencyExtractor()

    # Index setup
    index = RepositorySymbolIndex()
    worker_sym = _make_symbol("Worker", "class Worker:\n    def execute(self): pass")
    index.register_file_symbols("src/pkg/worker.py", [worker_sym])

    # Source code that calls external json.dumps and local Worker.execute
    code = """
def run():
    json.dumps({'k': 1})
    Worker.execute()
    unknown_func()
"""
    raw_deps = extractor.extract_from_source(code)

    imports = [
        ImportStatement(
            raw_statement="import json",
            module="json",
            imported_symbols=["json"],
            kind="stdlib",
            line=1,
        ),
        ImportStatement(
            raw_statement="from pkg.worker import Worker",
            module="pkg.worker",
            imported_symbols=["Worker"],
            kind="local",
            line=2,
        ),
    ]

    resolved = extractor.resolve_dependencies(
        dependencies=raw_deps,
        imports=imports,
        symbol_index=index,
        current_file_path="src/pkg/runner.py",
    )

    dep_map = {d.target_symbol: d for d in resolved}

    # json.dumps should be resolved as external
    assert "json.dumps" in dep_map
    assert dep_map["json.dumps"].resolution_status == "external"

    # Worker.execute should be resolved to pkg.worker.Worker.execute
    assert "pkg.worker.Worker.execute" in dep_map
    assert dep_map["pkg.worker.Worker.execute"].resolution_status == "resolved"
    assert dep_map["pkg.worker.Worker.execute"].target_brick_id == "src/pkg/worker.py:pkg.worker.Worker"

    # unknown_func remains unresolved
    assert "unknown_func" in dep_map
    assert dep_map["unknown_func"].resolution_status == "unresolved"

