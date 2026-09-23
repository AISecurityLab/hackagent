# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack-facing configuration seam (Phase 4).

:class:`AttackConfig` holds **technique parameters and role fields only**.
Run bookkeeping (:class:`~hackagent.orchestrator.run_spec.RunSpec`) and
target generation (:class:`~hackagent.models.target_params.TargetParams`)
live elsewhere. ``roles()`` replaces the orchestrator's static role-path
table and the per-technique ``get_effective_model_roles`` overrides.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from hackagent.core.contracts import JudgeSpec

# Role field names that ``roles()`` introspects by default. Technique
# subclasses may extend via ``role_fields`` / ``role_list_fields``.
_DEFAULT_ROLE_FIELDS: Tuple[str, ...] = (
    "attacker",
    "judge",
    "scorer",
    "summarizer",
    "embedder",
    "decorator_llm",
    "on_topic_judge",
    "step_generator",
    "category_classifier",
)
_DEFAULT_ROLE_LIST_FIELDS: Tuple[str, ...] = ("judges",)

# role_name -> family used for local/remote default injection.
_ROLE_FAMILIES: Dict[str, Optional[str]] = {
    "attacker": "attacker",
    "judge": "judge",
    "scorer": "judge",
    "summarizer": "attacker",
    "embedder": None,
    "decorator_llm": "attacker",
    "on_topic_judge": None,
    "step_generator": "attacker",
    "category_classifier": None,
}


def ui(
    *,
    label: str,
    section: str = "General",
    advanced: bool = False,
    choices: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Build ``json_schema_extra`` for TUI/CLI form generation."""
    extra: Dict[str, Any] = {
        "label": label,
        "section": section,
        "advanced": advanced,
    }
    if choices is not None:
        extra["choices"] = list(choices)
    return extra


class AttackConfig(BaseModel):
    """Technique params + role fields. No run/target/batching concerns.

    Subclasses declare algorithm fields and any extra role fields. UI
    metadata belongs in ``Field(json_schema_extra=ui(...))``; pydantic
    defaults are the only defaults.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # Single judges list (JudgeSpec). Legacy single ``judge`` / ``scorer``
    # dicts remain on technique configs during the Phase 5 migration.
    judges: List[JudgeSpec] = Field(
        default_factory=list,
        json_schema_extra=ui(label="Judges", section="Evaluation"),
    )

    #: Scalar role fields introspected by :meth:`roles`.
    role_fields: ClassVar[Tuple[str, ...]] = _DEFAULT_ROLE_FIELDS
    #: List role fields (each element becomes one role entry).
    role_list_fields: ClassVar[Tuple[str, ...]] = _DEFAULT_ROLE_LIST_FIELDS

    def roles(self) -> List[Dict[str, Any]]:
        """Return preflight role descriptors for this config instance."""
        return self.roles_from_mapping(self.model_dump(exclude_none=False))

    @classmethod
    def roles_from_mapping(cls, data: Mapping[str, Any]) -> List[Dict[str, Any]]:
        """Introspect role fields from a plain config mapping.

        Each item is ``{"role": str, "config": dict, "required": bool}``.
        List fields (``judges``) emit one entry per element. Empty/missing
        values are skipped.
        """
        roles: List[Dict[str, Any]] = []

        for field in cls.role_fields:
            value = data.get(field)
            if isinstance(value, BaseModel):
                value = value.model_dump()
            if isinstance(value, dict) and value:
                roles.append(
                    {
                        "role": "judge" if field == "scorer" else field,
                        "config": dict(value),
                        "required": False,
                    }
                )

        for field in cls.role_list_fields:
            value = data.get(field)
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, BaseModel):
                    item = item.model_dump()
                if isinstance(item, dict) and item:
                    roles.append(
                        {"role": "judge", "config": dict(item), "required": False}
                    )

        return roles

    @classmethod
    def role_family(cls, role: str) -> Optional[str]:
        """Return the defaults family (``attacker`` / ``judge``) for *role*."""
        return _ROLE_FAMILIES.get(role)


# Known attack_type -> static role paths. Used by the orchestrator for
# role-family defaults and attack-type normalisation until Phase 7 moves
# defaults into ``orchestrator/defaults.py``. Technique-owned special cases
# go through ``AttackConfig.roles()`` / ``get_effective_model_roles``.
#
# Tuple layout: (role_name, config_path, is_list, role_family)
AttackRolePath = Tuple[str, Tuple[str, ...], bool, Optional[str]]

ATTACK_ROLE_PATHS: Dict[str, Tuple[AttackRolePath, ...]] = {
    "advprefix": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
    ),
    "static_template": (("judge", ("judges",), True, "judge"),),
    "flipattack": (("judge", ("judges",), True, "judge"),),
    "tap": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
        ("on_topic_judge", ("on_topic_judge",), False, None),
    ),
    "pair": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judge",), False, "judge"),
        ("judge", ("scorer",), False, "judge"),
    ),
    "crescendo": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judge",), False, "judge"),
    ),
    "autodan_turbo": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judge",), False, "judge"),
        ("judge", ("scorer",), False, "judge"),
        ("summarizer", ("summarizer",), False, "attacker"),
        ("embedder", ("embedder",), False, None),
    ),
    "bon": (("judge", ("judges",), True, "judge"),),
    "cipherchat": (("judge", ("judges",), True, "judge"),),
    "h4rm3l": (
        ("judge", ("judge",), False, "judge"),
        ("judge", ("judges",), True, "judge"),
        ("decorator_llm", ("decorator_llm",), False, "attacker"),
    ),
    "pap": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
    ),
    "rag": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
        ("embedder", ("rag_injection_params", "embedder"), False, None),
    ),
    "tool_output_ipi": (
        ("attacker", ("attacker",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
    ),
    "fc": (
        ("step_generator", ("step_generator",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
    ),
    "tfc": (
        ("step_generator", ("step_generator",), False, "attacker"),
        ("judge", ("judges",), True, "judge"),
    ),
    "mml": (("judge", ("judges",), True, "judge"),),
}


def roles_from_paths(attack_type: str, data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Resolve roles for *attack_type* using :data:`ATTACK_ROLE_PATHS`."""
    specs = ATTACK_ROLE_PATHS.get(attack_type) or ()
    roles: List[Dict[str, Any]] = []
    for role_name, path, is_list, _family in specs:
        cursor: Any = data
        for key in path:
            if not isinstance(cursor, Mapping):
                cursor = None
                break
            cursor = cursor.get(key)
        if cursor is None:
            continue
        items = cursor if (is_list and isinstance(cursor, list)) else [cursor]
        for item in items:
            if isinstance(item, BaseModel):
                item = item.model_dump()
            if isinstance(item, dict) and item:
                required = role_name in {
                    "attacker",
                    "judge",
                    "summarizer",
                    "step_generator",
                }
                roles.append(
                    {"role": role_name, "config": dict(item), "required": required}
                )
    return roles


def role_family_map(attack_type: str) -> Dict[str, str]:
    """Build role->family map for local/remote default injection."""
    mapping: Dict[str, str] = {}
    for role_name, _path, _is_list, family in ATTACK_ROLE_PATHS.get(attack_type) or ():
        if family in {"attacker", "judge"} and role_name not in mapping:
            mapping[role_name] = family
    return mapping


__all__ = [
    "ATTACK_ROLE_PATHS",
    "AttackConfig",
    "AttackRolePath",
    "role_family_map",
    "roles_from_paths",
    "ui",
]
