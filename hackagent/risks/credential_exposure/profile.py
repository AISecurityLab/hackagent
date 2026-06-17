# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Threat profile for CredentialExposure vulnerability."""

from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import STATIC_TEMPLATE_ONLY
from hackagent.risks.credential_exposure import CredentialExposure

CREDENTIAL_EXPOSURE_PROFILE = ThreatProfile(
    vulnerability=CredentialExposure,
    datasets=[],  # No standard public dataset — requires custom goals
    attacks=STATIC_TEMPLATE_ONLY,
    objective="policy_violation",
    metrics=["asr"],
    description="Tests for hardcoded credentials, token leakage, and misconfigured access.",
)
