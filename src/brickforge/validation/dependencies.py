"""Dependency availability checks comparing package requirements against environments or lockfiles."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import metadata
from typing import Dict, List, Optional, Sequence, Union


@dataclass(frozen=True)
class DependencyCheckItem:
    """Evaluation result for an individual package requirement."""

    package_name: str
    required_constraint: Optional[str]
    installed_version: Optional[str]
    status: str  # 'satisfied', 'missing', 'incompatible', 'unknown'
    reason: str

    @property
    def is_satisfied(self) -> bool:
        return self.status == "satisfied"


@dataclass
class DependencyAvailabilityReport:
    """Consolidated report on declared dependencies vs environment/lockfile."""

    items: List[DependencyCheckItem] = field(default_factory=list)

    @property
    def is_all_satisfied(self) -> bool:
        return all(i.is_satisfied for i in self.items)

    @property
    def missing(self) -> List[str]:
        return [i.package_name for i in self.items if i.status == "missing"]

    @property
    def incompatible(self) -> List[str]:
        return [i.package_name for i in self.items if i.status == "incompatible"]

    @property
    def unknown(self) -> List[str]:
        return [i.package_name for i in self.items if i.status == "unknown"]


def parse_semver_tuple(version_str: str) -> Optional[List[int]]:
    """Parse version string like '2.3.1' into integer list [2, 3, 1]."""
    parts = re.findall(r"\d+", version_str)
    if not parts:
        return None
    return [int(p) for p in parts]


def check_version_satisfaction(installed: str, constraint: str) -> bool:
    """Statically verify if installed version satisfies constraint without network."""
    clean_c = constraint.strip()
    if not clean_c or clean_c == "*":
        return True

    inst_tuple = parse_semver_tuple(installed)
    if not inst_tuple:
        return False

    # Handle >=X.Y.Z
    if clean_c.startswith(">="):
        target_tuple = parse_semver_tuple(clean_c[2:])
        if not target_tuple:
            return False
        return inst_tuple >= target_tuple

    # Handle ==X.Y.Z
    if clean_c.startswith("=="):
        target_tuple = parse_semver_tuple(clean_c[2:])
        if not target_tuple:
            return False
        return inst_tuple == target_tuple

    # Handle >X.Y.Z
    if clean_c.startswith(">"):
        target_tuple = parse_semver_tuple(clean_c[1:])
        if not target_tuple:
            return False
        return inst_tuple > target_tuple

    # Handle <=X.Y.Z
    if clean_c.startswith("<="):
        target_tuple = parse_semver_tuple(clean_c[2:])
        if not target_tuple:
            return False
        return inst_tuple <= target_tuple

    # Handle <X.Y.Z
    if clean_c.startswith("<"):
        target_tuple = parse_semver_tuple(clean_c[1:])
        if not target_tuple:
            return False
        return inst_tuple < target_tuple

    # Handle ^X.Y (compatible with semver major)
    if clean_c.startswith("^"):
        target_tuple = parse_semver_tuple(clean_c[1:])
        if not target_tuple:
            return False
        if inst_tuple < target_tuple:
            return False
        # If major matches or target major is 0 and minor matches
        if target_tuple[0] > 0:
            return inst_tuple[0] == target_tuple[0]
        return inst_tuple[:2] == target_tuple[:2]

    # Bare version treated as ==
    target_tuple = parse_semver_tuple(clean_c)
    return inst_tuple == target_tuple if target_tuple else False


class DependencyAvailabilityChecker:
    """Audits required packages against an environment or lockfile mapping."""

    def __init__(self, environment_packages: Optional[Dict[str, str]] = None):
        """Initialize with an explicit dictionary or discover from active environment."""
        if environment_packages is not None:
            self.environment = {k.lower(): v for k, v in environment_packages.items()}
        else:
            self.environment = self._discover_installed_packages()

    @staticmethod
    def _discover_installed_packages() -> Dict[str, str]:
        """Introspect installed packages in current Python environment."""
        pkgs: Dict[str, str] = {}
        try:
            for dist in metadata.distributions():
                name = dist.metadata.get("Name")
                ver = dist.version
                if name and ver:
                    pkgs[name.lower()] = ver
        except Exception:
            pass
        return pkgs

    @classmethod
    def from_lockfile_text(cls, lockfile_text: str) -> DependencyAvailabilityChecker:
        """Parse requirements.txt-style lockfile into package mapping."""
        pkgs: Dict[str, str] = {}
        for line in lockfile_text.splitlines():
            clean = re.sub(r"#.*$", "", line).strip()
            if not clean:
                continue
            # match name==1.2.3 or name>=1.2.3
            m = re.match(r"^([\w\-]+)\s*==\s*([\w\.\-]+)", clean)
            if m:
                pkgs[m.group(1).lower()] = m.group(2)
            else:
                m_bare = re.match(r"^([\w\-]+)", clean)
                if m_bare:
                    pkgs[m_bare.group(1).lower()] = "0.0.0"
        return cls(environment_packages=pkgs)

    def check_requirements(
        self,
        requirements: Sequence[Union[str, Dict[str, Optional[str]]]],
    ) -> DependencyAvailabilityReport:
        """Evaluate a sequence of requirements against the environment."""
        items: List[DependencyCheckItem] = []

        for req in requirements:
            if isinstance(req, str):
                # parse name>=ver or name
                m = re.match(r"^([\w\-]+)(.*)$", req.strip())
                if m:
                    pkg_name = m.group(1).strip()
                    constraint = m.group(2).strip() or None
                else:
                    pkg_name = req.strip()
                    constraint = None
            else:
                pkg_name = req.get("name") or req.get("package_name") or ""
                constraint = req.get("version_constraint") or req.get("constraint")

            norm_name = pkg_name.lower()

            if norm_name not in self.environment:
                items.append(
                    DependencyCheckItem(
                        package_name=pkg_name,
                        required_constraint=constraint,
                        installed_version=None,
                        status="missing",
                        reason=f"Package '{pkg_name}' is not installed in the target environment.",
                    )
                )
                continue

            installed_ver = self.environment[norm_name]

            if not constraint:
                items.append(
                    DependencyCheckItem(
                        package_name=pkg_name,
                        required_constraint=None,
                        installed_version=installed_ver,
                        status="satisfied",
                        reason=f"Package installed (version {installed_ver}).",
                    )
                )
                continue

            # Validate constraint syntax
            if not re.search(r"[\d]", constraint):
                items.append(
                    DependencyCheckItem(
                        package_name=pkg_name,
                        required_constraint=constraint,
                        installed_version=installed_ver,
                        status="unknown",
                        reason=f"Constraint '{constraint}' could not be parsed.",
                    )
                )
                continue

            # Check satisfaction
            is_sat = check_version_satisfaction(installed_ver, constraint)
            if is_sat:
                items.append(
                    DependencyCheckItem(
                        package_name=pkg_name,
                        required_constraint=constraint,
                        installed_version=installed_ver,
                        status="satisfied",
                        reason=f"Version {installed_ver} satisfies {constraint}.",
                    )
                )
            else:
                items.append(
                    DependencyCheckItem(
                        package_name=pkg_name,
                        required_constraint=constraint,
                        installed_version=installed_ver,
                        status="incompatible",
                        reason=f"Installed version {installed_ver} violates requirement {constraint}.",
                    )
                )

        return DependencyAvailabilityReport(items=items)

