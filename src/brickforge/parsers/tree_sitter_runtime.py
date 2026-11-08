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
        # 1. Python
        try:
            import tree_sitter_python
            self.register_language("python", tree_sitter_python.language())
        except ImportError:
            logger.debug("tree_sitter_python module is not installed.")

        # 2. C#
        try:
            import tree_sitter_c_sharp
            self.register_language("csharp", tree_sitter_c_sharp.language())
            self.register_language("c_sharp", tree_sitter_c_sharp.language())
            self.register_language("cs", tree_sitter_c_sharp.language())
        except ImportError:
            logger.debug("tree_sitter_c_sharp module is not installed.")

        # 3. TypeScript & TSX
        try:
            import tree_sitter_typescript
            self.register_language("typescript", tree_sitter_typescript.language_typescript())
            self.register_language("ts", tree_sitter_typescript.language_typescript())
            self.register_language("tsx", tree_sitter_typescript.language_tsx())
            self.register_language("typescript-react", tree_sitter_typescript.language_tsx())
        except ImportError:
            logger.debug("tree_sitter_typescript module is not installed.")

        # 4. JavaScript
        try:
            import tree_sitter_javascript
            self.register_language("javascript", tree_sitter_javascript.language())
            self.register_language("js", tree_sitter_javascript.language())
            self.register_language("jsx", tree_sitter_javascript.language())
        except ImportError:
            logger.debug("tree_sitter_javascript module is not installed.")

        # 5. C++
        try:
            import tree_sitter_cpp
            self.register_language("cpp", tree_sitter_cpp.language())
            self.register_language("c++", tree_sitter_cpp.language())
        except ImportError:
            logger.debug("tree_sitter_cpp module is not installed.")

        # 6. C
        try:
            import tree_sitter_c
            self.register_language("c", tree_sitter_c.language())
        except ImportError:
            logger.debug("tree_sitter_c module is not installed.")

        # 7. Go
        try:
            import tree_sitter_go
            self.register_language("go", tree_sitter_go.language())
        except ImportError:
            logger.debug("tree_sitter_go module is not installed.")

        # 8. Java
        try:
            import tree_sitter_java
            self.register_language("java", tree_sitter_java.language())
        except ImportError:
            logger.debug("tree_sitter_java module is not installed.")

        # 9. Rust
        try:
            import tree_sitter_rust
            self.register_language("rust", tree_sitter_rust.language())
        except ImportError:
            logger.debug("tree_sitter_rust module is not installed.")

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

