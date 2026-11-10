# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Craft Adversarial Data risk.

Tests whether adversarially crafted data — perturbations, poisoned examples, or
augmentation abuse — can compromise model behaviour. Exports the
``CraftAdversarialDataType`` sub-types, the ``CraftAdversarialData``
vulnerability and the ``CRAFT_ADVERSARIAL_DATA_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.craft_adversarial_data.types import (
    CraftAdversarialDataType,
)
from hackagent.catalog.risks.craft_adversarial_data.vulnerabilities import (
    CraftAdversarialData,
)
from hackagent.catalog.risks.craft_adversarial_data.profile import (
    CRAFT_ADVERSARIAL_DATA_PROFILE,
)

__all__ = [
    "CraftAdversarialDataType",
    "CraftAdversarialData",
    "CRAFT_ADVERSARIAL_DATA_PROFILE",
]
