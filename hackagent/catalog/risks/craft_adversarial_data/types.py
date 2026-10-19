# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Craft Adversarial Data sub-types."""

from enum import Enum


class CraftAdversarialDataType(Enum):
    """Sub-types for Craft Adversarial Data."""

    PERTURBATION_ATTACKS = "perturbation_attacks"
    """Small, imperceptible changes to inputs that alter model outputs."""
    POISONED_EXAMPLES = "poisoned_examples"
    """Adversarially crafted examples designed to trigger specific model failures."""

    DATA_AUGMENTATION_ABUSE = "data_augmentation_abuse"
    """Exploiting data augmentation pipelines to inject adversarial samples."""


CRAFT_ADVERSARIAL_DATA_TYPES = list(CraftAdversarialDataType)
