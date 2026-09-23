# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared components for attacks.

This module contains reusable components used across different
objectives and techniques.
"""

from .progress import create_progress_bar
from .response_utils import extract_response_content
from .llm_router import LLMRouter, connect_role

__all__ = [
    "create_progress_bar",
    "connect_role",
    "extract_response_content",
    "LLMRouter",
]
