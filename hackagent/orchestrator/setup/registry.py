# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Lazy ``AttackId -> "module:Class"`` registry.

Importing this module does not import technique classes. :func:`load_attack`
resolves an entry the first time a run needs it.
"""

from __future__ import annotations

import importlib
from typing import Dict, Optional, Type

from hackagent.attacks.techniques.base import BaseAttack
from hackagent.catalog.taxonomy import AttackId

# Canonical ids only. There are no display-name aliases.
ATTACK_REGISTRY: Dict[str, str] = {
    "baseline": "hackagent.attacks.techniques.static.baseline.attack:BaselineAttack",
    "static_template": (
        "hackagent.attacks.techniques.static.static_template.attack:StaticTemplateAttack"
    ),
    "flipattack": "hackagent.attacks.techniques.static.flipattack.attack:FlipAttack",
    "cipherchat": "hackagent.attacks.techniques.static.cipherchat.attack:CipherChatAttack",
    "h4rm3l": "hackagent.attacks.techniques.static.h4rm3l.attack:H4rm3lAttack",
    "mml": "hackagent.attacks.techniques.static.mml.attack:MMLAttack",
    "fc": "hackagent.attacks.techniques.static.fc.attack:FCAttack",
    "tfc": "hackagent.attacks.techniques.static.fc.attack:tFCAttack",
    "rag": "hackagent.attacks.techniques.indirect.rag.attack:RagAttack",
    "pair": "hackagent.attacks.techniques.adaptive.pair.attack:PAIRAttack",
    "tap": "hackagent.attacks.techniques.adaptive.tap.attack:TAPAttack",
    "pap": "hackagent.attacks.techniques.adaptive.pap.attack:PAPAttack",
    "bon": "hackagent.attacks.techniques.adaptive.bon.attack:BoNAttack",
    "advprefix": "hackagent.attacks.techniques.adaptive.advprefix.attack:AdvPrefixAttack",
    "autodan_turbo": (
        "hackagent.attacks.techniques.adaptive.autodan_turbo.attack:AutoDANTurboAttack"
    ),
    "tool_output_ipi": (
        "hackagent.attacks.techniques.indirect.tool_output_ipi.attack:ToolOutputIPIAttack"
    ),
    "crescendo": "hackagent.attacks.techniques.multi_turn.crescendo.attack:CrescendoAttack",
}

# Typed configs used for JSON-schema planning. Techniques without one are
# still runnable; the planner just has no parameters to propose.
CONFIG_REGISTRY: Dict[str, str] = {
    "static_template": (
        "hackagent.attacks.techniques.static.static_template.config:TemplateAttackConfig"
    ),
    "flipattack": "hackagent.attacks.techniques.static.flipattack.config:FlipAttackConfig",
    "cipherchat": "hackagent.attacks.techniques.static.cipherchat.config:CipherChatConfig",
    "h4rm3l": "hackagent.attacks.techniques.static.h4rm3l.config:H4rm3lConfig",
    "mml": "hackagent.attacks.techniques.static.mml.config:MMLConfig",
    "fc": "hackagent.attacks.techniques.static.fc.config:FCConfig",
    "tfc": "hackagent.attacks.techniques.static.fc.config:tFCConfig",
    "rag": "hackagent.attacks.techniques.indirect.rag.config:RagConfig",
    "pair": "hackagent.attacks.techniques.adaptive.pair.config:PairConfig",
    "tap": "hackagent.attacks.techniques.adaptive.tap.config:TapConfig",
    "pap": "hackagent.attacks.techniques.adaptive.pap.config:PAPConfig",
    "bon": "hackagent.attacks.techniques.adaptive.bon.config:BoNConfig",
    "autodan_turbo": (
        "hackagent.attacks.techniques.adaptive.autodan_turbo.config:AutoDANTurboConfig"
    ),
    "tool_output_ipi": (
        "hackagent.attacks.techniques.indirect.tool_output_ipi.config:ToolOutputIPIConfig"
    ),
    "crescendo": "hackagent.attacks.techniques.multi_turn.crescendo.config:CrescendoConfig",
}


def _load(spec: str) -> type:
    module_name, _, class_name = spec.partition(":")
    if not module_name or not class_name:
        raise ValueError(f"Invalid registry spec {spec!r}; expected 'module:Class'")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ImportError(f"{spec} does not exist") from exc


def load_attack(attack_id: str) -> Type[BaseAttack]:
    """Import and return the technique class for a canonical ``AttackId``."""
    spec = ATTACK_REGISTRY.get(attack_id)
    if spec is None:
        known = ", ".join(ATTACK_REGISTRY)
        raise ValueError(
            f"Unsupported attack_type: {attack_id}. Supported types: {known}."
        )
    cls = _load(spec)
    if not isinstance(cls, type) or not issubclass(cls, BaseAttack):
        raise TypeError(f"{spec} is not a BaseAttack subclass")
    return cls


def load_config_model(attack_id: str) -> Optional[type]:
    """Return the technique's pydantic config, or ``None`` when it has none."""
    spec = CONFIG_REGISTRY.get(attack_id)
    if spec is None:
        return None
    return _load(spec)


def known_ids() -> tuple[AttackId, ...]:
    """Registry ids in catalog order."""
    return tuple(ATTACK_REGISTRY)  # type: ignore[return-value]


__all__ = [
    "ATTACK_REGISTRY",
    "CONFIG_REGISTRY",
    "known_ids",
    "load_attack",
    "load_config_model",
]
