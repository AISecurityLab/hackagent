# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack technique registry.

This module registers all available attack techniques as concrete orchestrators
using a factory function to eliminate boilerplate code.

The factory dynamically creates orchestrator classes that configure:
- attack_type: String identifier for the attack
- attack_impl_class: BaseAttack subclass implementing the algorithm

To add a new attack:
1. Implement BaseAttack subclass in techniques/your_attack/
2. Register here using create_orchestrator()
3. Add to ATTACK_REGISTRY dict
"""

from typing import Callable, Optional, Type

from hackagent.attacks.orchestrator import AttackOrchestrator
from hackagent.attacks.techniques.advprefix import AdvPrefixAttack
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.techniques.pair import PAIRAttack
from hackagent.attacks.techniques.baseline import BaselineAttack
from hackagent.attacks.techniques.flipattack import FlipAttack
from hackagent.attacks.techniques.tap import (
    TAPAttack,
)  # Placeholder for future implementation
from hackagent.attacks.techniques.autodan_turbo import AutoDANTurboAttack
from hackagent.attacks.techniques.bon import BoNAttack
from hackagent.attacks.techniques.h4rm3l import H4rm3lAttack
from hackagent.attacks.techniques.pap import PAPAttack


def create_orchestrator(
    attack_name: str,
    attack_impl_class: Type[BaseAttack],
    custom_setup: Optional[Callable] = None,
) -> Type[AttackOrchestrator]:
    """
    Factory function to create orchestrator classes dynamically.

    This eliminates repetitive class definitions while maintaining clean
    architecture separation between orchestration and attack algorithms.

    Args:
        attack_name: Attack identifier (e.g., "AdvPrefix")
        attack_impl_class: BaseAttack subclass implementing the technique
        custom_setup: Optional method for specialized kwargs preparation
            Signature: (self, attack_config, run_config_override) -> Dict[str, Any]

    Returns:
        Orchestrator class configured for this attack technique

    Example:
        >>> MyOrchestrator = create_orchestrator("MyAttack", MyAttackClass)
        >>> orchestrator = MyOrchestrator(hack_agent)
        >>> results = orchestrator.execute(attack_config)
    """
    class_attrs = {
        "attack_type": attack_name,
        "attack_impl_class": attack_impl_class,
        "__doc__": f"{attack_name}: {attack_impl_class.__doc__ or 'Attack technique orchestrator'}",
    }

    # Add custom method if provided
    if custom_setup:
        class_attrs["_get_attack_impl_kwargs"] = custom_setup

    return type(f"{attack_name}Orchestrator", (AttackOrchestrator,), class_attrs)


# Create orchestrators using factory (1 line per attack)
AdvPrefixOrchestrator = create_orchestrator("AdvPrefix", AdvPrefixAttack)
BaselineOrchestrator = create_orchestrator("Baseline", BaselineAttack)
PAIROrchestrator = create_orchestrator("PAIR", PAIRAttack)
FlipAttackOrchestrator = create_orchestrator("FlipAttack", FlipAttack)
TAPOrchestrator = create_orchestrator("TAP", TAPAttack)
AutoDANTurboOrchestrator = create_orchestrator("AutoDANTurbo", AutoDANTurboAttack)
BoNOrchestrator = create_orchestrator("bon", BoNAttack)
H4rm3lOrchestrator = create_orchestrator("h4rm3l", H4rm3lAttack)
PAPOrchestrator = create_orchestrator("pap", PAPAttack)

# Registry of all available attacks
ATTACK_REGISTRY = {
    "AdvPrefix": AdvPrefixOrchestrator,
    "Baseline": BaselineOrchestrator,
    "PAIR": PAIROrchestrator,
    "FlipAttack": FlipAttackOrchestrator,
    "TAP": TAPOrchestrator,
    "AutoDANTurbo": AutoDANTurboOrchestrator,
    "bon": BoNOrchestrator,
    "h4rm3l": H4rm3lOrchestrator,
    "pap": PAPOrchestrator,
}

__all__ = [
    "AdvPrefixOrchestrator",
    "BaselineOrchestrator",
    "PAIROrchestrator",
    "FlipAttackOrchestrator",
    "TAPOrchestrator",
    "AutoDANTurboOrchestrator",
    "BoNOrchestrator",
    "H4rm3lOrchestrator",
    "PAPOrchestrator",
    "ATTACK_REGISTRY",
]
