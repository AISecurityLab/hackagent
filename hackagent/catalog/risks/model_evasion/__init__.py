# Copyright 2025 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Model Evasion risk.

Tests whether adversarial examples, feature manipulation, or boundary
exploitation can evade the model's safety mechanisms. Exports the
``ModelEvasionType`` sub-types, the ``ModelEvasion`` vulnerability and the
``MODEL_EVASION_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.model_evasion.types import ModelEvasionType
from hackagent.catalog.risks.model_evasion.vulnerabilities import ModelEvasion
from hackagent.catalog.risks.model_evasion.profile import MODEL_EVASION_PROFILE

__all__ = ["ModelEvasionType", "ModelEvasion", "MODEL_EVASION_PROFILE"]
