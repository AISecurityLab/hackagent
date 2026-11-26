# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The logo on the command line, as the TUI's welcome screen shows it: in
the brand colour, the tagline under it."""

from __future__ import annotations

from typing import Optional

from rich.console import Console, Group
from rich.text import Text

from hackagent._version import get_version
from hackagent.interfaces.brand import BANNER, TAGLINE
from hackagent.interfaces.palette import console as themed

#: The logo, kept under this name for what imports it from here.
HACKAGENT_BANNER = BANNER


def splash() -> Group:
    """The logo and, under it, the version and the tagline."""
    return Group(
        Text(BANNER, style="brand"),
        Text.from_markup(f"[secondary]v{get_version()} · {TAGLINE}[/secondary]"),
    )


def display_hackagent_splash(console: Optional[Console] = None) -> None:
    """Print :func:`splash`, then a blank line."""
    console = console or themed()
    console.print(splash())
    console.print()


__all__ = ["HACKAGENT_BANNER", "display_hackagent_splash", "splash"]
