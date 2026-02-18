# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for ExcessiveAgency vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    PRIMARY,
    SECONDARY,
    BASELINE_ONLY,
)
from hackagent.risks.excessive_agency import ExcessiveAgency

EXCESSIVE_AGENCY_PROFILE = ThreatProfile(
    vulnerability=ExcessiveAgency,
    datasets=[
        ds(
            "agentharm",
            PRIMARY,
            "AgentHarm dataset for evaluating excessive agency in tool use",
        ),
        ds(
            "agentharm_benign",
            SECONDARY,
            "Benign agent scenarios to establish baseline behavior",
        ),
    ],
    attacks=BASELINE_ONLY,
    objective="policy_violation",
    metrics=["asr", "judge_score"],
    description="Tests whether the LLM performs actions exceeding its intended scope.",
)
