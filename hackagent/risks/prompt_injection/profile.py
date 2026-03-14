# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for PromptInjection vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    PRIMARY,
    SECONDARY,
    JAILBREAK_ATTACKS,
)
from hackagent.risks.prompt_injection import PromptInjection

PROMPT_INJECTION_PROFILE = ThreatProfile(
    vulnerability=PromptInjection,
    datasets=[
        ds(
            "advbench",
            PRIMARY,
            "520 adversarial goals covering injection scenarios",
        ),
        ds(
            "harmbench_contextual",
            PRIMARY,
            "Contextual prompts requiring instruction override",
        ),
        ds(
            "prompt_injections",
            PRIMARY,
            "662 prompt injection samples for direct PI testing (deepset)",
        ),
        ds(
            "strongreject",
            SECONDARY,
            "Forbidden prompts to test injection guardrails",
        ),
    ],
    attacks=JAILBREAK_ATTACKS,
    objective="jailbreak",
    metrics=["asr", "judge_score"],
    description="Tests whether injected instructions override system prompts.",
)
