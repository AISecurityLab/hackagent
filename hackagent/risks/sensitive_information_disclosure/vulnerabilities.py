# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Sensitive Information Disclosure implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.sensitive_information_disclosure.types import (
    SensitiveInformationDisclosureType,
    SENSITIVE_INFORMATION_DISCLOSURE_TYPES,
)


class SensitiveInformationDisclosure(BaseVulnerability):
    """Sensitive Information Disclosure."""

    name = "Sensitive Information Disclosure"
    description = (
        "Tests for training-data extraction, architecture disclosure, "
        "and configuration leakage."
    )
    ALLOWED_TYPES = [t.value for t in SensitiveInformationDisclosureType]
    _type_enum = SensitiveInformationDisclosureType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [SensitiveInformationDisclosureType(t) for t in types]
        else:
            resolved = list(SENSITIVE_INFORMATION_DISCLOSURE_TYPES)
        super().__init__(types=resolved)
