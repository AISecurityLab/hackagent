# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The example campaigns as one tree, the same in the TUI's picker and in
``hackagent examples list``.

The folders they are in, every one open, folders first and both in name
order; each campaign on one line with what it needs running besides
HackAgent, and what it is for on the next. :func:`example_rows` gives each
row as Rich text in the palette's colours: the TUI turns them into choices,
the CLI prints them.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from rich.text import Text

from hackagent.interfaces.palette import ACCENT, NAME, SECONDARY, UNDECIDED

#: How the tree is drawn: its guides, folders, the campaigns in them, what
#: each campaign is for, and what it needs.
GUIDE, FOLDER, CAMPAIGN, ABOUT, NEEDS = (
    SECONDARY,
    f"bold {ACCENT}",
    f"bold {NAME}",
    SECONDARY,
    UNDECIDED,
)


def example_rows(examples: Mapping[str, Path]) -> list[tuple[Optional[str], Text]]:
    """Each row of the tree: ``(name, text)`` for a campaign, ``(None,
    text)`` for a folder, which is a heading and cannot be chosen."""
    from hackagent import examples as catalog

    nested: dict[str, Any] = {}
    for name in examples:
        *folders, leaf = name.split("/")
        level = nested
        for folder in folders:
            level = level.setdefault(folder, {})
        level[leaf] = name

    rows: list[tuple[Optional[str], Text]] = []

    def add(level: Mapping[str, Any], indent: str, top: bool) -> None:
        folders = sorted(k for k, v in level.items() if isinstance(v, dict))
        leaves = sorted(k for k, v in level.items() if not isinstance(v, dict))
        entries = [(folder, True) for folder in folders] + [
            (leaf, False) for leaf in leaves
        ]
        for position, (entry, is_folder) in enumerate(entries):
            last = position == len(entries) - 1
            branch = "" if top else ("└─ " if last else "├─ ")
            below = indent + ("" if top else ("   " if last else "│  "))
            if is_folder:
                rows.append(
                    (
                        None,
                        Text.assemble((indent + branch, GUIDE), (f"{entry}/", FOLDER)),
                    )
                )
                add(level[entry], below, False)
                continue
            name = level[entry]
            needed = catalog.needs(name)
            rows.append(
                (
                    name,
                    Text.assemble(
                        (indent + branch, GUIDE),
                        (entry, CAMPAIGN),
                        (f"  ({needed})" if needed else "", NEEDS),
                        "\n",
                        (below, GUIDE),
                        (catalog.describe(examples[name]), ABOUT),
                    ),
                )
            )

    add(nested, "", True)
    return rows


__all__ = ["example_rows"]
