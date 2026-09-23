# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compatibility shim — prefer ``hackagent.attacks._lib``."""

from hackagent.attacks._lib.llm_router import LLMRouter, connect_role
from hackagent.attacks._lib.progress import create_progress_bar
from hackagent.attacks._lib.response import extract_response_content

__all__ = [
    "create_progress_bar",
    "connect_role",
    "extract_response_content",
    "LLMRouter",
]
