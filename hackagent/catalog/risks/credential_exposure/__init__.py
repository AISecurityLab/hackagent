# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Credential Exposure risk.

Tests for hardcoded credentials, token leakage, and misconfigured access
controls in AI systems. Exports the ``CredentialExposureType`` sub-types, the
``CredentialExposure`` vulnerability and the ``CREDENTIAL_EXPOSURE_PROFILE``
threat profile.
"""

from hackagent.catalog.risks.credential_exposure.types import CredentialExposureType
from hackagent.catalog.risks.credential_exposure.vulnerabilities import (
    CredentialExposure,
)
from hackagent.catalog.risks.credential_exposure.profile import (
    CREDENTIAL_EXPOSURE_PROFILE,
)

__all__ = [
    "CredentialExposureType",
    "CredentialExposure",
    "CREDENTIAL_EXPOSURE_PROFILE",
]
