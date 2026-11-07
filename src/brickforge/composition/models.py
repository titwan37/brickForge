"""Domain models for code composition requests and generated code proposals."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class TargetEnvironment:
    """Target execution environment for composed code."""

    language: str = "python"
    language_version: str = ">=3.10"
    framework: Optional[str] = None


@dataclass
class CompositionConstraints:
    """Constraints governing the generated composition proposal."""

    max_external_dependencies: int = 5
    disallow_eval_exec: bool = True
    pure_function_preferred: bool = False
    allowed_licenses: List[str] = field(default_factory=lambda: ["MIT", "Apache-2.0", "BSD-3-Clause"])
    custom_rules: List[str] = field(default_factory=list)


@dataclass
class CompositionRequest:
    """Request specification defining target interface, selected bricks, and constraints."""

    request_id: str
    target_environment: TargetEnvironment
    selected_brick_ids: List[str]
    adaptation_instructions: str
    interface_contract: Optional[Dict[str, Any]] = None
    constraints: CompositionConstraints = field(default_factory=CompositionConstraints)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "request_id": self.request_id,
            "target_environment": asdict(self.target_environment),
            "selected_brick_ids": list(self.selected_brick_ids),
            "adaptation_instructions": self.adaptation_instructions,
            "interface_contract": self.interface_contract,
            "constraints": asdict(self.constraints),
            "created_at": self.created_at,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize request to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CompositionRequest:
        """Construct request instance from dictionary."""
        env_data = data.get("target_environment", {})
        env = TargetEnvironment(
            language=env_data.get("language", "python"),
            language_version=env_data.get("language_version", ">=3.10"),
            framework=env_data.get("framework"),
        )
        c_data = data.get("constraints", {})
        constraints = CompositionConstraints(
            max_external_dependencies=c_data.get("max_external_dependencies", 5),
            disallow_eval_exec=bool(c_data.get("disallow_eval_exec", True)),
            pure_function_preferred=bool(c_data.get("pure_function_preferred", False)),
            allowed_licenses=c_data.get("allowed_licenses", ["MIT", "Apache-2.0"]),
            custom_rules=c_data.get("custom_rules", []),
        )
        return cls(
            request_id=data.get("request_id", f"req_{uuid.uuid4().hex[:12]}"),
            target_environment=env,
            selected_brick_ids=data.get("selected_brick_ids", []),
            adaptation_instructions=data.get("adaptation_instructions", ""),
            interface_contract=data.get("interface_contract"),
            constraints=constraints,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class ProposalArtifact:
    """An artifact file produced as part of a composition proposal."""

    artifact_id: str
    file_path: str
    content: str
    content_hash: str

    @classmethod
    def create(cls, file_path: str, content: str) -> ProposalArtifact:
        art_id = f"art_{uuid.uuid4().hex[:12]}"
        c_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(
            artifact_id=art_id,
            file_path=file_path,
            content=content,
            content_hash=c_hash,
        )


@dataclass
class CompositionProposal:
    """Structured proposal representing generated or adapted code requiring human/agent review."""

    proposal_id: str
    request_id: str
    adapted_code: str
    source_brick_ids: List[str]
    status: str = "draft"  # 'draft', 'review', 'accepted', 'rejected'
    artifacts: List[ProposalArtifact] = field(default_factory=list)
    rationale: str = ""
    confidence_score: float = 0.8
    warnings: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert proposal to serializable dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "request_id": self.request_id,
            "status": self.status,
            "adapted_code": self.adapted_code,
            "source_brick_ids": list(self.source_brick_ids),
            "artifacts": [asdict(a) for a in self.artifacts],
            "rationale": self.rationale,
            "confidence_score": self.confidence_score,
            "warnings": list(self.warnings),
            "created_at": self.created_at,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize proposal to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CompositionProposal:
        """Construct proposal instance from dictionary."""
        artifacts = [
            ProposalArtifact(
                artifact_id=a.get("artifact_id", ""),
                file_path=a.get("file_path", ""),
                content=a.get("content", ""),
                content_hash=a.get("content_hash", ""),
            )
            for a in data.get("artifacts", [])
        ]
        return cls(
            proposal_id=data.get("proposal_id", f"prop_{uuid.uuid4().hex[:12]}"),
            request_id=data.get("request_id", ""),
            adapted_code=data.get("adapted_code", ""),
            source_brick_ids=data.get("source_brick_ids", []),
            status=data.get("status", "draft"),
            artifacts=artifacts,
            rationale=data.get("rationale", ""),
            confidence_score=float(data.get("confidence_score", 0.8)),
            warnings=data.get("warnings", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )

