"""Extraction output mode formatting supporting source bundle, contract-only, and JSON metadata."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Union

from brickforge.contracts import BrickContract
from brickforge.extraction.bundler import ExtractionBundle
from brickforge.extraction.manifest import ExtractionManifest


class ExtractionOutputMode:
    SOURCE_BUNDLE = "source_bundle"
    CONTRACT_ONLY = "contract_only"
    JSON_METADATA = "json_metadata"


@dataclass
class ExtractionResponse:
    """Standardized output response for brick extraction operations."""

    mode: str
    brick_id: str
    symbol_name: str
    content_type: str
    content: Union[str, Dict[str, Any]]

    def as_text(self) -> str:
        """Render response as a plain text string."""
        if isinstance(self.content, str):
            return self.content
        return json.dumps(self.content, indent=2)

    def as_dict(self) -> Dict[str, Any]:
        """Render response as a dictionary if JSON/dict, otherwise wrap string."""
        if isinstance(self.content, dict):
            return self.content
        return {"source_code": self.content}


class ExtractionFormatter:
    """Formats extraction results into target output representations."""

    @staticmethod
    def format(
        bundle: ExtractionBundle,
        contract: BrickContract,
        manifest: Optional[ExtractionManifest] = None,
        mode: str = ExtractionOutputMode.CONTRACT_ONLY,
        include_source: bool = False,
    ) -> ExtractionResponse:
        """Format extraction outputs into the specified mode.

        By default, contract responses are strictly body-free, and JSON metadata
        only includes raw source code when include_source is explicitly True.
        """
        brick_id = bundle.target_brick_id
        symbol_name = bundle.target_symbol_name

        if mode == ExtractionOutputMode.SOURCE_BUNDLE:
            return ExtractionResponse(
                mode=mode,
                brick_id=brick_id,
                symbol_name=symbol_name,
                content_type="text/x-python",
                content=bundle.bundled_source,
            )

        elif mode == ExtractionOutputMode.CONTRACT_ONLY:
            # Strictly body-free contract representation
            contract_dict = contract.to_dict()
            contract_dict.pop("source_code", None)
            return ExtractionResponse(
                mode=mode,
                brick_id=brick_id,
                symbol_name=symbol_name,
                content_type="application/json",
                content=contract_dict,
            )

        elif mode == ExtractionOutputMode.JSON_METADATA:
            metadata: Dict[str, Any] = {
                "brick_id": brick_id,
                "symbol_name": symbol_name,
                "contract": contract.to_dict(),
                "manifest": manifest.to_dict() if manifest else None,
                "external_packages": bundle.external_packages,
                "unresolved_dependencies": bundle.unresolved_dependencies,
                "omitted_dependencies": bundle.omitted_dependencies,
            }
            # Only include full source code when explicitly requested
            if include_source:
                metadata["source_bundle"] = bundle.bundled_source
            else:
                metadata["source_bundle"] = None

            return ExtractionResponse(
                mode=mode,
                brick_id=brick_id,
                symbol_name=symbol_name,
                content_type="application/json",
                content=metadata,
            )

        else:
            raise ValueError(
                f"Unsupported output mode '{mode}'. "
                f"Supported modes: {[ExtractionOutputMode.SOURCE_BUNDLE, ExtractionOutputMode.CONTRACT_ONLY, ExtractionOutputMode.JSON_METADATA]}"
            )

