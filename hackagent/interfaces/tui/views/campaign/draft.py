# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The campaign being built, held as the document it will be saved as.

The draft stores only what the user set; everything else is the schema's
default, shown by the form but never written. Validation reports issues by
document path so the form can put each one on its row.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from hackagent.orchestrator.campaign import CampaignSpec

from .schema import Path

DEFAULT_DOCUMENT: dict[str, Any] = {
    "version": 1,
    "campaign": {"name": "Quick safety check"},
    "dataset": {
        "source": {"type": "preset", "name": "harmbench"},
        "selection": {"limit": 10},
    },
    "target": {
        "name": "local-model",
        "connection": {
            "provider": "local",
            "type": "OPENAI_SDK",
            "endpoint": "http://127.0.0.1:8000/v1",
        },
    },
    "attacks": [{"name": "baseline"}],
}

_SECTION_ORDER = tuple(CampaignSpec.model_fields)


@dataclass(frozen=True)
class Issue:
    """A validation problem at a document path."""

    loc: Path
    message: str


@dataclass(frozen=True)
class Plan:
    goals: Optional[int]
    attacks: int
    judges: int

    @property
    def searches(self) -> Optional[int]:
        return None if self.goals is None else self.goals * self.attacks


class CampaignDraft:
    """A mutable campaign document with path-based access."""

    def __init__(self, document: Optional[dict[str, Any]] = None) -> None:
        self.data: dict[str, Any] = copy.deepcopy(
            DEFAULT_DOCUMENT if document is None else document
        )

    # -- document access ------------------------------------------------

    def get(self, path: Path) -> tuple[bool, Any]:
        """``(found, value)`` at ``path``."""
        node: Any = self.data
        for part in path:
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and isinstance(part, int) and part < len(node):
                node = node[part]
            else:
                return False, None
        return True, node

    def set(self, path: Path, value: Any) -> bool:
        """Write ``value`` at ``path``; ``False`` when nothing changed."""
        found, current = self.get(path)
        if found and current == value:
            return False
        node: Any = self.data
        for part in path[:-1]:
            if isinstance(node, list):
                node = node[part]
                continue
            child = node.get(part)
            if not isinstance(child, (dict, list)):
                child = {}
                node[part] = child
            node = child
        node[path[-1]] = value
        return True

    def delete(self, path: Path, *, keep: int = 1) -> bool:
        """Remove ``path``, then the mappings it leaves empty below ``path[:keep]``."""
        found, _ = self.get(path)
        if not found:
            return False
        parents = [self.data]
        for part in path[:-1]:
            parents.append(parents[-1][part])
        del parents[-1][path[-1]]
        for depth in range(len(path) - 1, keep, -1):
            node = parents[depth]
            if isinstance(node, dict) and not node:
                del parents[depth - 1][path[depth - 1]]
            else:
                break
        return True

    def items(self, path: Path) -> list[Any]:
        found, value = self.get(path)
        return value if found and isinstance(value, list) else []

    def append(self, path: Path, item: dict[str, Any]) -> int:
        found, value = self.get(path)
        if not (found and isinstance(value, list)):
            value = []
            self.set(path, value)
        value.append(item)
        return len(value) - 1

    def remove(self, path: Path, index: int) -> None:
        items = self.items(path)
        if 0 <= index < len(items):
            items.pop(index)

    # -- persistence ----------------------------------------------------

    def to_yaml(self) -> str:
        ordered = {key: self.data[key] for key in _SECTION_ORDER if key in self.data}
        ordered.update(
            (key, value) for key, value in self.data.items() if key not in ordered
        )
        return yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, text: str) -> "CampaignDraft":
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("A campaign file must be a YAML mapping.")
        return cls(data)

    # -- validation -----------------------------------------------------

    def validate(self) -> tuple[Optional[CampaignSpec], tuple[Issue, ...]]:
        issues = list(self._attack_issues())
        try:
            spec: Optional[CampaignSpec] = CampaignSpec.model_validate(self.data)
        except ValidationError as exc:
            spec = None
            for error in exc.errors(include_url=False):
                message = str(error.get("msg") or "Invalid value")
                if message == "Field required":
                    message = "required"
                issues.append(
                    Issue(
                        tuple(error.get("loc") or ()),
                        message.removeprefix("Value error, "),
                    )
                )
        return (spec if not issues else None), tuple(issues)

    def _attack_issues(self) -> list[Issue]:
        """What campaign resolution would reject: bad parameters, missing roles."""
        from hackagent.attacks.techniques.registry import ATTACKS, get_attack_class

        issues = []
        for index, attack in enumerate(self.items(("attacks",))):
            name = attack.get("name") if isinstance(attack, dict) else None
            if name not in ATTACKS:
                continue
            params = get_attack_class(name).params_type
            root = ("attacks", index)
            try:
                params.model_validate(attack.get("parameters") or {})
            except ValidationError as exc:
                for error in exc.errors(include_url=False):
                    issues.append(
                        Issue(
                            root + ("parameters", *tuple(error.get("loc") or ())),
                            str(error.get("msg") or "Invalid value"),
                        )
                    )
            roles = attack.get("roles") or {}
            for role in sorted(params.REQUIRED_ROLES - set(roles)):
                issues.append(
                    Issue(root + ("roles", role), f"{name} requires the {role} model")
                )
        return issues

    def plan(self) -> Plan:
        found, goals = self.get(("dataset", "source", "goals"))
        _, source_type = self.get(("dataset", "source", "type"))
        _, limit = self.get(("dataset", "selection", "limit"))
        if source_type == "inline" and found and isinstance(goals, list):
            count: Optional[int] = len(goals)
            if isinstance(limit, int):
                count = min(count, limit)
        else:
            count = limit if isinstance(limit, int) else None
        return Plan(
            goals=count,
            attacks=len(self.items(("attacks",))),
            judges=len(self.items(("evaluation", "judges"))),
        )


__all__ = ["CampaignDraft", "DEFAULT_DOCUMENT", "Issue", "Plan"]
