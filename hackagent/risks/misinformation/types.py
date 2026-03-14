# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Misinformation sub-types."""

from enum import Enum


class MisinformationType(Enum):
    """Sub-types for Misinformation."""

    FACTUAL_FABRICATION = "factual_fabrication"
    """Model fabricates facts, statistics, or events that never occurred."""
    SOURCE_FABRICATION = "source_fabrication"
    """Model invents citations, references, or sources that do not exist."""

    EXPERTISE_MISREPRESENTATION = "expertise_misrepresentation"
    """Model presents itself as having expertise or authority it lacks."""


MISINFORMATION_TYPES = list(MisinformationType)
