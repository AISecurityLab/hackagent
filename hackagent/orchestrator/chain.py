# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The escalating jailbreak chain.

``hack_chain`` runs a sequence of attacks against one shared pool of goals.
By default it escalates: a goal a step jailbreaks is dropped before the next
step runs, so later techniques only face the goals still standing. The whole
chain is one campaign — :func:`~hackagent.orchestrator.campaign.legacy.run_chain_as_campaign`
builds the :class:`CampaignSpec` and the runner's ``escalate`` mode does the
dropping. The CLI quick scan uses this instead of reimplementing the ladder.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from hackagent.core.errors import HackAgentError
from hackagent.core.logging import get_logger

logger = get_logger(__name__)


def hack_chain(
    agent: Any,
    attacks: Optional[list] = None,
    goals: Optional[list] = None,
    run_config_override: Optional[Dict[str, Any]] = None,
    fail_on_run_error: bool = True,
    escalate_only_mitigated: bool = True,
    on_event: Optional[Any] = None,
    _tui_event_bus: Optional[Any] = None,
) -> list:
    """Run ``attacks`` in order against a shared pool of goals.

    ``attacks`` defaults to the jailbreak profile's primary techniques. With
    ``escalate_only_mitigated`` (the default) a goal is dropped from later
    steps once a step jailbreaks it; otherwise every step runs against every
    goal. ``fail_on_run_error`` stops the chain on a failing step instead of
    carrying on. ``on_event`` is forwarded to the campaign. See
    ``Target.hack_chain``.
    """
    from hackagent.orchestrator.campaign.legacy import run_chain_as_campaign

    if on_event is None:
        on_event = _tui_event_bus
    if attacks is None:
        attacks = _default_chain()
    if not attacks:
        raise HackAgentError(
            "'attacks' must be a non-empty list of attack_config dicts."
        )
    for index, step in enumerate(attacks):
        if not isinstance(step, dict) or not step.get("attack_type"):
            raise HackAgentError(f"hack_chain step {index} is missing 'attack_type'.")

    override = dict(run_config_override or {})
    if not fail_on_run_error:
        override.setdefault("on_error", "continue")
    else:
        override.setdefault("on_error", "stop")

    return run_chain_as_campaign(
        agent,
        attacks,
        goals=goals,
        run_config_override=override,
        on_event=on_event,
        escalate=escalate_only_mitigated,
    )


def _default_chain() -> list:
    """The jailbreak profile's primary techniques, those that can run."""
    from hackagent.catalog.risks.jailbreak import JAILBREAK_PROFILE
    from hackagent.attacks.techniques.registry import ATTACKS

    # A technique nothing can execute is dropped rather than failing the
    # chain on its first step.
    return [
        {"attack_type": rec.technique}
        for rec in JAILBREAK_PROFILE.primary_attacks
        if rec.technique in ATTACKS
    ]


__all__ = ["hack_chain"]
