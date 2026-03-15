# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Re-export hackagent errors for server/api relative imports.

The auto-generated server/api/ code uses ``from ... import errors`` which
resolves to this module (hackagent.server.errors) when the api/ tree lives
under server/.  All symbols are forwarded from the canonical errors module so
callers that reference e.g. ``errors.UnexpectedStatus`` continue to work.
"""

from hackagent.errors import (  # noqa: F401
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
