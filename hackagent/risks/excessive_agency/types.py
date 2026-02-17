# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Excessive Agency sub-types."""

from enum import Enum


class ExcessiveAgencyType(Enum):
    """Sub-types for Excessive Agency."""

    FUNCTIONALITY = "functionality"
    """Model performs actions beyond its intended scope."""
    PERMISSIONS = "permissions"
    """Model grants or exercises permissions it should not have."""

    AUTONOMY = "autonomy"
    """Model acts autonomously without required human oversight."""


EXCESSIVE_AGENCY_TYPES = list(ExcessiveAgencyType)
