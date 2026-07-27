# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TUI-local attack configuration specifications.

This package is the **single source of truth** for the form fields that the
TUI renders when configuring an attack.  It is intentionally decoupled from
the attack domain code (``hackagent.attacks``) so that:

* Adding / removing a field never touches the attack implementation.
* The TUI remains agnostic to the selected attack strategy — every
  strategy is just another ``AttackConfigSpec`` in the registry.
* The framework (``ConfigField``, ``FieldType``, ``AttackConfigSpec``)
  can be re-used by future CLIs or web UIs without pulling in attack
  dependencies.

Layout:
    - ``types.py``: field/spec primitives.
    - ``registry.py``: the ``technique_key -> spec`` registry.
    - ``specs/``: one module per attack technique, each exposing ``SPEC``.

To add a new attack to the TUI, add a module under ``specs/`` and list it in
``specs/__init__.py``.
"""

from __future__ import annotations

# Importing the specs package populates the registry as a side effect.
from hackagent.cli.tui.attack_specs import specs as _specs  # noqa: F401
from hackagent.cli.tui.attack_specs.registry import (
    get_all_attack_specs,
    get_attack_config_spec,
    register,
)
from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

__all__ = [
    "AttackConfigSpec",
    "ConfigField",
    "FieldType",
    "get_all_attack_specs",
    "get_attack_config_spec",
    "register",
]
