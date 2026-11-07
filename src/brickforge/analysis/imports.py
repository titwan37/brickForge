"""Import and external package reference extraction for Python source code."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Union


# Fallback set if sys.stdlib_module_names is not available
DEFAULT_STDLIB_MODULES = getattr(
    sys,
    "stdlib_module_names",
    frozenset(
        {
            "abc", "argparse", "ast", "asyncio", "base64", "collections", "contextlib",
            "csv", "dataclasses", "datetime", "decimal", "functools", "hashlib",
            "http", "io", "itertools", "json", "logging", "math", "os", "pathlib",
            "pickle", "re", "shutil", "sqlite3", "string", "subprocess", "sys",
            "tempfile", "time", "typing", "unittest", "urllib", "uuid", "warnings",
        }
    ),
)


@dataclass
class ImportStatement:
    """Represents an extracted Python import declaration."""

    raw_statement: str
    module: str
    imported_symbols: List[str] = field(default_factory=list)
    alias_mapping: Dict[str, str] = field(default_factory=dict)
    is_relative: bool = False
    relative_level: int = 0
    kind: str = "unknown"  # 'stdlib', 'third_party', 'local'
    line: int = 1


class PythonImportAnalyzer:
    """Extracts and classifies Python import statements."""

    def __init__(self, known_local_modules: Optional[Set[str]] = None):
        self.known_local_modules = set(known_local_modules or ())

    def extract_imports(self, source_code: Union[str, bytes]) -> List[ImportStatement]:
        """Extract all import declarations from source code."""
        if isinstance(source_code, bytes):
            try:
                code_str = source_code.decode("utf-8")
            except UnicodeDecodeError:
                code_str = source_code.decode("latin-1", errors="replace")
        else:
            code_str = source_code

        try:
            tree = ast.parse(code_str)
        except SyntaxError:
            return []

        imports: List[ImportStatement] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    kind = self._classify_module(root_pkg, is_relative=False)
                    raw = f"import {alias.name}"
                    alias_map = {}
                    if alias.asname:
                        raw += f" as {alias.asname}"
                        alias_map[alias.asname] = alias.name

                    imports.append(
                        ImportStatement(
                            raw_statement=raw,
                            module=alias.name,
                            imported_symbols=[alias.name],
                            alias_mapping=alias_map,
                            is_relative=False,
                            relative_level=0,
                            kind=kind,
                            line=node.lineno,
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                is_rel = node.level > 0
                mod_name = node.module or ""
                root_pkg = mod_name.split(".")[0] if mod_name else ""

                kind = self._classify_module(root_pkg, is_relative=is_rel)
                symbols: List[str] = []
                alias_map = {}

                parts = []
                for alias in node.names:
                    symbols.append(alias.name)
                    if alias.asname:
                        parts.append(f"{alias.name} as {alias.asname}")
                        alias_map[alias.asname] = alias.name
                    else:
                        parts.append(alias.name)

                dots = "." * node.level
                raw = f"from {dots}{mod_name} import {', '.join(parts)}"

                imports.append(
                    ImportStatement(
                        raw_statement=raw,
                        module=mod_name,
                        imported_symbols=symbols,
                        alias_mapping=alias_map,
                        is_relative=is_rel,
                        relative_level=node.level,
                        kind=kind,
                        line=node.lineno,
                    )
                )

        imports.sort(key=lambda i: i.line)
        return imports

    def get_external_packages(self, imports: Sequence[ImportStatement]) -> List[str]:
        """Return unique third-party package names required by the imports."""
        packages: Set[str] = set()
        for imp in imports:
            if imp.kind == "third_party" and imp.module:
                root = imp.module.split(".")[0]
                packages.add(root)
        return sorted(packages)

    def _classify_module(self, root_module: str, is_relative: bool) -> str:
        if is_relative or not root_module:
            return "local"
        if root_module in self.known_local_modules:
            return "local"
        if root_module in DEFAULT_STDLIB_MODULES:
            return "stdlib"
        return "third_party"

