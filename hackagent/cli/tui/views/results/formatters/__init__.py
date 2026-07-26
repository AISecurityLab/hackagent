# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Results formatting helpers.

Pure, widget-free functions that turn run/result/trace objects into Rich
markup strings. Keeping them separate from the ``ResultsTab`` widget makes
them directly unit-testable and reusable.
"""

from hackagent.cli.tui.views.results.formatters.datetimes import (
    _coerce_datetime,
    _format_local_datetime,
)
from hackagent.cli.tui.views.results.formatters.http import (
    _format_request_payload,
    _format_response_body,
)
from hackagent.cli.tui.views.results.formatters.summaries import (
    _format_result_full_details,
    _format_result_summary,
    _get_result_status_info,
)
from hackagent.cli.tui.views.results.formatters.text import (
    _escape,
    _format_chat_message,
    _format_message_content,
)
from hackagent.cli.tui.views.results.formatters.traces import (
    _format_config_dict,
    _format_trace_block,
    _format_trace_content,
    _step_num_circle,
    _step_style,
)

__all__ = [
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
