# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ToolHijacker: poison tool documents to influence retrieval and selection."""

from .attack import ToolHijackerAttack
from .config import ToolDocument, ToolHijackerParams

__all__ = ["ToolDocument", "ToolHijackerAttack", "ToolHijackerParams"]
