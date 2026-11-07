"""Base abstractions and data contracts for language AST adapters."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Union


VALID_SYMBOL_KINDS = {
    "function",
    "method",
    "class",
    "struct",
    "trait",
    "interface",
    "enum",
    "module",
    "property",
    "constant",
    "type_alias",
}


@dataclass
class ParseDiagnostic:
    """Diagnostic message produced during file parsing."""

    severity: str  # 'error', 'warning', 'info'
    message: str
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class ExtractedSymbol:
    """An individual AST symbol (class, function, method, etc.) extracted from source code."""

    symbol_name: str
    qualified_name: str
    kind: str
    language: str
    signature: str
    signature_hash: str
    docstring: Optional[str]
    source_code: str
    source_hash: str
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    is_async: bool = False
    visibility: Optional[str] = None
    parent_name: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in VALID_SYMBOL_KINDS:
            raise ValueError(f"Invalid symbol kind '{self.kind}'. Must be one of {VALID_SYMBOL_KINDS}")
        if not self.signature_hash and self.signature:
            self.signature_hash = hashlib.sha256(self.signature.encode("utf-8")).hexdigest()
        if not self.source_hash and self.source_code:
            self.source_hash = hashlib.sha256(self.source_code.encode("utf-8")).hexdigest()


@dataclass
class ParsedFileResult:
    """Result of parsing an entire source file."""

    language: str
    symbols: List[ExtractedSymbol] = field(default_factory=list)
    parse_status: str = "ok"  # 'ok', 'partial', 'failed', 'unsupported'
    diagnostics: List[ParseDiagnostic] = field(default_factory=list)
    loc: int = 0
    parser_name: str = "native"
    parser_version: str = "1.0"


class BaseLanguageAdapter(ABC):
    """Abstract base class for all language AST adapters."""

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Name of the programming language (e.g., 'python', 'rust')."""

    @property
    @abstractmethod
    def file_extensions(self) -> Sequence[str]:
        """Recognized file extensions (e.g., ('.py', '.pyi'))."""

    def can_handle(self, file_path: Union[str, Path]) -> bool:
        """Check if this adapter supports the given file by extension."""
        ext = Path(file_path).suffix.lower()
        return ext in self.file_extensions

    @abstractmethod
    def parse(
        self,
        source_code: Union[str, bytes],
        file_path: Optional[Union[str, Path]] = None,
    ) -> ParsedFileResult:
        """Parse source code into discrete symbols and diagnostics."""

