# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TUI views.

:class:`CampaignBuilder` is the app: build a campaign, check it, run it. The
others are standalone views the CLI still opens (``hackagent results``,
``hackagent agent``); they are no longer part of the main screen.
"""

from hackagent.interfaces.tui.views.agents import AgentsTab
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.config import ConfigTab
from hackagent.interfaces.tui.views.results import ResultsTab

__all__ = [
    "AgentsTab",
    "CampaignBuilder",
    "ConfigTab",
    "ResultsTab",
]
