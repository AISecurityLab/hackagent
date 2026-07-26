# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Scan Command

``hackagent scan <url>`` red-teams a website's chatbot through the ``web``
provider: it drives the live page in a real browser, typing each prompt into the
chat widget and reading the reply from the DOM — so it works on any chat UI
regardless of transport (WebSocket/SSE/HTTP), with no endpoint reverse-
engineering. Add ``--plan`` to let an LLM pick the attack strategy; ``--no-attack``
just prints the target config (attack runs in the TUI by default, headless with
``--no-tui``).

This module also exposes the reusable ``run_quick_scan`` helper that backs the
``hackagent eval`` flow (the canned jailbreak campaign from JAILBREAK_PROFILE).

Router module: re-exports :func:`scan` and :func:`run_quick_scan` so that
``hackagent.cli.commands.scan`` keeps its historical import surface.

Layout:
    - ``helpers.py``: preset defaults and pure helpers.
    - ``command.py``: the ``scan`` click command.
    - ``quick.py``: the reusable ``run_quick_scan`` helper.
"""

from hackagent.cli.commands.scan.command import scan
from hackagent.cli.commands.scan.helpers import (
    DEFAULT_ATTACK_TYPE,
    DEFAULT_GOALS,
    _extract_asr,
    _format_asr,
    _normalize_attack_type,
    _provider_endpoint,
)
from hackagent.cli.commands.scan.quick import run_quick_scan

__all__ = [
    "DEFAULT_ATTACK_TYPE",
    "DEFAULT_GOALS",
    "run_quick_scan",
    "scan",
    "_extract_asr",
    "_format_asr",
    "_normalize_attack_type",
    "_provider_endpoint",
]
