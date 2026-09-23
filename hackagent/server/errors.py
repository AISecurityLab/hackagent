# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Compatibility re-export of canonical HackAgent errors.

All symbols are forwarded from ``hackagent.core.errors`` so imports that resolve
through ``hackagent.server.errors`` continue to work.
"""

from hackagent.core.errors import (
    ApiError,
    HackAgentError,
    UnexpectedStatus,
    UnexpectedStatusError,
)

__all__ = [
    "ApiError",
    "HackAgentError",
    "UnexpectedStatus",
    "UnexpectedStatusError",
]
