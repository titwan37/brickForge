"""Static repository symbol index and import resolution for Python codebases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from brickforge.analysis.imports import ImportStatement
from brickforge.parsers.base import ExtractedSymbol


@dataclass(frozen=True)
class SymbolLocation:
    """Location and contract identity of an indexed symbol."""

    relative_path: str
    symbol_name: str
    qualified_name: str
    kind: str
    start_line: int
    end_line: int


class RepositorySymbolIndex:
    """In-memory index of symbols across a repository enabling static cross-file resolution."""

    def __init__(self) -> None:
        # module_name -> {symbol_name: SymbolLocation}
        self._module_symbols: Dict[str, Dict[str, SymbolLocation]] = {}
        # relative_path -> module_name
        self._file_to_module: Dict[str, str] = {}
        # module_name -> relative_path
        self._module_to_file: Dict[str, str] = {}
        # all qualified_names -> SymbolLocation
        self._qualified_index: Dict[str, SymbolLocation] = {}

    def path_to_module_name(self, relative_path: Union[str, Path]) -> str:
        """Convert a relative file path to a Python dotted module path."""
        norm = str(relative_path).replace("\\", "/").strip().lstrip("/")
        p = Path(norm)

        # Strip common src/ directory prefix if present
        parts = list(p.parts)
        if parts and parts[0] in ("src", "lib"):
            parts = parts[1:]

        if not parts:
            return ""

        # Handle __init__.py
        if parts[-1].lower() in ("__init__.py", "__init__.pyi"):
            parts = parts[:-1]
        else:
            # Strip file extension
            parts[-1] = Path(parts[-1]).stem

        return ".".join(parts)

    def register_file_symbols(
        self,
        relative_path: Union[str, Path],
        symbols: Sequence[ExtractedSymbol],
    ) -> str:
        """Register all symbols extracted from a specific file.

        Returns:
            The resolved module name for the file.
        """
        norm_path = str(relative_path).replace("\\", "/").strip().lstrip("/")
        module_name = self.path_to_module_name(norm_path)

        self._file_to_module[norm_path] = module_name
        self._module_to_file[module_name] = norm_path

        if module_name not in self._module_symbols:
            self._module_symbols[module_name] = {}

        for sym in symbols:
            loc = SymbolLocation(
                relative_path=norm_path,
                symbol_name=sym.symbol_name,
                qualified_name=f"{module_name}.{sym.qualified_name}" if module_name else sym.qualified_name,
                kind=sym.kind,
                start_line=sym.start_line,
                end_line=sym.end_line,
            )
            # Index by top-level or method name in the module
            self._module_symbols[module_name][sym.symbol_name] = loc
            self._qualified_index[loc.qualified_name] = loc
            # Also index by relative qualified name within module
            self._qualified_index[f"{module_name}.{sym.symbol_name}"] = loc

        return module_name

    def lookup_symbol_in_module(self, module_name: str, symbol_name: str) -> Optional[SymbolLocation]:
        """Look up a symbol inside a known module."""
        return self._module_symbols.get(module_name, {}).get(symbol_name)

    def resolve_relative_module(self, current_module: str, relative_level: int, target_suffix: str = "") -> str:
        """Resolve a relative import module string (e.g. level=1, suffix='models')."""
        parts = current_module.split(".") if current_module else []
        if relative_level > len(parts):
            base_parts: List[str] = []
        else:
            base_parts = parts[: len(parts) - (relative_level - 1)]

        # Drop the current module itself if level >= 1
        if relative_level >= 1 and base_parts:
            base_parts = base_parts[:-1]

        if target_suffix:
            base_parts.append(target_suffix)

        return ".".join(base_parts)

    def resolve_import_targets(
        self,
        current_file_path: Union[str, Path],
        import_stmt: ImportStatement,
    ) -> Dict[str, Optional[SymbolLocation]]:
        """Statically resolve symbols imported by an ImportStatement to catalog locations."""
        norm_file = str(current_file_path).replace("\\", "/").strip().lstrip("/")
        current_module = self._file_to_module.get(norm_file, self.path_to_module_name(norm_file))

        resolved: Dict[str, Optional[SymbolLocation]] = {}

        if import_stmt.is_relative:
            target_module = self.resolve_relative_module(
                current_module,
                import_stmt.relative_level,
                import_stmt.module,
            )
        else:
            target_module = import_stmt.module

        for sym_name in import_stmt.imported_symbols:
            # Check if target is a symbol inside target_module
            loc = self.lookup_symbol_in_module(target_module, sym_name)
            if loc:
                resolved[sym_name] = loc
                continue

            # Check if target_module.sym_name is itself a module or package
            submodule = f"{target_module}.{sym_name}" if target_module else sym_name
            if submodule in self._module_to_file:
                resolved[sym_name] = SymbolLocation(
                    relative_path=self._module_to_file[submodule],
                    symbol_name=sym_name,
                    qualified_name=submodule,
                    kind="module",
                    start_line=1,
                    end_line=1,
                )
            else:
                # Check if it is a package prefix for any registered modules
                prefix = f"{submodule}."
                matching_mod = next((m for m in self._module_to_file if m.startswith(prefix)), None)
                if matching_mod:
                    pkg_path = str(Path(self._module_to_file[matching_mod]).parent).replace("\\", "/")
                    resolved[sym_name] = SymbolLocation(
                        relative_path=pkg_path,
                        symbol_name=sym_name,
                        qualified_name=submodule,
                        kind="module",
                        start_line=1,
                        end_line=1,
                    )
                else:
                    resolved[sym_name] = None

        return resolved
