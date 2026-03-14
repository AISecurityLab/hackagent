# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for Misinformation vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    PRIMARY,
    SECONDARY,
    BASELINE_ONLY,
)
from hackagent.risks.misinformation import Misinformation

MISINFORMATION_PROFILE = ThreatProfile(
    vulnerability=Misinformation,
    datasets=[
        ds(
            "truthfulqa",
            PRIMARY,
            "TruthfulQA for evaluating factual accuracy and misinformation",
        ),
        ds(
            "saladbench",
            SECONDARY,
            "SaladBench for broader misinformation coverage",
        ),
    ],
    attacks=BASELINE_ONLY,
    objective="harmful_behavior",
    metrics=["truthfulness_score", "accuracy_score"],
    description="Tests whether the LLM produces factual fabrications or misinformation.",
)
