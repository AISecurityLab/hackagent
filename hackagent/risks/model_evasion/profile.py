# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for ModelEvasion vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    PRIMARY,
    SECONDARY,
    JAILBREAK_ATTACKS,
)
from hackagent.risks.model_evasion import ModelEvasion

MODEL_EVASION_PROFILE = ThreatProfile(
    vulnerability=ModelEvasion,
    datasets=[
        ds(
            "advbench",
            PRIMARY,
            "Adversarial benchmarks for evaluating evasion resistance",
        ),
        ds(
            "xstest",
            SECONDARY,
            "XSTest for adversarial prompt detection",
        ),
    ],
    attacks=JAILBREAK_ATTACKS,
    objective="jailbreak",
    metrics=["asr", "judge_score"],
    description="Tests whether adversarial examples can evade the model's safety mechanisms.",
)
