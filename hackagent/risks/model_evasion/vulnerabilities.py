# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model Evasion implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.model_evasion.types import (
    ModelEvasionType,
    MODEL_EVASION_TYPES,
)


class ModelEvasion(BaseVulnerability):
    """Model Evasion."""

    name = "Model Evasion"
    description = (
        "Tests whether adversarial examples, feature manipulation, or "
        "boundary exploitation can evade the model's safety mechanisms."
    )
    ALLOWED_TYPES = [t.value for t in ModelEvasionType]
    _type_enum = ModelEvasionType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [ModelEvasionType(t) for t in types]
        else:
            resolved = list(MODEL_EVASION_TYPES)
        super().__init__(types=resolved)
