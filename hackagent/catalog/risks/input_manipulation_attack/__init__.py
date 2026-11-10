# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Input Manipulation Attack risk.

Tests whether encoding bypasses, format string attacks, or Unicode manipulation
can evade input validation and safety filters. Exports the
``InputManipulationAttackType`` sub-types, the ``InputManipulationAttack``
vulnerability and the ``INPUT_MANIPULATION_ATTACK_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.input_manipulation_attack.types import (
    InputManipulationAttackType,
)
from hackagent.catalog.risks.input_manipulation_attack.vulnerabilities import (
    InputManipulationAttack,
)
from hackagent.catalog.risks.input_manipulation_attack.profile import (
    INPUT_MANIPULATION_ATTACK_PROFILE,
)

__all__ = [
    "InputManipulationAttackType",
    "InputManipulationAttack",
    "INPUT_MANIPULATION_ATTACK_PROFILE",
]
