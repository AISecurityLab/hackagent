# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared attack helpers (transforms, scoring, templates, objectives).

Depth-0 techniques import only ``hackagent.core`` and this package — not
other depth-0 packages or sibling techniques.
"""

from hackagent.attacks._lib.progress import create_progress_bar, report_progress
from hackagent.attacks._lib.response import (
    extract_response_content,
    get_guardrail_info,
    is_guardrail_response,
)
from hackagent.attacks._lib.scoring import (
    normalize_judge_score,
    normalized_jailbreak_threshold,
)

__all__ = [
    "create_progress_bar",
    "extract_response_content",
    "get_guardrail_info",
    "is_guardrail_response",
    "normalize_judge_score",
    "normalized_jailbreak_threshold",
    "report_progress",
]
