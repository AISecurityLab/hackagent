# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Registry of TUI attack configuration specs.

Holds the ordered ``technique_key -> AttackConfigSpec`` mapping. The
registry is populated by importing :mod:`hackagent.cli.tui.attack_specs.specs`,
which registers one spec per attack technique module.
"""

from __future__ import annotations

from typing import Dict, Optional

from hackagent.cli.tui.attack_specs.types import AttackConfigSpec

_SPECS: Dict[str, AttackConfigSpec] = {}


def register(spec: AttackConfigSpec) -> AttackConfigSpec:
    """Register and return *spec* (convenience for inline use)."""
    _SPECS[spec.technique_key] = spec
    return spec


def get_attack_config_spec(technique_key: str) -> Optional[AttackConfigSpec]:
    """Return the config spec for *technique_key*, or ``None``."""
    return _SPECS.get(technique_key)


def get_all_attack_specs() -> Dict[str, AttackConfigSpec]:
    """Return all registered attack config specs."""
    return dict(_SPECS)
