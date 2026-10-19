# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Name → class lookup for the attacks a campaign can run.

Attack modules are imported on first use, so naming an attack does not pull
in the image dependencies of FC or MML.
"""

from __future__ import annotations

import importlib
from typing import Any, Optional, Union

from .iterative import IterativeAttack
from .static.base import StaticAttack

_PACKAGE = "hackagent.attacks.techniques"

_ATTACKS: dict[str, str] = {
    "baseline": "static.baseline:BaselineAttack",
    "static_template": "static.static_template:StaticTemplateAttack",
    "flipattack": "static.flipattack:FlipAttack",
    "cipherchat": "static.cipherchat:CipherChatAttack",
    "h4rm3l": "static.h4rm3l:H4rm3lAttack",
    "mml": "static.mml:MMLAttack",
    "fc": "static.fc:FCAttack",
    "tfc": "static.fc:tFCAttack",
    "bon": "adaptive.bon:BoNAttack",
    "pap": "adaptive.pap:PAPAttack",
    "pair": "adaptive.pair:PAIRAttack",
    "tap": "adaptive.tap:TAPAttack",
    "crescendo": "multi_turn.crescendo:CrescendoAttack",
    "advprefix": "adaptive.advprefix:AdvPrefixAttack",
    "tool_output_ipi": "indirect.tool_output_ipi:ToolOutputIPIAttack",
    "rag": "indirect.rag:RagAttack",
    "autodan_turbo": "adaptive.autodan_turbo:AutoDANTurboAttack",
}

ATTACKS = frozenset(_ATTACKS)
STATIC_ATTACKS = frozenset(
    name for name, path in _ATTACKS.items() if path.startswith("static.")
)
ITERATIVE_ATTACKS = ATTACKS - STATIC_ATTACKS

AttackType = Union[type[StaticAttack], type[IterativeAttack]]


def get_attack_class(name: str) -> AttackType:
    """Return the attack class registered under ``name``."""
    try:
        module_name, class_name = _ATTACKS[name].split(":")
    except KeyError:
        known = ", ".join(sorted(ATTACKS))
        raise ValueError(f"Unknown attack {name!r}. Available: {known}.") from None
    module = importlib.import_module(f"{_PACKAGE}.{module_name}")
    return getattr(module, class_name)


def params_schema(name: str) -> Optional[dict[str, Any]]:
    """JSON schema of ``name``'s parameters, roles left out.

    A role field holds a callable, which has no JSON schema, so the schema
    comes from a model of the plain parameters. Those are exactly the keys
    a campaign file puts under ``parameters``, which is what every form and
    planner catalogue needs to offer.
    """
    from pydantic import create_model

    if name not in _ATTACKS:
        return None
    params_type = get_attack_class(name).params_type
    roles = params_type.role_names()
    fields = {
        field: (info.annotation, info)
        for field, info in params_type.model_fields.items()
        if field not in roles
    }
    if not fields:
        return None
    return create_model(f"{params_type.__name__}Form", **fields).model_json_schema()


__all__ = [
    "ATTACKS",
    "ITERATIVE_ATTACKS",
    "STATIC_ATTACKS",
    "AttackType",
    "get_attack_class",
    "params_schema",
]
