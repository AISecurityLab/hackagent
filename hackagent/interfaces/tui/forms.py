# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack forms generated from technique JSON schema.

The facade's catalog is the only field source. There is no second,
hand-written schema beside the pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class FieldType(str, Enum):
    """Widget kinds the attacks form knows how to render."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    TEXT = "text"


_TYPE_MAP = {
    "string": FieldType.STRING,
    "integer": FieldType.INTEGER,
    "int": FieldType.INTEGER,
    "number": FieldType.FLOAT,
    "float": FieldType.FLOAT,
    "boolean": FieldType.BOOLEAN,
    "bool": FieldType.BOOLEAN,
    "choice": FieldType.CHOICE,
    "text": FieldType.TEXT,
}


@dataclass
class ConfigField:
    """One form control, flattened from a technique JSON schema."""

    key: str
    label: str
    field_type: FieldType
    default: Any = None
    description: str = ""
    required: bool = False
    choices: Optional[Sequence[Tuple[str, Any]]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    section: str = "General"
    advanced: bool = False


@dataclass
class AttackConfigSpec:
    """Form for one registered technique."""

    technique_key: str
    display_name: str
    description: str = ""
    fields: List[ConfigField] = field(default_factory=list)
    category_value: str = ""
    category_label: str = ""
    category_description: str = ""
    tag_values: Tuple[str, ...] = ()
    tag_labels: Tuple[str, ...] = ()

    def sections(self) -> List[str]:
        """Unique section names in order of first appearance."""
        seen: set[str] = set()
        result: list[str] = []
        for item in self.fields:
            if item.section not in seen:
                seen.add(item.section)
                result.append(item.section)
        return result

    def fields_for_section(
        self, section: str, *, include_advanced: bool = False
    ) -> List[ConfigField]:
        """Fields belonging to ``section``."""
        return [
            item
            for item in self.fields
            if item.section == section and (include_advanced or not item.advanced)
        ]

    def defaults_dict(self) -> Dict[str, Any]:
        """Flat ``{key: default}`` for fields that declare a default."""
        return {
            item.key: item.default
            for item in self.fields
            if item.default is not None
        }

    def validate(self, values: Dict[str, Any]) -> List[str]:
        """Return human-readable errors. An empty list means the values fit."""
        errors: list[str] = []
        for item in self.fields:
            val = values.get(item.key)
            if item.required and (val is None or val == ""):
                errors.append(f"{item.label} is required.")
                continue
            if val is None or val == "":
                continue
            if item.field_type == FieldType.INTEGER:
                try:
                    int_val = int(val)
                except (TypeError, ValueError):
                    errors.append(f"{item.label} must be an integer.")
                    continue
                if item.min_value is not None and int_val < item.min_value:
                    errors.append(
                        f"{item.label} must be ≥ {item.min_value} (got {int_val})."
                    )
                if item.max_value is not None and int_val > item.max_value:
                    errors.append(
                        f"{item.label} must be ≤ {item.max_value} (got {int_val})."
                    )
            elif item.field_type == FieldType.FLOAT:
                try:
                    float_val = float(val)
                except (TypeError, ValueError):
                    errors.append(f"{item.label} must be a number.")
                    continue
                if item.min_value is not None and float_val < item.min_value:
                    errors.append(
                        f"{item.label} must be ≥ {item.min_value} (got {float_val})."
                    )
                if item.max_value is not None and float_val > item.max_value:
                    errors.append(
                        f"{item.label} must be ≤ {item.max_value} (got {float_val})."
                    )
            elif item.field_type == FieldType.CHOICE:
                valid_values = [choice[1] for choice in (item.choices or [])]
                if val not in valid_values:
                    errors.append(f"{item.label}: '{val}' is not a valid choice.")
        return errors


def _field_from_catalog(raw: Dict[str, Any]) -> ConfigField:
    choices = None
    if raw.get("choices"):
        choices = [tuple(pair) for pair in raw["choices"]]
    return ConfigField(
        key=raw["key"],
        label=raw["label"],
        field_type=_TYPE_MAP.get(str(raw.get("type") or "string"), FieldType.STRING),
        default=raw.get("default"),
        description=str(raw.get("description") or ""),
        required=bool(raw.get("required")),
        choices=choices,
        min_value=raw.get("min"),
        max_value=raw.get("max"),
        section=str(raw.get("section") or "General"),
        advanced=bool(raw.get("advanced")),
    )


def _spec_from_entry(entry: Dict[str, Any]) -> AttackConfigSpec:
    return AttackConfigSpec(
        technique_key=entry["attack_type"],
        display_name=entry["label"],
        description=entry.get("description") or "",
        fields=[_field_from_catalog(raw) for raw in entry.get("fields") or []],
        category_value=entry.get("category") or "",
        category_label=entry.get("category_label") or "",
        category_description=entry.get("category_description") or "",
        tag_values=tuple(entry.get("tags") or ()),
        tag_labels=tuple(entry.get("tag_labels") or ()),
    )


def get_all_attack_specs() -> Dict[str, AttackConfigSpec]:
    """Every registered technique, in registry order."""
    from hackagent.client import catalog_entries

    return {entry["attack_type"]: _spec_from_entry(entry) for entry in catalog_entries()}


def get_attack_config_spec(technique_key: str) -> Optional[AttackConfigSpec]:
    """Form for ``technique_key``, or ``None`` when it is not registered."""
    return get_all_attack_specs().get(technique_key)


__all__ = [
    "AttackConfigSpec",
    "ConfigField",
    "FieldType",
    "get_all_attack_specs",
    "get_attack_config_spec",
]
