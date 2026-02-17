# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Craft Adversarial Data implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.craft_adversarial_data.types import (
    CraftAdversarialDataType,
    CRAFT_ADVERSARIAL_DATA_TYPES,
)


class CraftAdversarialData(BaseVulnerability):
    """Craft Adversarial Data."""

    name = "Craft Adversarial Data"
    description = (
        "Tests whether adversarially crafted data — perturbations, poisoned "
        "examples, or augmentation abuse — can compromise model behaviour."
    )
    ALLOWED_TYPES = [t.value for t in CraftAdversarialDataType]
    _type_enum = CraftAdversarialDataType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [CraftAdversarialDataType(t) for t in types]
        else:
            resolved = list(CRAFT_ADVERSARIAL_DATA_TYPES)
        super().__init__(types=resolved)
