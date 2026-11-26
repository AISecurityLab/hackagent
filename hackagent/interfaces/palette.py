# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The colours of HackAgent, wherever it is shown: the log in a terminal and
in the TUI's run view, the TUI's results and builder, every CLI command.
Nothing else names a colour.

**Defender polarity.** A result is coloured from the point of view of the
target, never the attacker: a jailbreak is red, a mitigated goal green, and
nothing an attacker achieved is ever green. A check the target or the panel
passed is green too, one that failed red; an error is yellow, like a
warning, and what is not decided yet is dim.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.theme import Theme

#: The logo's colour, on the welcome screen and on the command line.
BRAND = "#ff0000"

#: A log line's level name, by severity.
LEVEL_STYLES: dict[str, str] = {
    "DEBUG": "dim",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold reverse red",
}

#: A verdict's colour, by its word: an attempt's, a goal's, a check's.
VERDICT_STYLES: dict[str, str] = {
    "jailbroken": "bold red",
    "mitigated": "green",
    "failed": "red",
    "unreachable": "red",
    "error": "yellow",
    "unresolved": "dim",
    "pending": "dim",
    "no verdict": "dim",
}

#: A check that passed, failed, or was not decided (a judge audit).
PASSED, FAILED, UNDECIDED = "green", "red", "yellow"

#: What is said in passing: the time of a log line, the steps it is nested
#: in, a hint.
SECONDARY = "dim"

#: A heading or a group (a folder, a judge audit, an action offered), and a
#: thing of the kind listed (an example campaign).
ACCENT, NAME = "cyan", "#c9a0ff"

#: The tag of an attack in the log, one per attack for the whole run.
TAG_STYLES: tuple[str, ...] = (
    "cyan",
    "magenta",
    "blue",
    "yellow",
    "bright_cyan",
    "bright_magenta",
    "bright_blue",
    "bright_yellow",
)


#: Something worth knowing that is not a failure.
WARNING = "yellow"

#: The same colours by what they mean, for a CLI command's markup and tables
#: (``[passed]✓[/passed] saved``), so no command picks a colour of its own.
THEME = Theme(
    {
        "brand": f"bold {BRAND}",
        "heading": f"bold {ACCENT}",
        "accent": ACCENT,
        "name": NAME,
        "passed": PASSED,
        "failed": FAILED,
        "warning": WARNING,
        "secondary": SECONDARY,
    }
)


def console(**options: object) -> Console:
    """A Rich console that knows :data:`THEME`'s names."""
    return Console(theme=THEME, **options)  # type: ignore[arg-type]


def paint(text: str, style: str) -> str:
    """``text``, escaped, as Rich markup in ``style`` (as is without one)."""
    said = escape(text)
    return f"[{style}]{said}[/{style}]" if style else said


def verdict(word: str) -> str:
    """A verdict's word in its colour, as Rich markup."""
    return paint(word, VERDICT_STYLES.get(word, ""))


__all__ = [
    "ACCENT",
    "BRAND",
    "FAILED",
    "LEVEL_STYLES",
    "NAME",
    "PASSED",
    "SECONDARY",
    "TAG_STYLES",
    "THEME",
    "UNDECIDED",
    "VERDICT_STYLES",
    "WARNING",
    "console",
    "paint",
    "verdict",
]
