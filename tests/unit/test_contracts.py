"""Unit tests for brick contract representation and metadata serialization."""

import json
import pytest

from brickforge.analysis.dependencies import ExtractedDependency
from brickforge.contracts import (
    BrickContract,
    DependencySummary,
    PackageRequirement,
    SourceLocation,
)
from brickforge.parsers.base import ExtractedSymbol


def test_contract_serialization_roundtrip():
    contract = BrickContract(
        symbol_name="authenticate_user",
        qualified_name="auth.service.authenticate_user",
        kind="function",
        language="python",
        signature="def authenticate_user(token: str) -> UserSession:",
        docstring="Validate auth token and return an active session.",
        decorators=["@cached(ttl=300)"],
        source_location=SourceLocation(
            file_path="src/auth/service.py",
            start_line=15,
            end_line=45,
            start_byte=200,
            end_byte=950,
        ),
        imports=["import jwt", "from datetime import datetime"],
        package_requirements=[
            PackageRequirement(
                ecosystem="pip",
                package_name="pyjwt",
                version_constraint=">=2.0.0",
                import_statement="import jwt",
            )
        ],
        dependency_summary=DependencySummary(
            calls=["jwt.decode", "UserSession"],
            uses_types=["str", "UserSession"],
            decorates=["cached"],
            external_count=1,
            resolved_count=1,
        ),
        portability_score=0.85,
        tags=["auth", "security", "jwt"],
        brick_id="brick_test123",
        content_hash="abc123hash",
    )

    data = contract.to_dict()
    # Contract must NOT expose full source body
    assert "source_code" not in data

    json_str = contract.to_json()
    assert "authenticate_user" in json_str

    restored = BrickContract.from_dict(json.loads(json_str))
    assert restored.symbol_name == contract.symbol_name
    assert restored.signature == contract.signature
    assert restored.source_location.start_line == 15
    assert len(restored.package_requirements) == 1
    assert restored.package_requirements[0].package_name == "pyjwt"
    assert restored.dependency_summary.calls == ["jwt.decode", "UserSession"]
    assert restored.portability_score == 0.85


def test_contract_from_extracted_symbol():
    sym = ExtractedSymbol(
        symbol_name="CryptoManager",
        qualified_name="crypto.CryptoManager",
        kind="class",
        language="python",
        signature="class CryptoManager(BaseManager):",
        signature_hash="sig_hash_1",
        docstring="Handles symmetric encryption.",
        source_code="class CryptoManager(BaseManager):\n    pass",
        source_hash="src_hash_1",
        start_byte=10,
        end_byte=120,
        start_line=2,
        end_line=10,
        bases=["BaseManager"],
        decorators=["@dataclass"],
    )

    deps = [
        ExtractedDependency(
            dependency_type="calls",
            target_symbol="aes_encrypt",
            confidence=0.9,
            line_number=5,
            resolution_status="resolved",
        ),
        ExtractedDependency(
            dependency_type="calls",
            target_symbol="crypto.hazmat.primitives",
            confidence=0.6,
            line_number=6,
            resolution_status="external",
        ),
    ]

    pkgs = [
        PackageRequirement(
            ecosystem="pip",
            package_name="cryptography",
            version_constraint=">=40.0.0",
        )
    ]

    contract = BrickContract.from_extracted_symbol(
        symbol=sym,
        file_path="src/crypto.py",
        brick_id="brick_crypto_1",
        imports=["from cryptography import hazmat"],
        dependencies=deps,
        packages=pkgs,
        portability_score=0.92,
        tags=["crypto", "security"],
    )

    assert contract.symbol_name == "CryptoManager"
    assert contract.kind == "class"
    assert contract.source_location.file_path == "src/crypto.py"
    assert "BaseManager" in contract.dependency_summary.inherits
    assert "@dataclass" in contract.dependency_summary.decorates
    assert contract.dependency_summary.external_count == 1
    assert contract.dependency_summary.resolved_count == 1
    assert contract.package_requirements[0].package_name == "cryptography"


def test_contract_from_database_records():
    brick_row = {
        "id": "brick_db_1",
        "symbol_name": "fetch_data",
        "qualified_name": "api.fetch_data",
        "kind": "function",
        "language": "python",
        "signature": "def fetch_data(url: str):",
        "docstring": "Fetch remote json data.",
        "start_line": 20,
        "end_line": 35,
        "start_byte": 400,
        "end_byte": 750,
        "portability_score": 0.75,
        "tags": '["api", "network"]',
        "source_hash": "hash_xyz",
    }

    dep_rows = [
        {
            "dependency_type": "calls",
            "resolution_status": "external",
            "unresolved_symbol": "requests.get",
            "confidence": 0.95,
        }
    ]

    pkg_rows = [
        {
            "ecosystem": "pip",
            "package_name": "requests",
            "version_constraint": "^2.28.0",
            "import_statement": "import requests",
        }
    ]

    contract = BrickContract.from_database_records(
        brick_row=brick_row,
        file_path="src/api.py",
        dependencies=dep_rows,
        packages=pkg_rows,
    )

    assert contract.brick_id == "brick_db_1"
    assert contract.symbol_name == "fetch_data"
    assert contract.tags == ["api", "network"]
    assert contract.dependency_summary.external_count == 1
    assert contract.package_requirements[0].package_name == "requests"

