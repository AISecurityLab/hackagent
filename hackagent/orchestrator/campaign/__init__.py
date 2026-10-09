# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Declarative campaigns of static and iterative attacks.

- :mod:`.spec`: the campaign file schema
- :mod:`.loader`: YAML → :class:`CampaignSpec`
- :mod:`.resolve`: spec → goals, models, judge panel, constructed attacks
- :mod:`.runner`: the async goal pipeline and :func:`run_campaign`
- :mod:`.tracking`: store records of each attack run
- :mod:`.results`: attempts, outcomes, and output files
- :mod:`.audit`: the ``evaluation.audit`` block, run before the attacks
- :mod:`.preflight`: ping the target and judges before attacking
- :mod:`.legacy`: the ``attack_config`` dict → campaign adapter behind ``hack``
"""

from hackagent.orchestrator.campaign.audit import (
    AuditFailed,
    format_report,
    read_report,
    run_audit,
)
from hackagent.orchestrator.campaign.loader import load_campaign
from hackagent.orchestrator.campaign.overrides import (
    EndpointOverrides,
    ServerReadiness,
    apply_endpoint_overrides,
    campaign_models,
    installed_models,
    wait_for_servers,
)
from hackagent.orchestrator.campaign.preflight import PreflightError, preflight
from hackagent.orchestrator.campaign.resolve import ResolvedCampaign, resolve_campaign
from hackagent.orchestrator.campaign.results import (
    Attempt,
    AttackOutcome,
    CampaignResult,
    summary,
)
from hackagent.orchestrator.campaign.runner import run_campaign
from hackagent.orchestrator.campaign.spec import CampaignSpec

__all__ = [
    "AuditFailed",
    "Attempt",
    "AttackOutcome",
    "CampaignResult",
    "CampaignSpec",
    "EndpointOverrides",
    "ResolvedCampaign",
    "ServerReadiness",
    "apply_endpoint_overrides",
    "campaign_models",
    "format_report",
    "installed_models",
    "PreflightError",
    "load_campaign",
    "preflight",
    "read_report",
    "resolve_campaign",
    "run_audit",
    "run_campaign",
    "summary",
    "wait_for_servers",
]
