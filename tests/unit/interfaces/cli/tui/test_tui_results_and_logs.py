# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Copying the run's log, or a selection, from the TUI."""

from unittest.mock import MagicMock


class TestLogCopy:
    """The Ctrl+Y copy-selection binding: a selection, else the run's log."""

    def test_ctrl_y_binding_registered(self) -> None:
        from hackagent.interfaces.tui.app import HackAgentTUI

        pairs = {(b.key, b.action) for b in HackAgentTUI.BINDINGS}
        assert ("ctrl+y", "copy_selection") in pairs

    def test_action_copies_current_selection(self) -> None:
        from unittest.mock import PropertyMock, patch

        from hackagent.interfaces.tui.app import HackAgentTUI

        app = HackAgentTUI(MagicMock())
        app.copy_to_clipboard = MagicMock()
        app.notify = MagicMock()
        screen = MagicMock()
        screen.get_selected_text.return_value = "selected log line"
        with (
            patch.object(
                HackAgentTUI, "screen", new_callable=PropertyMock, return_value=screen
            ),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            app.action_copy_selection()
        # A selection takes priority; it goes to the clipboard via the helper.
        app.copy_to_clipboard.assert_called_once_with("selected log line")

    def test_action_falls_back_to_logs_when_no_selection(self) -> None:
        from unittest.mock import PropertyMock, patch

        from hackagent.interfaces.tui.app import HackAgentTUI

        app = HackAgentTUI(MagicMock())
        app.copy_to_clipboard = MagicMock()
        app.notify = MagicMock()
        # No selection: the run's log is copied.
        screen = MagicMock()
        screen.get_selected_text.return_value = ""
        with (
            patch.object(
                HackAgentTUI, "screen", new_callable=PropertyMock, return_value=screen
            ),
            patch.object(
                HackAgentTUI,
                "_run_log_text",
                return_value="log line 1\nlog line 2",
            ),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            app.action_copy_selection()
        app.copy_to_clipboard.assert_called_once_with("log line 1\nlog line 2")

    def test_action_warns_when_nothing_to_copy(self) -> None:
        from unittest.mock import PropertyMock, patch

        from hackagent.interfaces.tui.app import HackAgentTUI

        app = HackAgentTUI(MagicMock())
        app.copy_to_clipboard = MagicMock()
        app.notify = MagicMock()
        screen = MagicMock()
        screen.get_selected_text.return_value = ""
        with (
            patch.object(
                HackAgentTUI, "screen", new_callable=PropertyMock, return_value=screen
            ),
            patch.object(HackAgentTUI, "_run_log_text", return_value=""),
        ):
            app.action_copy_selection()
        app.copy_to_clipboard.assert_not_called()
        app.notify.assert_called_once()


# ============================================================================
# Shared clipboard helper + Actions copy button
# ============================================================================


class TestClipboardHelper:
    """The shared copy_to_clipboard helper used by the log/actions Copy buttons."""

    def test_uses_osc52_via_app(self) -> None:
        from unittest.mock import patch

        from hackagent.interfaces.tui.widgets.clipboard import copy_to_clipboard

        app = MagicMock()
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            ok = copy_to_clipboard(app, "hello")
        assert ok is True
        app.copy_to_clipboard.assert_called_once_with("hello")

    def test_empty_text_returns_false(self) -> None:
        from hackagent.interfaces.tui.widgets.clipboard import copy_to_clipboard

        assert copy_to_clipboard(None, "") is False

    def test_richlog_plaintext_joins_strip_text(self) -> None:

        from hackagent.interfaces.tui.widgets.clipboard import richlog_plaintext

        s1, s2 = MagicMock(), MagicMock()
        s1.text = "first line"
        s2.text = "second line"
        log = MagicMock()
        log.lines = [s1, s2]
        assert richlog_plaintext(log) == "first line\nsecond line"
