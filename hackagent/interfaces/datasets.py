# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The dataset presets as one list, the same in the TUI's Datasets screen
and in ``hackagent datasets list``.

Each preset by its name alone. What it is, where it is loaded from and
the rest is said beside the list in the TUI and by ``hackagent datasets
show``, as the example campaigns are listed (:mod:`.examples`).
:func:`preset_rows` gives each row as Rich text in the palette's colours:
the TUI turns them into choices, the CLI prints them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rich.text import Text

from hackagent.interfaces.examples import CAMPAIGN


def source_of(config: Mapping[str, Any]) -> str:
    """Where a preset's goals come from: a Hugging Face path, a URL, a file."""
    return str(config.get("path") or config.get("url") or "—")


def preset_rows(presets: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, Text]]:
    """Each preset, in name order: ``(name, text)``."""
    return [
        (
            name,
            Text(name, style=CAMPAIGN),
        )
        for name, config in sorted(presets.items())
    ]


#: How a preset is named in a campaign, to say where to use it.
def in_a_campaign(name: str) -> str:
    return f"dataset: {{source: {{type: preset, name: {name}}}}}"


__all__ = ["in_a_campaign", "preset_rows", "source_of"]
