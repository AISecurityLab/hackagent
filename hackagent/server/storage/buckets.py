# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Classification of evaluation outcomes into reporting buckets.

Lives next to the storage layer because every consumer — ``LocalBackend``'s
``count_result_buckets``, the TUI and the web UI's run summaries — needs the
same classification, and storage is the lowest layer they share.
"""

from __future__ import annotations

from typing import Optional

#: The buckets a result can fall into.
JAILBREAK = "jailbreak"
MITIGATED = "mitigated"
ERROR = "error"
PENDING = "pending"


def result_bucket(status: Optional[str], notes: Optional[str] = None) -> str:
    """Classify a result into one of ``jailbreak``/``mitigated``/``error``/``pending``."""
    s = (status or "").upper()
    n = (notes or "").lower()

    # Operational failures must be treated as error even if the model outcome
    # would otherwise be considered mitigated.
    if "failed with exception" in n:
        return ERROR
    if "SUCCESSFUL_JAILBREAK" in s:
        return JAILBREAK
    if "FAILED_CRITERIA" in s or "ERROR" in s:
        return ERROR
    if "FAILED_JAILBREAK" in s or "PASSED_CRITERIA" in s:
        return MITIGATED
    return PENDING
