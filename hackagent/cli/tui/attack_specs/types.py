# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Field and spec primitives for TUI attack configuration forms.

Defines the declarative building blocks (:class:`FieldType`,
:class:`ConfigField`, :class:`AttackConfigSpec`) used to describe the form
fields the TUI renders when configuring an attack. Kept free of attack
domain imports so other front-ends can reuse it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class FieldType(str, Enum):
    """Supported configuration field types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    TEXT = "text"


@dataclass
class ConfigField:
    """Specification for a single configuration parameter.

    Attributes:
        key: Dot-separated key path (e.g. ``"attacker.temperature"``).
             Dotted keys are expanded into nested dicts at collection time.
        label: Human-readable label shown in the UI.
        field_type: One of :class:`FieldType` values.
        default: Default value for the field.
        description: Tooltip / help text shown to the user.
        required: Whether the field must be provided.
        choices: For ``CHOICE`` type, the list of ``(label, value)`` pairs.
        min_value: Minimum value for numeric fields.
        max_value: Maximum value for numeric fields.
        step: Step increment for numeric fields (sliders / spinners).
        section: Logical grouping (e.g. ``"Generation"``).  The TUI uses
                 this to organize fields into collapsible sections.
        advanced: If ``True`` the field is hidden behind the
                  "Show advanced settings" toggle.
    """

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
    """Complete configuration specification for an attack technique.

    Attributes:
        technique_key: Internal identifier (e.g. ``"advprefix"``).
        display_name: Human-friendly name shown in the UI selector.
        description: Short description of the technique.
        fields: Ordered list of :class:`ConfigField`.
    """

    technique_key: str
    display_name: str
    description: str = ""
    fields: List[ConfigField] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def sections(self) -> List[str]:
        """Return unique section names in order of first appearance."""
        seen: set[str] = set()
        result: list[str] = []
        for f in self.fields:
            if f.section not in seen:
                seen.add(f.section)
                result.append(f.section)
        return result

    def fields_for_section(
        self, section: str, *, include_advanced: bool = False
    ) -> List[ConfigField]:
        """Return fields belonging to *section*."""
        return [
            f
            for f in self.fields
            if f.section == section and (include_advanced or not f.advanced)
        ]

    def defaults_dict(self) -> Dict[str, Any]:
        """Build a flat ``{key: default}`` mapping for all fields."""
        return {f.key: f.default for f in self.fields if f.default is not None}

    def validate(self, values: Dict[str, Any]) -> List[str]:
        """Validate *values* against the spec.

        Returns:
            A list of human-readable error strings (empty = valid).
        """
        errors: list[str] = []
        for f in self.fields:
            val = values.get(f.key)

            if f.required and (val is None or val == ""):
                errors.append(f"{f.label} is required.")
                continue

            if val is None or val == "":
                continue

            if f.field_type == FieldType.INTEGER:
                try:
                    int_val = int(val)
                except (TypeError, ValueError):
                    errors.append(f"{f.label} must be an integer.")
                    continue
                if f.min_value is not None and int_val < f.min_value:
                    errors.append(f"{f.label} must be ≥ {f.min_value} (got {int_val}).")
                if f.max_value is not None and int_val > f.max_value:
                    errors.append(f"{f.label} must be ≤ {f.max_value} (got {int_val}).")

            elif f.field_type == FieldType.FLOAT:
                try:
                    float_val = float(val)
                except (TypeError, ValueError):
                    errors.append(f"{f.label} must be a number.")
                    continue
                if f.min_value is not None and float_val < f.min_value:
                    errors.append(
                        f"{f.label} must be ≥ {f.min_value} (got {float_val})."
                    )
                if f.max_value is not None and float_val > f.max_value:
                    errors.append(
                        f"{f.label} must be ≤ {f.max_value} (got {float_val})."
                    )

            elif f.field_type == FieldType.CHOICE:
                valid_values = [c[1] for c in (f.choices or [])]
                if val not in valid_values:
                    errors.append(f"{f.label}: '{val}' is not a valid choice.")

        return errors
