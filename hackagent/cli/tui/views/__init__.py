# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TUI Views

Tab views/panels for the HackAgent TUI application.
Each view represents a different functional area of the interface.
"""

from hackagent.cli.tui.views.agents import AgentsTab
from hackagent.cli.tui.views.attacks import AttacksTab
from hackagent.cli.tui.views.config import ConfigTab
from hackagent.cli.tui.views.results import ResultsTab

__all__ = ["AgentsTab", "AttacksTab", "ConfigTab", "ResultsTab"]

"""
TUI Tabs Module

Individual tab implementations for the HackAgent TUI.
"""
