# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Sensitive Information Disclosure sub-types."""

from enum import Enum


class SensitiveInformationDisclosureType(Enum):
    """Sub-types for Sensitive Information Disclosure."""

    TRAINING_DATA_EXTRACTION = "training_data_extraction"
    """Model memorisation allows extraction of training data."""
    SYSTEM_ARCHITECTURE_DISCLOSURE = "system_architecture_disclosure"
    """Model reveals internal architecture details."""

    CONFIGURATION_LEAKAGE = "configuration_leakage"
    """Model exposes configuration parameters or settings."""


SENSITIVE_INFORMATION_DISCLOSURE_TYPES = list(SensitiveInformationDisclosureType)
