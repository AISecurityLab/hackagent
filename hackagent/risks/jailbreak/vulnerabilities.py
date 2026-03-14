# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Jailbreak implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.jailbreak.types import JailbreakType, JAILBREAK_TYPES


class Jailbreak(BaseVulnerability):
    """Jailbreak."""

    name = "Jailbreak"
    description = (
        "Tests whether the LLM can be manipulated into bypassing its safety "
        "filters through roleplay, encoding, multi-turn, hypothetical, or "
        "authority-manipulation techniques."
    )
    ALLOWED_TYPES = [t.value for t in JailbreakType]
    _type_enum = JailbreakType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [JailbreakType(t) for t in types]
        else:
            resolved = list(JAILBREAK_TYPES)
        super().__init__(types=resolved)
