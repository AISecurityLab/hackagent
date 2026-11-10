# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared attack helpers.

Depth-0 techniques import only ``hackagent.core`` and this package — not
other depth-0 packages or sibling techniques. What is here:

- :mod:`.response`: response text and guardrail extraction, shared with the
  model layer;
- :mod:`.prompt_parser`: reading the JSON ``improvement``/``prompt`` turns
  PAIR's and TAP's attackers write;
- :mod:`.graphviz`: the Graphviz bootstrap FC-Attack renders with;
- :mod:`.templates` and :mod:`.transforms`: a template library and text
  transforms that no technique currently imports (static_template keeps its
  own templates).
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
