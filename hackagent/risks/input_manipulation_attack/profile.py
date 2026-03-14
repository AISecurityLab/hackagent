# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for InputManipulationAttack vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    SECONDARY,
    JAILBREAK_ATTACKS,
)
from hackagent.risks.input_manipulation_attack import InputManipulationAttack

INPUT_MANIPULATION_ATTACK_PROFILE = ThreatProfile(
    vulnerability=InputManipulationAttack,
    datasets=[
        ds(
            "wmdp_cyber",
            SECONDARY,
            "Cybersecurity knowledge covering SQL injection and command injection techniques",
        ),
    ],
    attacks=JAILBREAK_ATTACKS,
    objective="jailbreak",
    metrics=["asr", "judge_score"],
    description="Tests for SQL injection, command injection, and shell escape sequences.",
)
