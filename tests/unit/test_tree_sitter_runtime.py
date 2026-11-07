"""Unit tests for Tree-sitter runtime and Python grammar loader."""

from __future__ import annotations

import pytest

from brickforge.parsers.tree_sitter_runtime import TreeSitterRuntime


class TestTreeSitterRuntime:
    """Tests for TreeSitterRuntime loading and parser management."""

    @pytest.fixture
    def runtime(self) -> TreeSitterRuntime:
        return TreeSitterRuntime()

    def test_python_grammar_loaded(self, runtime: TreeSitterRuntime):
        assert runtime.is_language_available("python") is True
        lang = runtime.get_language("python")
        assert lang is not None

    def test_unregistered_language_raises(self, runtime: TreeSitterRuntime):
        assert runtime.is_language_available("unregistered_xyz") is False
        with pytest.raises(ValueError, match="Unsupported or unregistered"):
            runtime.get_language("unregistered_xyz")

    def test_create_parser_and_parse(self, runtime: TreeSitterRuntime):
        code = "def greet(name: str) -> str:\n    return f'Hello, {name}'\n"
        tree = runtime.parse(code, lang_name="python")

        assert tree.root_node.type == "module"
        assert len(tree.root_node.children) >= 1

        fn_node = tree.root_node.children[0]
        assert fn_node.type == "function_definition"

    def test_collect_error_nodes_on_syntax_error(self, runtime: TreeSitterRuntime):
        bad_code = "def broken(:\n    pass\n"
        tree = runtime.parse(bad_code, lang_name="python")

        errors = runtime.collect_error_nodes(tree.root_node)
        assert len(errors) > 0
        assert any(e.type in ("ERROR", "MISSING") or e.is_missing for e in errors)

    def test_no_errors_on_clean_code(self, runtime: TreeSitterRuntime):
        clean_code = "class Calculator:\n    def add(self, a, b):\n        return a + b\n"
        tree = runtime.parse(clean_code, lang_name="python")

        errors = runtime.collect_error_nodes(tree.root_node)
        assert len(errors) == 0

