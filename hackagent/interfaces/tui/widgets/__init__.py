# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TUI Widgets

Reusable Textual widgets for the HackAgent TUI interface.
"""

from hackagent.interfaces.tui.widgets.actions import AgentActionsViewer
from hackagent.interfaces.tui.widgets.logs import AttackLogViewer

__all__ = ["AttackLogViewer", "AgentActionsViewer"]
