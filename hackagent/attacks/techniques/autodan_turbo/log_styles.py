# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Colored logging helpers for AutoDAN-Turbo phases."""

import os


_PHASE_COLORS = {
    "PIPELINE": "97",  # bright white
    "WARMUP": "96",  # bright cyan
    "LIFELONG": "95",  # bright magenta
    "EVALUATION": "92",  # bright green
    "GENERATE": "36",  # cyan
    "TARGET": "33",  # yellow
    "SCORING": "94",  # bright blue
    "SUMMARIZE": "93",  # bright yellow
    "FINAL": "32",  # green
}


def _color_enabled() -> bool:
    """Check whether ANSI coloring is enabled for logs.

    Returns:
        ``True`` unless ``NO_COLOR=1`` is set in environment.
    """
    return os.environ.get("NO_COLOR") != "1"


def _apply_color(text: str, color: str) -> str:
    """Wrap text with ANSI color code when coloring is enabled.

    Args:
        text: Plain message.
        color: ANSI color code as string (e.g. ``"96"``).

    Returns:
        Colored text or original text when colors are disabled.
    """
    if not _color_enabled():
        return text
    return f"\x1b[{color}m{text}\x1b[0m"


def phase_prefix(phase: str) -> str:
    """Build colored bracket prefix for a phase tag.

    Args:
        phase: Phase identifier (warmup/lifelong/evaluation/etc.).

    Returns:
        Colored prefix like ``[WARMUP]``.
    """
    name = (phase or "PIPELINE").upper()
    color = _PHASE_COLORS.get(name, "37")
    return _apply_color(f"[{name}]", color)


def format_phase_message(phase: str, message: str) -> str:
    """Format a full colored phase-scoped log line.

    Args:
        phase: Phase identifier.
        message: Message body to append after phase tag.

    Returns:
        Colored string ``[PHASE] message``.
    """
    name = (phase or "PIPELINE").upper()
    color = _PHASE_COLORS.get(name, "37")
    return _apply_color(f"[{name}] {message}", color)


def phase_separator(phase: str, title: str = "") -> str:
    """Create a colored visual separator for phase boundaries.

    Args:
        phase: Phase identifier.
        title: Optional label appended after phase name.

    Returns:
        Decorative separator line for logs.
    """
    sep = "-" * 22
    body = f"{sep} {phase.upper()}"
    if title:
        body += f" :: {title}"
    body += f" {sep}"
    color = _PHASE_COLORS.get(phase.upper(), "37")
    return _apply_color(body, color)
