# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Eval Commands

Evaluate AI agent security.

``hackagent eval`` without a strategy runs the evaluation campaign.
``hackagent eval <strategy>`` runs a specific attack strategy.

Router module: re-exports ``eval_cmd`` and the shared helpers so that
``hackagent.cli.commands.attack`` keeps its historical import surface.

Layout:
    - ``catalog.py``: the ``ATTACK_CATALOG`` strategy metadata.
    - ``options.py``: the ``_common_attack_options`` click decorator.
    - ``config.py``: pure config building (``parse_config``).
    - ``runner.py``: shared execution path (``run_attack``).
    - ``display.py``: Rich rendering helpers.
    - ``group.py``: the ``eval`` click group.
    - ``strategies.py``: the per-strategy subcommands (generated).
    - ``chain.py`` / ``info.py``: the ``chain``, ``list`` and ``info`` commands.
"""

from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG
from hackagent.cli.commands.attack.config import (
    _build_attack_config,
    _build_guardrail_config,
    _parse_goals,
    _summarize_goals_source,
    build_guardrail_config,
    parse_config,
)
from hackagent.cli.commands.attack.display import (
    _display_advprefix_info,
    _display_attack_results,
    _display_attack_summary,
    _display_generic_attack_info,
)
from hackagent.cli.commands.attack.group import eval_cmd
from hackagent.cli.commands.attack.options import _common_attack_options
from hackagent.cli.commands.attack.runner import _run_attack_command, run_attack

# Importing these modules registers their commands on ``eval_cmd``.
from hackagent.cli.commands.attack import chain as _chain  # noqa: F401
from hackagent.cli.commands.attack import info as _info  # noqa: F401
from hackagent.cli.commands.attack import strategies as _strategies  # noqa: F401

__all__ = [
    "ATTACK_CATALOG",
    "eval_cmd",
    "parse_config",
    "run_attack",
    "build_guardrail_config",
    "_build_attack_config",
    "_build_guardrail_config",
    "_common_attack_options",
    "_display_advprefix_info",
    "_display_attack_results",
    "_display_attack_summary",
    "_display_generic_attack_info",
    "_parse_goals",
    "_run_attack_command",
    "_summarize_goals_source",
]
