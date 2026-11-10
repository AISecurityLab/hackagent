# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Input Manipulation Attack implementation."""

from typing import List, Optional
from hackagent.catalog.risks.base import BaseVulnerability
from hackagent.catalog.risks.input_manipulation_attack.types import (
    InputManipulationAttackType,
    INPUT_MANIPULATION_ATTACK_TYPES,
)


class InputManipulationAttack(BaseVulnerability):
    """The Input Manipulation Attack vulnerability, with the sub-types to test.

    Args:
        types: Sub-type values to select, e.g. ``"encoding_bypass"``. All
            sub-types when omitted or empty.

    Raises:
        ValueError: When a value is not a ``InputManipulationAttackType``.
    """

    name = "Input Manipulation Attack"
    description = (
        "Tests whether encoding bypasses, format string attacks, or "
        "Unicode manipulation can evade input validation and safety filters."
    )
    ALLOWED_TYPES = [t.value for t in InputManipulationAttackType]
    _type_enum = InputManipulationAttackType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [InputManipulationAttackType(t) for t in types]
        else:
            resolved = list(INPUT_MANIPULATION_ATTACK_TYPES)
        super().__init__(types=resolved)
