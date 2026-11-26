# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The colours of HackAgent, wherever it is shown: the log in a terminal and
in the TUI's run view, the TUI's results and builder, every CLI command.
Nothing else names a colour.

**Exact colours.** Every colour is a value, never a name: a name like
``magenta`` is drawn as each terminal's theme, and the TUI's, decide (one
draws it purple, another pinkish red), so the same attack would look
different in the CLI and the TUI, and like a jailbreak in one of them. The
TUI's own theme (:func:`~hackagent.interfaces.tui.theme.hackagent_theme`)
is built from these too.

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

#: The colours, by hue. A verdict, a check and a log level take theirs from
#: here by meaning: green holds, red failed, yellow is worth knowing.
GREEN, RED, YELLOW, CYAN, VIOLET = "#5fd75f", "#ff5f5f", "#ffd75f", "#5fd7ff", "#c9a0ff"
SAND = "#d7af87"

#: A log line's level name, by severity.
LEVEL_STYLES: dict[str, str] = {
    # Sand: not the time's gray it sits beside, nor any verdict's colour.
    "DEBUG": SAND,
    "INFO": GREEN,
    "WARNING": YELLOW,
    "ERROR": f"bold {RED}",
    "CRITICAL": f"bold reverse {RED}",
}

#: A verdict's colour, by its word: an attempt's, a goal's, a check's.
VERDICT_STYLES: dict[str, str] = {
    "jailbroken": f"bold {RED}",
    "mitigated": GREEN,
    "failed": RED,
    "unreachable": RED,
    "error": YELLOW,
    "unresolved": "dim",
    "pending": "dim",
    "no verdict": "dim",
}

#: A check that passed, failed, or was not decided (a judge audit).
PASSED, FAILED, UNDECIDED = GREEN, RED, YELLOW

#: What is said in passing: the time of a log line, the steps it is nested
#: in, a hint.
SECONDARY = "dim"

#: A heading or a group (a folder, a judge audit, an action offered), and a
#: thing of the kind listed (an example campaign).
ACCENT, NAME = CYAN, VIOLET

#: The tag of an attack in the log, one per attack for the whole run. None
#: is red, green or yellow, which say how something went: an attack's name
#: must never read as a verdict.
TAG_STYLES: tuple[str, ...] = (
    "#5fd7ff",  # cyan
    "#87afff",  # blue
    "#af87ff",  # violet
    "#d787d7",  # orchid
    "#87d7d7",  # teal
    "#afd7ff",  # sky
)


#: Something worth knowing that is not a failure.
WARNING = YELLOW

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
    """A Rich console that knows :data:`THEME`'s names, and colours nothing
    on its own: Rich would pick out numbers and ids (the ``3`` of
    ``gemma3:4b``) in colours the palette never chose."""
    options.setdefault("highlight", False)
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
