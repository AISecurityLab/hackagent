# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Excessive Agency implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.excessive_agency.types import (
    ExcessiveAgencyType,
    EXCESSIVE_AGENCY_TYPES,
)


class ExcessiveAgency(BaseVulnerability):
    """Excessive Agency."""

    name = "Excessive Agency"
    description = (
        "Tests whether the LLM performs actions or grants permissions "
        "exceeding its intended scope without oversight."
    )
    ALLOWED_TYPES = [t.value for t in ExcessiveAgencyType]
    _type_enum = ExcessiveAgencyType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [ExcessiveAgencyType(t) for t in types]
        else:
            resolved = list(EXCESSIVE_AGENCY_TYPES)
        super().__init__(types=resolved)
