# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attacks view package.

Router module: re-exports :class:`AttacksTab` and the module-level helpers so
that ``hackagent.cli.tui.views.attacks`` keeps its historical import surface.

Layout:
    - ``tab.py``: the ``AttacksTab`` widget (lifecycle, events, form reset).
    - ``layout.py``: ``compose`` (widget tree).
    - ``form.py``: strategy config form rendering / collection / prefill.
    - ``runner.py``: execute-button validation and worker launch.
    - ``executor.py``: the background attack worker.
    - ``helpers.py``: module-level helpers and constants.
"""

from hackagent.cli.tui.views.attacks.helpers import (
    _AGENT_TYPE_CHOICES,
    _CFG_PREFIX,
    _ENDPOINT_OPTIONAL_AGENT_TYPES,
    _default_campaign_attack_keys,
    _escape,
    _field_widget_id,
)
from hackagent.cli.tui.views.attacks.tab import AttacksTab

__all__ = [
    "AttacksTab",
    "_AGENT_TYPE_CHOICES",
    "_CFG_PREFIX",
    "_ENDPOINT_OPTIONAL_AGENT_TYPES",
    "_default_campaign_attack_keys",
    "_escape",
    "_field_widget_id",
]
