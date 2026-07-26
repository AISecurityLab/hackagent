# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Results view package.

Router module: re-exports :class:`ResultsTab` and the formatting helpers so
that ``hackagent.cli.tui.views.results`` keeps its historical import surface.

Layout:
    - ``tab.py``: the ``ResultsTab`` widget (layout, bindings, data refresh).
    - ``table.py``: run-list table rendering.
    - ``details.py``: right-hand detail panel rendering.
    - ``export.py``: CSV/JSON export actions.
    - ``formatters/``: pure Rich-markup formatting helpers.
"""

from hackagent.cli.tui.views.results.formatters import (
    _coerce_datetime,
    _escape,
    _format_chat_message,
    _format_config_dict,
    _format_local_datetime,
    _format_message_content,
    _format_request_payload,
    _format_response_body,
    _format_result_full_details,
    _format_result_summary,
    _format_trace_block,
    _format_trace_content,
    _get_result_status_info,
    _step_num_circle,
    _step_style,
)
from hackagent.cli.tui.views.results.formatters.run_report import (
    build_run_report_header,
)
from hackagent.cli.tui.views.results.tab import ResultsTab

__all__ = [
    "ResultsTab",
    "build_run_report_header",
    "_coerce_datetime",
    "_escape",
    "_format_chat_message",
    "_format_config_dict",
    "_format_local_datetime",
    "_format_message_content",
    "_format_request_payload",
    "_format_response_body",
    "_format_result_full_details",
    "_format_result_summary",
    "_format_trace_block",
    "_format_trace_content",
    "_get_result_status_info",
    "_step_num_circle",
    "_step_style",
]
