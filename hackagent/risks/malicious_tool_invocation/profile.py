# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for MaliciousToolInvocation vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    SECONDARY,
    BASELINE_ONLY,
)
from hackagent.risks.malicious_tool_invocation import MaliciousToolInvocation

MALICIOUS_TOOL_INVOCATION_PROFILE = ThreatProfile(
    vulnerability=MaliciousToolInvocation,
    datasets=[
        ds(
            "agentharm",
            SECONDARY,
            "Agentic tasks that exercise plugin/tool interactions",
        ),
    ],
    attacks=BASELINE_ONLY,
    objective="policy_violation",
    metrics=["asr", "judge_score"],
    description="Tests for untrusted plugin execution, data exfiltration, and privilege escalation via plugins.",
)
