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

# Selectors for a collapsed chat widget's launcher button. Many sites hide the
# bot behind a floating bubble (often in an iframe) — clicking it reveals the
# input. Vendor-specific / launcher-class selectors come first (low false
# positive), generic aria/title hints last. Tried in order across all frames.
_LAUNCHER_SELECTORS = (
    # Known vendors
    ".intercom-launcher",
    "[class*=intercom-launcher i]",
    "#launcher",  # Zendesk / Zopim
    "[class*=zEWidget-launcher i]",
    "#chat-widget-container",  # LiveChat
    "#drift-frame-controller",
    "[class*=drift-widget i]",
    "#fc_frame",  # Freshchat
    "[class*=crisp-client i] a",
    "[class*=tidio i]",
    # Generic launcher / chat bubble buttons
    "[class*=launcher i]",
    "[id*=launcher i]",
    "button[class*=chat i]",
    "[class*=chat i][role=button]",
    "[id*=chat i][role=button]",
    "[class*=chat-bubble i]",
    "[class*=chatbot i][role=button]",
    # "open the widget" style buttons (e.g. CSI's Camilla:
    # class="camilla-widget-open-button" role="button")
    "[class*=widget-open i]",
    "[class*=open-button i]",
    "[class*=widget i][role=button]",
    "[role=button][class*=assist i]",
    # aria/title hints (broadest — last)
    "[aria-label*=chat i]",
    "[aria-label*=assistant i]",
    "[aria-label*=assistenza i]",  # Italian
    "[title*=chat i]",
    "[title*=assistant i]",
)

# Cookie/consent "accept" controls. A consent overlay commonly sits on top of
# the page and intercepts clicks (incl. the chat launcher), so we dismiss it
# first. Known CMP buttons (precise) first, then Playwright :has-text() matches
# on unambiguous accept phrases (EN + IT). :has-text() is case-insensitive
# substring, so 'Accetta' also matches 'ACCETTA TUTTI'.
_CONSENT_SELECTORS = (
    "#onetrust-accept-btn-handler",  # OneTrust
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",  # Cookiebot
    "#CybotCookiebotDialogBodyButtonAccept",
    "#didomi-notice-agree-button",  # Didomi
    "[data-testid=uc-accept-all-button]",  # Usercentrics
    ".iubenda-cs-accept-btn",  # Iubenda
    "#iubenda-cs-accept-btn",
    ".cc-allow",  # cookieconsent
    ".cookie-accept",
    "[id*=cookie i] button:has-text('Accetta')",
    "[class*=cookie i] button:has-text('Accetta')",
    "button:has-text('Accetta tutt')",
    "button:has-text('Acconsento')",
    "button:has-text('Consenti tutt')",
    "button:has-text('Ho capito')",
    "button:has-text('Accept all')",
    "button:has-text('Accept cookies')",
    "button:has-text('Accept & close')",
    "button:has-text('I agree')",
    "button:has-text('Got it')",
    "[role=button]:has-text('Accetta tutt')",
    "a:has-text('Accetta tutt')",
)


def _click_element(handle, *, timeout: int = 2000) -> bool:
    """Click an element robustly: scroll in, normal click, DOM-click fallback.

    Returns True if either the actionable click or the direct DOM dispatch
    succeeded. The DOM fallback (``el.click()``) bypasses pointer-event
    interception (overlays) and actionability gating (``<div role=button>``).
    """
    try:
        handle.scroll_into_view_if_needed(timeout=1000)
    except Exception:
        pass
    try:
        handle.click(timeout=timeout)
        return True
    except Exception:
        try:
            handle.evaluate("el => el.click()")
            return True
        except Exception:
            return False


def _dismiss_consent(page) -> bool:
    """Accept/dismiss a cookie-consent banner so it can't intercept clicks.

    Clicks the first visible known-CMP / accept-phrase control found across all
    frames. Best-effort and idempotent; returns True if it clicked something.
    """
    for frame in page.frames:
        for sel in _CONSENT_SELECTORS:
            try:
                handles = frame.query_selector_all(sel)
            except Exception:
                continue
            for h in handles:
                try:
                    if not h.is_visible():
                        continue
                    if _click_element(h):
                        return True
                except Exception:
                    continue
    return False


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


def _open_chat_launcher(page, selector=None) -> bool:
    """Click a likely chat-launcher to reveal a collapsed widget.

    Many sites render no chat input until the user clicks a floating bubble
    (frequently inside an iframe). This clicks the first visible launcher it
    finds so the caller can then poll for the now-revealed input.

    Args:
        page: the Playwright page.
        selector: an explicit launcher CSS selector to use instead of the
            built-in heuristics.

    Returns True if it clicked something, else False.
    """
    selectors = (selector,) if selector else _LAUNCHER_SELECTORS
    for frame in page.frames:
        for sel in selectors:
            try:
                handles = frame.query_selector_all(sel)
            except Exception:
                continue
            for h in handles:
                try:
                    if not h.is_visible():
                        continue
                    # Avoid following navigational links that merely mention
                    # "chat" — only click buttons / non-navigating controls.
                    href = (h.get_attribute("href") or "").strip()
                    if href and not href.startswith("#") and selector is None:
                        continue
                    # Robust click (covers overlay interception / <div role=button>).
                    if _click_element(h):
                        return True
                except Exception:
                    continue
    return False


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
