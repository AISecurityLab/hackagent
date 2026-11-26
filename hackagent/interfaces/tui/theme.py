# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The TUI's look: its Textual theme, built from the palette
(:func:`hackagent_theme`), and the brand reds its frame is drawn in
(:func:`css_variables`). What a result is called, and its colour, is the
palette's and :mod:`hackagent.interfaces.results`', as everywhere else.
"""

from typing import Any

from hackagent.interfaces.palette import BRAND

# --------------------------------------------------------------------------
# Brand palette
# --------------------------------------------------------------------------

BRAND_RED = BRAND
"""Primary brand red — borders, logo, accents: the palette's brand colour."""

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


def hackagent_theme() -> Any:
    """The TUI's Textual theme: Textual's dark one, its accent, success,
    warning and error taken from the palette, so a focus ring, a check and
    an error look as they do on the command line."""
    from textual.theme import BUILTIN_THEMES, Theme

    from hackagent.interfaces.palette import ACCENT, FAILED, PASSED, WARNING

    base = BUILTIN_THEMES["textual-dark"]
    return Theme(
        name="hackagent",
        primary=base.primary,
        secondary=base.secondary,
        accent=ACCENT,
        success=PASSED,
        warning=WARNING,
        error=FAILED,
        foreground=base.foreground,
        dark=True,
    )


def css_variables() -> dict[str, str]:
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


__all__ = ["css_variables", "hackagent_theme"]
