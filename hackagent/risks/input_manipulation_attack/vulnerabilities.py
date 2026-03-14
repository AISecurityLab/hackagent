# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Input Manipulation Attack implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.input_manipulation_attack.types import (
    InputManipulationAttackType,
    INPUT_MANIPULATION_ATTACK_TYPES,
)


class InputManipulationAttack(BaseVulnerability):
    """Input Manipulation Attack."""

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
