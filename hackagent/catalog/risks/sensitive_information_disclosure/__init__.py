# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Sensitive Information Disclosure risk.

Tests for training-data extraction, architecture disclosure, and configuration
leakage. Exports the ``SensitiveInformationDisclosureType`` sub-types, the
``SensitiveInformationDisclosure`` vulnerability and the
``SENSITIVE_INFORMATION_DISCLOSURE_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.sensitive_information_disclosure.types import (
    SensitiveInformationDisclosureType,
)
from hackagent.catalog.risks.sensitive_information_disclosure.vulnerabilities import (
    SensitiveInformationDisclosure,
)
from hackagent.catalog.risks.sensitive_information_disclosure.profile import (
    SENSITIVE_INFORMATION_DISCLOSURE_PROFILE,
)

__all__ = [
    "SensitiveInformationDisclosureType",
    "SensitiveInformationDisclosure",
    "SENSITIVE_INFORMATION_DISCLOSURE_PROFILE",
]
