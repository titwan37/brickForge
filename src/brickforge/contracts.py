"""Brick contract representation exposing interface metadata without full source body."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from brickforge.analysis.dependencies import ExtractedDependency
from brickforge.parsers.base import ExtractedSymbol


@dataclass(frozen=True)
class SourceLocation:
    """Exact source coordinates of a code brick."""

    file_path: str
    start_line: int
    end_line: int
    start_byte: int = 0
    end_byte: int = 0


@dataclass(frozen=True)
class PackageRequirement:
    """External dependency requirement needed to execute or import a brick."""

    ecosystem: str
    package_name: str
    version_constraint: Optional[str] = None
    import_statement: str = ""


@dataclass(frozen=True)
class DependencySummary:
    """Aggregated summary of incoming/outgoing dependencies for a brick."""

    calls: List[str] = field(default_factory=list)
    inherits: List[str] = field(default_factory=list)
    uses_types: List[str] = field(default_factory=list)
    decorates: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    external_count: int = 0
    resolved_count: int = 0


@dataclass
class BrickContract:
    """Complete interface contract and metadata for a reusable software brick.

    Exposes symbol signature, documentation, typing, location, packages,
    and dependency edges without requiring full source code body.
    """

    symbol_name: str
    qualified_name: str
    kind: str
    language: str
    signature: str
    docstring: Optional[str]
    decorators: List[str]
    source_location: SourceLocation
    imports: List[str] = field(default_factory=list)
    package_requirements: List[PackageRequirement] = field(default_factory=list)
    dependency_summary: DependencySummary = field(default_factory=DependencySummary)
    portability_score: float = 0.5
    tags: List[str] = field(default_factory=list)
    brick_id: Optional[str] = None
    content_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert contract to a structured dictionary."""
        return {
            "brick_id": self.brick_id,
            "symbol_name": self.symbol_name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "language": self.language,
            "signature": self.signature,
            "docstring": self.docstring,
            "decorators": list(self.decorators),
            "source_location": asdict(self.source_location),
            "imports": list(self.imports),
            "package_requirements": [asdict(p) for p in self.package_requirements],
            "dependency_summary": asdict(self.dependency_summary),
            "portability_score": self.portability_score,
            "tags": list(self.tags),
            "content_hash": self.content_hash,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize contract to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BrickContract:
        """Reconstruct a BrickContract from dictionary format."""
        loc_data = data.get("source_location", {})
        location = SourceLocation(
            file_path=loc_data.get("file_path", ""),
            start_line=loc_data.get("start_line", 1),
            end_line=loc_data.get("end_line", 1),
            start_byte=loc_data.get("start_byte", 0),
            end_byte=loc_data.get("end_byte", 0),
        )

        pkgs = [
            PackageRequirement(
                ecosystem=p.get("ecosystem", "unknown"),
                package_name=p.get("package_name", ""),
                version_constraint=p.get("version_constraint"),
                import_statement=p.get("import_statement", ""),
            )
            for p in data.get("package_requirements", [])
        ]

        dep_data = data.get("dependency_summary", {})
        dep_summary = DependencySummary(
            calls=dep_data.get("calls", []),
            inherits=dep_data.get("inherits", []),
            uses_types=dep_data.get("uses_types", []),
            decorates=dep_data.get("decorates", []),
            unresolved=dep_data.get("unresolved", []),
            external_count=dep_data.get("external_count", 0),
            resolved_count=dep_data.get("resolved_count", 0),
        )

        return cls(
            symbol_name=data.get("symbol_name", ""),
            qualified_name=data.get("qualified_name", ""),
            kind=data.get("kind", "function"),
            language=data.get("language", "python"),
            signature=data.get("signature", ""),
            docstring=data.get("docstring"),
            decorators=data.get("decorators", []),
            source_location=location,
            imports=data.get("imports", []),
            package_requirements=pkgs,
            dependency_summary=dep_summary,
            portability_score=float(data.get("portability_score", 0.5)),
            tags=data.get("tags", []),
            brick_id=data.get("brick_id"),
            content_hash=data.get("content_hash"),
        )

    @classmethod
    def from_extracted_symbol(
        cls,
        symbol: ExtractedSymbol,
        file_path: str = "",
        brick_id: Optional[str] = None,
        imports: Optional[Sequence[str]] = None,
        dependencies: Optional[Sequence[ExtractedDependency]] = None,
        packages: Optional[Sequence[PackageRequirement]] = None,
        portability_score: float = 0.5,
        tags: Optional[Sequence[str]] = None,
    ) -> BrickContract:
        """Create contract from AST symbol and extracted dependencies."""
        location = SourceLocation(
            file_path=file_path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            start_byte=symbol.start_byte,
            end_byte=symbol.end_byte,
        )

        calls: List[str] = []
        inherits: List[str] = list(symbol.bases)
        uses_types: List[str] = []
        decorates: List[str] = list(symbol.decorators)
        unresolved: List[str] = []
        ext_count = 0
        res_count = 0

        if dependencies:
            for d in dependencies:
                if d.resolution_status == "external":
                    ext_count += 1
                elif d.resolution_status == "resolved":
                    res_count += 1
                elif d.resolution_status == "unresolved":
                    unresolved.append(d.target_symbol)

                if d.dependency_type == "calls":
                    calls.append(d.target_symbol)
                elif d.dependency_type == "inherits" and d.target_symbol not in inherits:
                    inherits.append(d.target_symbol)
                elif d.dependency_type == "uses_type":
                    uses_types.append(d.target_symbol)
                elif d.dependency_type == "decorates" and d.target_symbol not in decorates:
                    decorates.append(d.target_symbol)

        dep_summary = DependencySummary(
            calls=calls,
            inherits=inherits,
            uses_types=uses_types,
            decorates=decorates,
            unresolved=unresolved,
            external_count=ext_count,
            resolved_count=res_count,
        )

        return cls(
            symbol_name=symbol.symbol_name,
            qualified_name=symbol.qualified_name,
            kind=symbol.kind,
            language=symbol.language,
            signature=symbol.signature,
            docstring=symbol.docstring,
            decorators=decorates,
            source_location=location,
            imports=list(imports or []),
            package_requirements=list(packages or []),
            dependency_summary=dep_summary,
            portability_score=portability_score,
            tags=list(tags or []),
            brick_id=brick_id,
            content_hash=symbol.source_hash,
        )

    @classmethod
    def from_database_records(
        cls,
        brick_row: Dict[str, Any],
        file_path: str = "",
        dependencies: Optional[List[Dict[str, Any]]] = None,
        packages: Optional[List[Dict[str, Any]]] = None,
    ) -> BrickContract:
        """Create contract from database query row records."""
        tags_raw = brick_row.get("tags", "[]")
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else list(tags_raw or [])

        location = SourceLocation(
            file_path=file_path,
            start_line=brick_row.get("start_line", 1),
            end_line=brick_row.get("end_line", 1),
            start_byte=brick_row.get("start_byte", 0),
            end_byte=brick_row.get("end_byte", 0),
        )

        pkg_reqs: List[PackageRequirement] = []
        if packages:
            for p in packages:
                pkg_reqs.append(
                    PackageRequirement(
                        ecosystem=p.get("ecosystem", "unknown"),
                        package_name=p.get("package_name", ""),
                        version_constraint=p.get("version_constraint"),
                        import_statement=p.get("import_statement", ""),
                    )
                )

        calls: List[str] = []
        inherits: List[str] = []
        uses_types: List[str] = []
        decorates: List[str] = []
        unresolved: List[str] = []
        ext_count = 0
        res_count = 0

        if dependencies:
            for d in dependencies:
                status = d.get("resolution_status", "unresolved")
                dtype = d.get("dependency_type", "")
                target = d.get("unresolved_symbol") or str(d.get("target_row_id") or "")

                if status == "external":
                    ext_count += 1
                elif status == "resolved":
                    res_count += 1
                else:
                    unresolved.append(target)

                if dtype == "calls":
                    calls.append(target)
                elif dtype == "inherits":
                    inherits.append(target)
                elif dtype == "uses_type":
                    uses_types.append(target)
                elif dtype == "decorates":
                    decorates.append(target)

        dep_summary = DependencySummary(
            calls=calls,
            inherits=inherits,
            uses_types=uses_types,
            decorates=decorates,
            unresolved=unresolved,
            external_count=ext_count,
            resolved_count=res_count,
        )

        return cls(
            symbol_name=brick_row.get("symbol_name", ""),
            qualified_name=brick_row.get("qualified_name", ""),
            kind=brick_row.get("kind", "function"),
            language=brick_row.get("language", "python"),
            signature=brick_row.get("signature", ""),
            docstring=brick_row.get("docstring"),
            decorators=decorates,
            source_location=location,
            package_requirements=pkg_reqs,
            dependency_summary=dep_summary,
            portability_score=float(brick_row.get("portability_score", 0.5)),
            tags=tags,
            brick_id=brick_row.get("id"),
            content_hash=brick_row.get("source_hash"),
        )

