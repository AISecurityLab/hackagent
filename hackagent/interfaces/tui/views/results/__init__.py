# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Past runs in the TUI: :class:`ResultsTab`, the tree of campaigns, their
attacks and the goals each tried (``tab.py``), and its CSV and JSON exports
(``export.py``). What each line says is :mod:`hackagent.interfaces.results`,
which ``hackagent results summary`` prints too.
"""

from hackagent.interfaces.tui.views.results.tab import ResultsTab

__all__ = ["ResultsTab"]
