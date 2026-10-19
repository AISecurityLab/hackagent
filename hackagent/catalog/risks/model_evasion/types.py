# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model Evasion sub-types."""

from enum import Enum


class ModelEvasionType(Enum):
    """Sub-types for Model Evasion."""

    ADVERSARIAL_EXAMPLES = "adversarial_examples"
    """Crafted inputs that cause the model to misclassify or produce wrong outputs."""
    FEATURE_SPACE_MANIPULATION = "feature_space_manipulation"
    """Manipulating input features to evade detection or safety mechanisms."""

    MODEL_BOUNDARY_EXPLOITATION = "model_boundary_exploitation"
    """Exploiting decision boundaries to find blind spots in model behaviour."""


MODEL_EVASION_TYPES = list(ModelEvasionType)
