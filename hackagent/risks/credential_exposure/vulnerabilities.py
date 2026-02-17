# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Credential Exposure and Mismanagement implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.credential_exposure.types import (
    CredentialExposureType,
    CREDENTIAL_EXPOSURE_TYPES,
)


class CredentialExposure(BaseVulnerability):
    """Credential Exposure and Mismanagement."""

    name = "Credential Exposure"
    description = (
        "Tests for hardcoded credentials, token leakage, and "
        "misconfigured access controls in AI systems."
    )
    ALLOWED_TYPES = [t.value for t in CredentialExposureType]
    _type_enum = CredentialExposureType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [CredentialExposureType(t) for t in types]
        else:
            resolved = list(CREDENTIAL_EXPOSURE_TYPES)
        super().__init__(types=resolved)
