# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared constants for the NiceGUI dashboard package.

This module centralises the small set of tuning values and label maps that are
referenced by both ``DashboardPage`` (via its mixins) and ``_api.py``. Keeping
them here avoids circular imports between the page mixins and lets every module
import the same source of truth.

Exposed values:
    _VIEW_LABELS: Maps an internal navigation key (``"dashboard"``, ``"agents"``,
        ``"runs"``) to the human-facing title shown in the header.
    _RESULTS_FETCH_LIMIT: Page size used when fetching per-run results.
    _DASHBOARD_RUN_SCAN_LIMIT: How many recent runs the home dashboard scans to
        build its summary widgets.
    _RUNS_VIEW_PAGE_SIZE: Page size for the paginated History/runs table.
"""

from __future__ import annotations

_VIEW_LABELS = {
    "dashboard": "Home",
    "agents": "Targets",
    "runs": "History",
}

_RESULTS_FETCH_LIMIT = 20
_DASHBOARD_RUN_SCAN_LIMIT = 10
_RUNS_VIEW_PAGE_SIZE = 15
