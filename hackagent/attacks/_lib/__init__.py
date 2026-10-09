# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared attack helpers.

Depth-0 techniques import only ``hackagent.core`` and this package — not
other depth-0 packages or sibling techniques. What remains here is the live
set: response extraction (shared with the model layer), prompt parsing,
templating transforms, and the graphviz helper.
"""

from hackagent.attacks._lib.response import (
    extract_response_content,
    get_guardrail_info,
    is_guardrail_response,
)

__all__ = [
    "extract_response_content",
    "get_guardrail_info",
    "is_guardrail_response",
]
