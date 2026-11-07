"""Tree-sitter runtime and grammar loading for BrickForge."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Union

import tree_sitter

logger = logging.getLogger(__name__)


class TreeSitterRuntime:
    """Manages Tree-sitter language grammars, parser instances, and error nodes."""

    def __init__(self) -> None:
        self._languages: Dict[str, tree_sitter.Language] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        """Register known built-in grammar modules."""
        try:
            import tree_sitter_python

            self.register_language("python", tree_sitter_python.language())
        except ImportError:
            logger.warning("tree_sitter_python module is not installed.")

    def register_language(self, name: str, language_capsule: object) -> None:
        """Register a Tree-sitter language by name."""
        try:
            if isinstance(language_capsule, tree_sitter.Language):
                self._languages[name.lower()] = language_capsule
            else:
                self._languages[name.lower()] = tree_sitter.Language(language_capsule)
        except Exception as e:
            raise RuntimeError(f"Failed to load Tree-sitter grammar for '{name}': {e}") from e

    def get_language(self, name: str) -> tree_sitter.Language:
        """Retrieve a registered Tree-sitter Language."""
        norm_name = name.lower()
        if norm_name not in self._languages:
            raise ValueError(
                f"Unsupported or unregistered Tree-sitter language '{name}'. "
                f"Available languages: {sorted(self._languages.keys())}"
            )
        return self._languages[norm_name]

    def is_language_available(self, name: str) -> bool:
        """Check if a grammar is loaded and ready for parsing."""
        return name.lower() in self._languages

    def create_parser(self, lang_name: str = "python") -> tree_sitter.Parser:
        """Create a new Tree-sitter Parser configured with the given language."""
        lang = self.get_language(lang_name)
        try:
            return tree_sitter.Parser(lang)
        except TypeError:
            # Fallback for older tree-sitter API variations
            parser = tree_sitter.Parser()
            parser.language = lang
            return parser

    def parse(self, source_code: Union[str, bytes], lang_name: str = "python") -> tree_sitter.Tree:
        """Parse source code with the specified language grammar."""
        parser = self.create_parser(lang_name)
        code_bytes = source_code.encode("utf-8") if isinstance(source_code, str) else source_code
        return parser.parse(code_bytes)

    @staticmethod
    def collect_error_nodes(root_node: tree_sitter.Node) -> List[tree_sitter.Node]:
        """Collect all ERROR and MISSING syntax nodes within a parsed tree."""
        errors: List[tree_sitter.Node] = []

        def _traverse(node: tree_sitter.Node) -> None:
            if node.type in ("ERROR", "MISSING") or node.is_missing:
                errors.append(node)
            for child in node.children:
                _traverse(child)

        _traverse(root_node)
        return errors

