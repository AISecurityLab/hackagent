# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Parse results shared by the judge types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssertionResult:
    """A parsed judge reply.

    ``is_confident`` is false when the parser had to guess. Callers may
    retry once in that case.
    """

    score: float
    explanation: str
    is_confident: bool
