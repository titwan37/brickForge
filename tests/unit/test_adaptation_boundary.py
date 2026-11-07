"""Unit tests for optional language adaptation boundary and experimental transpilation gates."""

import pytest

from brickforge.composition.adaptation import (
    CrossLanguageAdaptationRegistry,
    MockCrossLanguageAdapter,
)


def test_cross_language_adapter_enforces_review_gate():
    adapter = MockCrossLanguageAdapter(source_lang="python", target_lang="typescript")

    assert adapter.source_language == "python"
    assert adapter.target_language == "typescript"

    python_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = adapter.adapt(python_code)

    # Transpilation must be explicitly marked experimental
    assert res.status == "experimental"

    # Human review must strictly be required
    assert res.requires_human_review is True

    # Check disclaimer and header warnings
    assert "experimental" in res.disclaimer.lower()
    assert "[EXPERIMENTAL TRANSPILATION" in res.adapted_code
    assert "REVIEW REQUIRED" in res.adapted_code


def test_adaptation_registry():
    registry = CrossLanguageAdaptationRegistry()
    adapter = MockCrossLanguageAdapter("python", "rust")
    registry.register(adapter)

    assert registry.is_supported("python", "rust")
    assert not registry.is_supported("python", "go")

    fetched = registry.get_adapter("PYTHON", "RUST")
    assert fetched is not None
    assert fetched.source_language == "python"
    assert fetched.target_language == "rust"

    assert registry.get_adapter("python", "go") is None

