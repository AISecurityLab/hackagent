# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Playwright helpers for the ``web`` provider.

Shared utilities for driving a real Chromium: ensuring the browser binary is
installed (fetched on first use), and locating the chat input / send button on a
loaded page. The ``web`` provider
(:mod:`hackagent.router.providers.web`) uses these to type prompts into a live
chat widget and read the replies.

Playwright is a core dependency. The Chromium *binary* it drives is not a pip
package, so it is fetched on first use (or pre-fetch with ``playwright install
chromium``).
"""

import os
import subprocess
import sys

from hackagent.logger import get_logger

logger = get_logger(__name__)


class BrowserScanError(Exception):
    """Raised when the browser can't run (e.g. Playwright/Chromium not installed)."""


# CSS selectors, tried in order, for the message input and the send control.
_INPUT_SELECTORS = (
    "textarea",
    "input[type=text]",
    "input[type=search]",
    "[contenteditable=true]",
    "[role=textbox]",
)
_SEND_SELECTORS = (
    "button[type=submit]",
    "button[aria-label*=send i]",
    "button[title*=send i]",
    "[data-testid*=send i]",
    "[class*=send i][role=button]",
)

_PACKAGE_MISSING_MSG = (
    "Playwright is required for the web provider but is not importable. "
    "Reinstall hackagent, or:  pip install playwright"
)


def _get_playwright():
    """Return ``(sync_playwright, True)`` or ``(None, False)`` if unavailable."""
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright, True
    except ImportError:
        return None, False


def chromium_installed() -> bool:
    """True if Playwright's Chromium browser binary is present on disk.

    Checks the expected executable path without launching a browser, so it's
    cheap to call on every run. Returns False if Playwright isn't importable.
    """
    _, available = _get_playwright()
    if not available:
        return False
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            path = p.chromium.executable_path
        return bool(path) and os.path.exists(path)
    except Exception:
        # Playwright raises when the browser was never downloaded.
        return False


def install_chromium(timeout: int = 900) -> None:
    """Download Playwright's Chromium via ``python -m playwright install chromium``.

    Output streams to the terminal so the user sees download progress. Raises
    :class:`BrowserScanError` with a manual-command hint on any failure.
    """
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    manual = "run it manually:  playwright install chromium"
    try:
        proc = subprocess.run(cmd, timeout=timeout)
    except FileNotFoundError as e:
        raise BrowserScanError(
            f"Could not invoke Playwright to install Chromium; {manual}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise BrowserScanError(
            f"Timed out downloading Chromium after {timeout}s; {manual}"
        ) from e
    if proc.returncode != 0:
        raise BrowserScanError(
            f"Failed to download Chromium (exit {proc.returncode}); {manual}"
        )


def ensure_chromium(*, auto_install: bool = True, console=None) -> None:
    """Ensure Playwright + its Chromium are ready for the ``web`` provider.

    Raises :class:`BrowserScanError` if Playwright isn't installed, or if
    Chromium is missing and ``auto_install`` is False. When ``auto_install`` is
    True and Chromium is missing, downloads it (announcing via ``console`` if
    given). A no-op when everything is already present.
    """
    _, available = _get_playwright()
    if not available:
        raise BrowserScanError(_PACKAGE_MISSING_MSG)
    if chromium_installed():
        return
    if not auto_install:
        raise BrowserScanError(
            "Playwright's Chromium browser is not installed. Run:  "
            "playwright install chromium"
        )
    if console is not None:
        console.print(
            "[dim]Chromium isn't installed — downloading it once (~150 MB)…[/dim]"
        )
    logger.info("downloading Chromium for the web provider (one-time)")
    install_chromium()


def _type_into(handle, text: str) -> None:
    """Fill an input/textarea, falling back to typing for contenteditable."""
    try:
        handle.fill(text)
        return
    except Exception:
        pass
    handle.click()
    handle.type(text)


def _find_input(page, selector=None):
    """Locate the first visible, editable chat input across all frames.

    Args:
        page: the Playwright page.
        selector: an explicit CSS selector to use instead of the built-in
            heuristics (for sites where the heuristics miss the box).

    Returns ``(handle, frame)`` or ``(None, None)``.
    """
    selectors = (selector,) if selector else _INPUT_SELECTORS
    for frame in page.frames:
        for sel in selectors:
            try:
                handles = frame.query_selector_all(sel)
            except Exception:
                continue
            for h in handles:
                try:
                    if h.is_visible() and h.is_editable():
                        return h, frame
                except Exception:
                    continue
    # With an explicit selector, accept a visible (not necessarily "editable")
    # match too — contenteditable wrappers sometimes report is_editable False.
    if selector:
        for frame in page.frames:
            try:
                h = frame.query_selector(selector)
            except Exception:
                continue
            try:
                if h is not None and h.is_visible():
                    return h, frame
            except Exception:
                continue
    return None, None


def _find_send_button(frame):
    """Locate a plausible send button within ``frame``; ``None`` if absent."""
    for selector in _SEND_SELECTORS:
        try:
            h = frame.query_selector(selector)
        except Exception:
            continue
        if h is not None:
            try:
                if h.is_visible():
                    return h
            except Exception:
                continue
    return None
