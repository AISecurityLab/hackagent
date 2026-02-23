# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for SensitiveInformationDisclosure vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import (
    ds,
    SECONDARY,
    JAILBREAK_ATTACKS,
)
from hackagent.risks.sensitive_information_disclosure import (
    SensitiveInformationDisclosure,
)

SENSITIVE_INFORMATION_DISCLOSURE_PROFILE = ThreatProfile(
    vulnerability=SensitiveInformationDisclosure,
    datasets=[
        ds("advbench", SECONDARY, "Adversarial prompts that may trigger info leaks"),
        ds(
            "saladbench",
            SECONDARY,
            "21K harmful questions — includes info disclosure scenarios",
        ),
    ],
    attacks=JAILBREAK_ATTACKS,
    objective="jailbreak",
    metrics=["asr", "judge_score"],
    description="Tests for training data extraction, architecture disclosure, and config leakage.",
)
