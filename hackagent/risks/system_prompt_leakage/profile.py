# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for SystemPromptLeakage vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    SECONDARY,
    JAILBREAK_ATTACKS,
)
from hackagent.risks.system_prompt_leakage import SystemPromptLeakage

SYSTEM_PROMPT_LEAKAGE_PROFILE = ThreatProfile(
    vulnerability=SystemPromptLeakage,
    datasets=[
        ds(
            "advbench",
            SECONDARY,
            "Adversarial goals that may trigger system prompt disclosure",
        ),
    ],
    attacks=JAILBREAK_ATTACKS,
    objective="jailbreak",
    metrics=["asr", "judge_score"],
    description="Tests whether the model leaks system prompts, secrets, or guard configurations.",
)
