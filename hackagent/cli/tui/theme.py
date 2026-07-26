# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TUI Theme and Terminology

Single source of truth for the HackAgent TUI's colour palette and for the
vocabulary used to describe evaluation outcomes and run states.

Two rules keep the interface coherent:

1. **Defender polarity.** A result is described from the point of view of the
   agent under test, never the attacker. A jailbreak that got through is a
   ``Vulnerable`` result and is always red; a jailbreak that was refused is a
   ``Mitigated`` result and is always green. "Successful attack" wording (which
   would paint a vulnerability green) is not used anywhere in the TUI.
2. **One palette.** Brand colours live here so views and CSS never re-invent
   their own shade of red.
"""

from dataclasses import dataclass
from typing import Any

# --------------------------------------------------------------------------
# Brand palette
# --------------------------------------------------------------------------

BRAND_RED = "#ff0000"
"""Primary brand red — borders, logo, accents."""

BRAND_RED_DARK = "#8b0000"
"""Dark red — headers, active tabs, primary buttons."""

BRAND_RED_DARKER = "#2b0000"
"""Darkest red — footer and inactive tab strip backgrounds."""

BRAND_RED_HOVER = "#5b0000"
"""Mid red — hover and cursor highlights."""

TEXT_ON_BRAND = "#ffffff"
"""Foreground colour on top of any brand red background."""

TEXT_MUTED = "#cccccc"
"""Foreground colour for de-emphasised text on dark backgrounds."""


def css_variables() -> dict:
    """Return the brand palette as Textual CSS variables.

    The returned names are usable in stylesheets as ``$brand``,
    ``$brand-dark``, ``$brand-darker``, ``$brand-hover``, ``$brand-text`` and
    ``$brand-text-muted``.
    """
    return {
        "brand": BRAND_RED,
        "brand-dark": BRAND_RED_DARK,
        "brand-darker": BRAND_RED_DARKER,
        "brand-hover": BRAND_RED_HOVER,
        "brand-text": TEXT_ON_BRAND,
        "brand-text-muted": TEXT_MUTED,
    }


# --------------------------------------------------------------------------
# Evaluation outcomes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """Presentation vocabulary for a single evaluation outcome.

    Attributes:
        key: Stable identifier, also used as the CSS modifier class.
        label: Human-readable label shown to the user.
        color: Rich colour name used to render the label.
        icon: Emoji shown next to the label.
    """

    key: str
    label: str
    color: str
    icon: str

    def render(self) -> str:
        """Return the outcome as Rich markup, e.g. ``[red]🔓 Vulnerable[/red]``."""
        return f"[{self.color}]{self.icon} {self.label}[/{self.color}]"

    @property
    def css_class(self) -> str:
        """Return the CSS modifier class for this outcome."""
        return f"-{self.key}"


VULNERABLE = Outcome("vulnerable", "Vulnerable", "red", "🔓")
"""The attack got through: the target agent is vulnerable."""

MITIGATED = Outcome("mitigated", "Mitigated", "green", "🛡")
"""The attack was refused or blocked by the target agent."""

ERRORED = Outcome("errored", "Error", "yellow", "⚠")
"""The attempt could not be evaluated because something went wrong."""

NOT_EVALUATED = Outcome("not-evaluated", "Not Evaluated", "dim", "⏳")
"""No verdict is available yet."""

OUTCOMES = (VULNERABLE, MITIGATED, ERRORED, NOT_EVALUATED)


def classify_evaluation_status(status: Any) -> Outcome:
    """Map a raw evaluation status onto the TUI outcome vocabulary.

    Args:
        status: An ``EvaluationStatus`` enum member, a string, or anything
            coercible to a string. ``None`` is treated as unevaluated.

    Returns:
        The matching :class:`Outcome`.
    """
    if status is None:
        return NOT_EVALUATED

    raw = getattr(status, "value", status)
    text = str(raw).upper()

    if "JAILBREAK" in text:
        if "SUCCESSFUL" in text:
            return VULNERABLE
        if "FAILED" in text:
            return MITIGATED
    if "ERROR" in text:
        return ERRORED
    return NOT_EVALUATED


# --------------------------------------------------------------------------
# Run states
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RunState:
    """Presentation vocabulary for a run's lifecycle state."""

    key: str
    label: str
    color: str
    icon: str

    def render(self) -> str:
        """Return the state as Rich markup."""
        return f"[{self.color}]{self.icon} {self.label}[/{self.color}]"

    def render_icon(self) -> str:
        """Return just the coloured icon, for compact table cells."""
        return f"[{self.color}]{self.icon}[/{self.color}]"


RUN_COMPLETED = RunState("completed", "Completed", "green", "✅")
RUN_RUNNING = RunState("running", "Running", "cyan", "🔄")
RUN_FAILED = RunState("failed", "Failed", "red", "❌")
RUN_PENDING = RunState("pending", "Pending", "yellow", "⏳")
RUN_UNKNOWN = RunState("unknown", "Unknown", "dim", "❓")

RUN_STATES = (RUN_COMPLETED, RUN_RUNNING, RUN_FAILED, RUN_PENDING, RUN_UNKNOWN)


def classify_run_status(status: Any) -> RunState:
    """Map a raw run status onto the TUI run-state vocabulary.

    Args:
        status: A status enum member, a string, or anything coercible to a
            string. ``None`` is treated as unknown.

    Returns:
        The matching :class:`RunState`.
    """
    if status is None:
        return RUN_UNKNOWN

    raw = getattr(status, "value", status)
    text = str(raw).upper()

    for state in (RUN_COMPLETED, RUN_RUNNING, RUN_FAILED, RUN_PENDING):
        if state.key.upper() == text:
            return state
    return RUN_UNKNOWN
