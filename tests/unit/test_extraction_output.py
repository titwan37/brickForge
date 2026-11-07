"""Unit tests for extraction output modes (source bundle, contract-only, JSON metadata)."""

import pytest

from brickforge.contracts import BrickContract, SourceLocation
from brickforge.extraction.bundler import ExtractionBundle
from brickforge.extraction.output import ExtractionFormatter, ExtractionOutputMode


@pytest.fixture
def mock_bundle_and_contract():
    bundle = ExtractionBundle(
        target_brick_id="brick_test_1",
        target_symbol_name="encrypt_aes",
        bundled_source="import os\n\ndef encrypt_aes(data):\n    return data\n",
        import_headers=["import os"],
        included_brick_ids=["brick_test_1"],
        external_packages=["cryptography"],
        unresolved_dependencies=[],
    )

    contract = BrickContract(
        symbol_name="encrypt_aes",
        qualified_name="crypto.encrypt_aes",
        kind="function",
        language="python",
        signature="def encrypt_aes(data: bytes) -> bytes:",
        docstring="Encrypt raw bytes using AES-GCM.",
        decorators=[],
        source_location=SourceLocation("src/crypto.py", 1, 10),
        brick_id="brick_test_1",
    )

    return bundle, contract


def test_contract_only_mode_is_body_free(mock_bundle_and_contract):
    bundle, contract = mock_bundle_and_contract
    resp = ExtractionFormatter.format(
        bundle=bundle,
        contract=contract,
        mode=ExtractionOutputMode.CONTRACT_ONLY,
    )

    assert resp.mode == ExtractionOutputMode.CONTRACT_ONLY
    assert resp.content_type == "application/json"
    assert isinstance(resp.content, dict)
    assert resp.content["symbol_name"] == "encrypt_aes"
    assert resp.content["signature"] == "def encrypt_aes(data: bytes) -> bytes:"
    assert "source_code" not in resp.content


def test_source_bundle_mode(mock_bundle_and_contract):
    bundle, contract = mock_bundle_and_contract
    resp = ExtractionFormatter.format(
        bundle=bundle,
        contract=contract,
        mode=ExtractionOutputMode.SOURCE_BUNDLE,
    )

    assert resp.mode == ExtractionOutputMode.SOURCE_BUNDLE
    assert resp.content_type == "text/x-python"
    assert isinstance(resp.content, str)
    assert "def encrypt_aes" in resp.content
    assert "import os" in resp.content


def test_json_metadata_mode_source_inclusion(mock_bundle_and_contract):
    bundle, contract = mock_bundle_and_contract

    # 1. Default: include_source = False
    resp_default = ExtractionFormatter.format(
        bundle=bundle,
        contract=contract,
        mode=ExtractionOutputMode.JSON_METADATA,
        include_source=False,
    )
    assert resp_default.content["source_bundle"] is None
    assert resp_default.content["contract"]["symbol_name"] == "encrypt_aes"

    # 2. Explicit: include_source = True
    resp_with_source = ExtractionFormatter.format(
        bundle=bundle,
        contract=contract,
        mode=ExtractionOutputMode.JSON_METADATA,
        include_source=True,
    )
    assert resp_with_source.content["source_bundle"] is not None
    assert "def encrypt_aes" in resp_with_source.content["source_bundle"]


def test_unsupported_mode_raises(mock_bundle_and_contract):
    bundle, contract = mock_bundle_and_contract
    with pytest.raises(ValueError, match="Unsupported output mode"):
        ExtractionFormatter.format(
            bundle=bundle,
            contract=contract,
            mode="invalid_mode",
        )

