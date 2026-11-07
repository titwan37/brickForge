"""Explicit extension point and boundary for cross-language code adaptation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AdaptationResult:
    """Outcome of a language adaptation or transpilation attempt."""

    source_language: str
    target_language: str
    adapted_code: str
    status: str = "experimental"
    requires_human_review: bool = True
    disclaimer: str = (
        "WARNING: Cross-language transpilation is experimental. "
        "Generated code requires thorough manual review and compiler/test validation "
        "before production use."
    )
    notes: List[str] = field(default_factory=list)


class BaseLanguageAdapterExtension(ABC):
    """Abstract extension point for converting code between distinct programming languages."""

    @property
    @abstractmethod
    def source_language(self) -> str:
        """Source language name (e.g. 'python')."""

    @property
    @abstractmethod
    def target_language(self) -> str:
        """Target language name (e.g. 'typescript')."""

    @abstractmethod
    def adapt(self, source_code: str, context: Optional[Dict[str, Any]] = None) -> AdaptationResult:
        """Perform experimental cross-language transformation."""


class MockCrossLanguageAdapter(BaseLanguageAdapterExtension):
    """Reference implementation providing experimental translation stubbing."""

    def __init__(self, source_lang: str = "python", target_lang: str = "typescript"):
        self._source_lang = source_lang
        self._target_lang = target_lang

    @property
    def source_language(self) -> str:
        return self._source_lang

    @property
    def target_language(self) -> str:
        return self._target_lang

    def adapt(self, source_code: str, context: Optional[Dict[str, Any]] = None) -> AdaptationResult:
        """Produce an experimental cross-language stub with explicit human review gates."""
        header = (
            f"// [EXPERIMENTAL TRANSPILATION: {self.source_language} -> {self.target_language}]\n"
            f"// REVIEW REQUIRED: This code was translated across language boundaries and is unverified.\n\n"
        )
        # Wrap or stub the source code into target language syntax
        stub_body = f"/* Original {self.source_language} source:\n{source_code}\n*/\nexport function adaptedStub() {{\n    throw new Error('Not implemented');\n}}\n"
        return AdaptationResult(
            source_language=self.source_language,
            target_language=self.target_language,
            adapted_code=header + stub_body,
            status="experimental",
            requires_human_review=True,
            notes=["Transpiled across language boundary; manual type alignment required."],
        )


class CrossLanguageAdaptationRegistry:
    """Registry managing available cross-language adaptation adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[Tuple[str, str], BaseLanguageAdapterExtension] = {}

    def register(self, adapter: BaseLanguageAdapterExtension) -> None:
        key = (adapter.source_language.lower(), adapter.target_language.lower())
        self._adapters[key] = adapter

    def get_adapter(self, source_language: str, target_language: str) -> Optional[BaseLanguageAdapterExtension]:
        key = (source_language.lower(), target_language.lower())
        return self._adapters.get(key)

    def is_supported(self, source_language: str, target_language: str) -> bool:
        key = (source_language.lower(), target_language.lower())
        return key in self._adapters

