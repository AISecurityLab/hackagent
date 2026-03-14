# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Terminal User Interface (TUI)

Full-featured terminal interface for HackAgent with tabbed navigation,
real-time attack monitoring, and interactive configuration.

Structure:
    - app.py: Main TUI application class
    - base.py: Base widgets and utilities
    - logger.py: TUI logging handler for attack execution logs
    - views/: Tab views (dashboard, agents, attacks, results, config)
    - widgets/: Reusable UI components (log viewer, etc.)
"""

from hackagent.cli.tui.app import HackAgentTUI

__all__ = ["HackAgentTUI"]
