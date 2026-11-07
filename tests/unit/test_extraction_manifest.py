"""Unit tests for extraction manifest and provenance report generation."""

import json
import pytest

from brickforge.extraction.manifest import ExtractionManifest, ManifestBrickItem, ManifestGenerator


def test_manifest_generation():
    generator = ManifestGenerator()

    bricks = [
        {
            "id": "brick_main",
            "symbol_name": "process_order",
            "qualified_name": "orders.process_order",
            "kind": "function",
            "relative_path": "src/orders/service.py",
            "source_hash": "hash_proc",
        },
        {
            "id": "brick_helper",
            "symbol_name": "validate_order",
            "qualified_name": "orders.validate_order",
            "kind": "function",
            "relative_path": "src/orders/validation.py",
            "source_hash": "hash_val",
        },
    ]

    transformations = [
        {
            "line_number": 2,
            "original_statement": "from orders.validation import validate_order",
            "rewritten_statement": None,
            "reason": "symbols_bundled_locally",
        }
    ]

    manifest = generator.generate(
        target_brick_id="brick_main",
        bricks=bricks,
        import_headers=["import json"],
        transformations=transformations,
        unresolved_dependencies=["logger.debug"],
        external_packages=["pydantic"],
    )

    assert manifest.target_brick_id == "brick_main"
    assert len(manifest.selected_bricks) == 2

    # Check target flag
    target_item = next(b for b in manifest.selected_bricks if b.is_target)
    assert target_item.brick_id == "brick_main"

    helper_item = next(b for b in manifest.selected_bricks if not b.is_target)
    assert helper_item.brick_id == "brick_helper"

    # Check files and hashes
    assert manifest.source_files == ["src/orders/service.py", "src/orders/validation.py"]
    assert manifest.source_hashes["brick_main"] == "hash_proc"
    assert manifest.source_hashes["brick_helper"] == "hash_val"

    # Check transformations and unresolved
    assert len(manifest.transformations) == 1
    assert manifest.unresolved_dependencies == ["logger.debug"]
    assert manifest.external_packages == ["pydantic"]


def test_manifest_serialization_roundtrip():
    generator = ManifestGenerator()
    manifest = generator.generate(
        target_brick_id="b1",
        bricks=[
            {
                "id": "b1",
                "symbol_name": "fn",
                "qualified_name": "mod.fn",
                "kind": "function",
                "file_path": "f.py",
                "source_hash": "h1",
            }
        ],
        import_headers=["import os"],
    )

    json_str = manifest.to_json()
    assert "manifest_id" in json_str

    restored = ExtractionManifest.from_dict(json.loads(json_str))
    assert restored.manifest_id == manifest.manifest_id
    assert restored.target_brick_id == "b1"
    assert restored.imports == ["import os"]
    assert len(restored.selected_bricks) == 1
    assert restored.selected_bricks[0].symbol_name == "fn"

