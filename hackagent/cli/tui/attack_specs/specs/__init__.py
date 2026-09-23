# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Per-technique attack configuration specs.

Importing this package registers every spec, in the declaration order
below. That order is user-visible: it drives the TUI strategy selector and
the default evaluation-campaign selection.

To add a new attack to the TUI, drop a module here exposing a ``SPEC``
:class:`~hackagent.cli.tui.attack_specs.types.AttackConfigSpec` and append it
to ``_SPEC_MODULES``. The technique must already have a primary category in
:mod:`hackagent.catalog.taxonomy`.
"""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.registry import register
from hackagent.cli.tui.attack_specs.specs import (
    advprefix,
    autodan_turbo,
    baseline,
    bon,
    cipherchat,
    fc,
    flipattack,
    h4rm3l,
    mml,
    pair,
    pap,
    static_template,
    tap,
    tfc,
    tool_output_ipi,
)

_SPEC_MODULES = (
    advprefix,
    baseline,
    static_template,
    pair,
    autodan_turbo,
    flipattack,
    tap,
    bon,
    cipherchat,
    h4rm3l,
    pap,
    fc,
    tfc,
    mml,
    tool_output_ipi,
)

for _module in _SPEC_MODULES:
    register(_module.SPEC)

__all__ = ["_SPEC_MODULES"]
