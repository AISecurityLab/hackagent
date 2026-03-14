# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for Jailbreak vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    PRIMARY,
    SECONDARY,
    ALL_ATTACKS,
)
from hackagent.risks.jailbreak import Jailbreak

JAILBREAK_PROFILE = ThreatProfile(
    vulnerability=Jailbreak,
    datasets=[
        ds(
            "strongreject",
            PRIMARY,
            "324 forbidden prompts designed for jailbreak evaluation",
        ),
        ds("harmbench", PRIMARY, "200 harmful behaviors for bypass testing"),
        ds("advbench", PRIMARY, "520 adversarial goals for jailbreak attacks"),
        ds(
            "jailbreakbench",
            PRIMARY,
            "100 curated misuse behaviours from NeurIPS 2024 benchmark",
        ),
        ds(
            "simplesafetytests",
            SECONDARY,
            "100 clear-cut harmful prompts as baseline",
        ),
        ds(
            "donotanswer",
            SECONDARY,
            "939 refusal questions for comprehensive coverage",
        ),
        ds(
            "saladbench_attack",
            SECONDARY,
            "5K attack-enhanced prompts with jailbreak methods",
        ),
    ],
    attacks=ALL_ATTACKS,
    objective="jailbreak",
    metrics=["asr", "judge_score"],
    description="Tests resistance to multi-turn, roleplay, encoding, and authority-based bypass.",
)
