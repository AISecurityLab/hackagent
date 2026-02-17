# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared components for attacks.

This module contains reusable components used across different
objectives and techniques.
"""

from .progress import create_progress_bar
from .response_utils import extract_response_content
from .router_factory import create_router
from .tui import with_tui_logging

__all__ = [
    "create_progress_bar",
    "create_router",
    "extract_response_content",
    "with_tui_logging",
]
