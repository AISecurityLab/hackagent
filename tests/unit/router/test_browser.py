# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Playwright helpers used by the ``web`` provider.

Playwright itself is never launched here — these cover the input/send-button
location helpers (with mocked frames) and the Chromium ensure/install flow.
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.router.discovery.browser import (
    BrowserScanError,
    _find_input,
    _find_send_button,
    chromium_installed,
    ensure_chromium,
    install_chromium,
)

logging.disable(logging.CRITICAL)


class TestFindInput(unittest.TestCase):
    def _frame_with(self, handle, selector_match=None):
        frame = MagicMock()
        if selector_match is None:
            frame.query_selector_all.return_value = [handle]
        else:
            frame.query_selector_all.side_effect = (
                lambda sel: [handle] if sel == selector_match else []
            )
        return frame

    def test_heuristic_finds_visible_editable(self):
        handle = MagicMock()
        handle.is_visible.return_value = True
        handle.is_editable.return_value = True
        frame = self._frame_with(handle)
        page = MagicMock()
        page.frames = [frame]
        h, f = _find_input(page)
        self.assertIs(h, handle)

    def test_explicit_selector_used(self):
        handle = MagicMock()
        handle.is_visible.return_value = True
        handle.is_editable.return_value = True
        frame = self._frame_with(handle, selector_match="#box")
        page = MagicMock()
        page.frames = [frame]
        h, f = _find_input(page, "#box")
        self.assertIs(h, handle)
        frame.query_selector_all.assert_called_with("#box")

    def test_explicit_selector_visible_only_fallback(self):
        # contenteditable wrappers can report is_editable() False; an explicit
        # selector still accepts a visible match via the second pass.
        handle = MagicMock()
        handle.is_visible.return_value = True
        handle.is_editable.return_value = False
        frame = MagicMock()
        frame.query_selector_all.return_value = [handle]
        frame.query_selector.return_value = handle
        page = MagicMock()
        page.frames = [frame]
        h, f = _find_input(page, "#box")
        self.assertIs(h, handle)

    def test_returns_none_when_nothing_matches(self):
        frame = MagicMock()
        frame.query_selector_all.return_value = []
        page = MagicMock()
        page.frames = [frame]
        self.assertEqual(_find_input(page), (None, None))


class TestFindSendButton(unittest.TestCase):
    def test_finds_visible_button(self):
        btn = MagicMock()
        btn.is_visible.return_value = True
        frame = MagicMock()
        frame.query_selector.side_effect = (
            lambda sel: btn if sel == "button[type=submit]" else None
        )
        self.assertIs(_find_send_button(frame), btn)

    def test_none_when_absent(self):
        frame = MagicMock()
        frame.query_selector.return_value = None
        self.assertIsNone(_find_send_button(frame))


class TestEnsureChromium(unittest.TestCase):
    def test_package_missing_raises(self):
        with patch(
            "hackagent.router.discovery.browser._get_playwright",
            return_value=(None, False),
        ):
            with self.assertRaises(BrowserScanError):
                ensure_chromium()

    def test_already_installed_is_noop(self):
        with (
            patch(
                "hackagent.router.discovery.browser._get_playwright",
                return_value=(object(), True),
            ),
            patch(
                "hackagent.router.discovery.browser.chromium_installed",
                return_value=True,
            ),
            patch(
                "hackagent.router.discovery.browser.install_chromium"
            ) as mock_install,
        ):
            ensure_chromium()
            mock_install.assert_not_called()

    def test_missing_without_auto_install_raises(self):
        with (
            patch(
                "hackagent.router.discovery.browser._get_playwright",
                return_value=(object(), True),
            ),
            patch(
                "hackagent.router.discovery.browser.chromium_installed",
                return_value=False,
            ),
        ):
            with self.assertRaises(BrowserScanError):
                ensure_chromium(auto_install=False)

    def test_missing_with_auto_install_downloads(self):
        with (
            patch(
                "hackagent.router.discovery.browser._get_playwright",
                return_value=(object(), True),
            ),
            patch(
                "hackagent.router.discovery.browser.chromium_installed",
                return_value=False,
            ),
            patch(
                "hackagent.router.discovery.browser.install_chromium"
            ) as mock_install,
        ):
            ensure_chromium(auto_install=True)
            mock_install.assert_called_once()


class TestInstallChromium(unittest.TestCase):
    def test_success(self):
        proc = MagicMock(returncode=0)
        with patch(
            "hackagent.router.discovery.browser.subprocess.run", return_value=proc
        ) as mock_run:
            install_chromium()
            argv = mock_run.call_args.args[0]
            self.assertEqual(argv[-3:], ["playwright", "install", "chromium"])

    def test_nonzero_exit_raises(self):
        proc = MagicMock(returncode=1)
        with patch(
            "hackagent.router.discovery.browser.subprocess.run", return_value=proc
        ):
            with self.assertRaises(BrowserScanError):
                install_chromium()

    def test_missing_executable_raises(self):
        with patch(
            "hackagent.router.discovery.browser.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            with self.assertRaises(BrowserScanError):
                install_chromium()

    def test_chromium_installed_false_without_playwright(self):
        with patch(
            "hackagent.router.discovery.browser._get_playwright",
            return_value=(None, False),
        ):
            self.assertFalse(chromium_installed())


if __name__ == "__main__":
    unittest.main()
