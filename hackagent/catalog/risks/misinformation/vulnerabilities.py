# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Misinformation implementation."""

from typing import List, Optional
from hackagent.catalog.risks.base import BaseVulnerability
from hackagent.catalog.risks.misinformation.types import (
    MisinformationType,
    MISINFORMATION_TYPES,
)


class Misinformation(BaseVulnerability):
    """The Misinformation vulnerability, with the sub-types to test.

    Args:
        types: Sub-type values to select, e.g. ``"factual_fabrication"``. All
            sub-types when omitted or empty.

    Raises:
        ValueError: When a value is not a ``MisinformationType``.
    """

    name = "Misinformation"
    description = (
        "Tests whether the LLM produces factual fabrications, invented "
        "sources, or misrepresented expertise."
    )
    ALLOWED_TYPES = [t.value for t in MisinformationType]
    _type_enum = MisinformationType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [MisinformationType(t) for t in types]
        else:
            resolved = list(MISINFORMATION_TYPES)
        super().__init__(types=resolved)
