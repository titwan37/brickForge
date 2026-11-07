"""Unit tests for repository-specific import normalization and rewriting."""

import pytest

from brickforge.extraction.import_rewriter import ImportRewriter


def test_prefix_remapping():
    rewriter = ImportRewriter(
        prefix_mappings={
            "legacy_repo.backend": "modern_app.core",
        }
    )

    code = """
from legacy_repo.backend.crypto import encrypt_aes
import legacy_repo.backend.utils as utils

def do_work():
    return encrypt_aes()
"""
    res = rewriter.rewrite(code)
    assert res.has_changes
    assert len(res.rewrites) == 2

    assert "from modern_app.core.crypto import encrypt_aes" in res.rewritten_code
    assert "import modern_app.core.utils as utils" in res.rewritten_code

    # Check audit log
    assert any("legacy_repo.backend -> modern_app.core" in r.reason for r in res.rewrites)


def test_bundled_symbol_elimination():
    rewriter = ImportRewriter(
        bundled_symbols={"helper_one", "helper_two"}
    )

    code = """
from .utils import helper_one, helper_two
from .utils import helper_one, remaining_fn

def main():
    pass
"""
    res = rewriter.rewrite(code)
    assert res.has_changes
    assert len(res.rewrites) == 2

    # First import eliminated completely
    assert "from .utils import helper_one, helper_two" not in res.rewritten_code
    # Second import pruned to remaining_fn
    assert "from .utils import remaining_fn" in res.rewritten_code


def test_flatten_relative_imports():
    rewriter = ImportRewriter(flatten_relative=True)

    code = """
from ...config import settings

def init():
    pass
"""
    res = rewriter.rewrite(code)
    assert res.has_changes
    assert "from .config import settings" in res.rewritten_code


def test_unmodified_when_no_rules_match():
    rewriter = ImportRewriter()
    code = "import json\nimport sys\n"
    res = rewriter.rewrite(code)
    assert not res.has_changes
    assert res.rewritten_code == code

