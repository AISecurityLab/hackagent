# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Misinformation implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.misinformation.types import (
    MisinformationType,
    MISINFORMATION_TYPES,
)


class Misinformation(BaseVulnerability):
    """Misinformation."""

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
