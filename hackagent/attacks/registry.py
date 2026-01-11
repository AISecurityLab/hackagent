# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Attack technique registry.

This module registers all available attack techniques as concrete orchestrators
using a factory function to eliminate boilerplate code.

The factory dynamically creates orchestrator classes that configure:
- attack_type: String identifier for the attack
- attack_impl_class: BaseAttack subclass implementing the algorithm
- Custom methods: Optional specialized behavior (e.g., PAIR's attacker setup)

To add a new attack:
1. Implement BaseAttack subclass in techniques/your_attack/
2. Register here using create_orchestrator()
3. Add to ATTACK_REGISTRY dict
"""

from typing import Any, Callable, Dict, Optional, Type

from hackagent.attacks.orchestrator import AttackOrchestrator
from hackagent.attacks.techniques.advprefix import AdvPrefixAttack
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.techniques.pair import PAIRAttack
from hackagent.attacks.techniques.template_based import TemplateBasedAttack


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

    # Add custom method if provided (e.g., PAIR's attacker router setup)
    if custom_setup:
        class_attrs["_get_attack_impl_kwargs"] = custom_setup

    return type(f"{attack_name}Orchestrator", (AttackOrchestrator,), class_attrs)


def _pair_setup_attacker(
    self,
    attack_config: Dict[str, Any],
    run_config_override: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    PAIR-specific setup: creates attacker router for adversarial prompt generation.

    PAIR uses a separate LLM as an "attacker" to generate adversarial prompts
    that are then tested against the target agent.
    """
    kwargs = AttackOrchestrator._get_attack_impl_kwargs(
        self, attack_config, run_config_override
    )

    attacker_config = attack_config.get("attacker", {})

    from hackagent.router import AgentRouter

    kwargs["attacker_router"] = AgentRouter(
        client=self.client,
        name=attacker_config.get("identifier", "hackagent-attacker"),
        agent_type="OPENAI",
        endpoint=attacker_config.get("endpoint", "https://api.openai.com/v1"),
        metadata=attacker_config,
        adapter_operational_config=attacker_config,
        overwrite_metadata=True,
    )

    return kwargs


# Create orchestrators using factory (1 line per attack instead of 6-50 lines)
AdvPrefixOrchestrator = create_orchestrator("AdvPrefix", AdvPrefixAttack)
TemplateBasedOrchestrator = create_orchestrator("TemplateBased", TemplateBasedAttack)
PAIROrchestrator = create_orchestrator("PAIR", PAIRAttack, _pair_setup_attacker)


# Registry of all available attacks
ATTACK_REGISTRY = {
    "AdvPrefix": AdvPrefixOrchestrator,
    "TemplateBased": TemplateBasedOrchestrator,
    "PAIR": PAIROrchestrator,
}

# Backward compatibility aliases
AdvPrefix = AdvPrefixOrchestrator
TemplateBased = TemplateBasedOrchestrator
PAIR = PAIROrchestrator

__all__ = [
    "AdvPrefixOrchestrator",
    "TemplateBasedOrchestrator",
    "PAIROrchestrator",
    "ATTACK_REGISTRY",
    "AdvPrefix",
    "TemplateBased",
    "PAIR",
]
