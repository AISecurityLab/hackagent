# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack Log Viewer Component

A reusable Textual widget for displaying live attack execution logs
with syntax highlighting, auto-scrolling, and filtering capabilities.
"""

from typing import Any, List, Optional, Tuple

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Checkbox, Input, RichLog, Static


def _escape(value: Any) -> str:
    """Escape a value for safe Rich markup rendering.

    Args:
        value: Any value to escape

    Returns:
        String with Rich markup characters escaped

    Note:
        We escape ALL square brackets, not just tag-like patterns,
        because Rich's markup parser can get confused by unescaped
        brackets in certain contexts (e.g., JSON arrays inside colored text).
    """
    if value is None:
        return ""
    # Escape ALL square brackets to prevent any markup interpretation issues
    text = str(value)
    return text.replace("[", "\\[").replace("]", "\\]")


class AttackLogViewer(Container):
    """
    A container widget for displaying attack execution logs in real-time.

    This component provides:
    - Live log streaming with syntax highlighting
    - Color-coded log levels (INFO, WARNING, ERROR)
    - Auto-scroll to latest logs
    - Manual scroll capability
    - Clear logs functionality
    - Export logs to file
    """

    DEFAULT_CSS = """
    AttackLogViewer {
        border: solid $primary;
        padding: 0;
    }

    AttackLogViewer .log-header {
        dock: top;
        height: 3;
        background: $panel;
        padding: 0 1;
        content-align: center middle;
    }

    AttackLogViewer .log-controls {
        dock: top;
        height: 3;
        background: $surface;
        padding: 0 1;
        layout: horizontal;
    }

    AttackLogViewer .log-filters {
        dock: top;
        height: 3;
        background: $surface;
        padding: 0 1;
        layout: horizontal;
    }

    AttackLogViewer .log-filters Checkbox {
        width: 14;
        margin: 0 1;
    }

    AttackLogViewer #log-search {
        width: 1fr;
        margin: 0 1;
    }

    AttackLogViewer RichLog {
        background: $surface;
        border: none;
        padding: 1;
        height: 1fr;
        width: 100%;
    }

    AttackLogViewer Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str = "Attack Execution Logs",
        show_controls: bool = True,
        max_lines: int = 1000,
        **kwargs,
    ):
        """
        Initialize the log viewer.

        Args:
            title: Title to display in the header
            show_controls: Whether to show control buttons
            max_lines: Maximum number of log lines to retain
            **kwargs: Additional keyword arguments for Container
        """
        super().__init__(**kwargs)
        self.log_title = title
        self.show_controls = show_controls
        self.max_lines = max_lines
        self._auto_scroll = True
        # Structured ring buffer: (level, raw_message). Headers (step markers,
        # banners, etc.) are stored with level ``"HEADER"`` so filtering can
        # treat them as level-independent.
        self._records: List[Tuple[str, str]] = []
        self._level_enabled = {
            "DEBUG": True,
            "INFO": True,
            "WARNING": True,
            "ERROR": True,
        }
        self._search_query: str = ""

    def compose(self) -> ComposeResult:
        """Compose the log viewer layout."""
        # Header
        yield Static(
            f"[bold cyan]{self.log_title}[/bold cyan]",
            classes="log-header",
        )

        # Control buttons (optional)
        if self.show_controls:
            with Horizontal(classes="log-controls"):
                yield Button("Clear", id="clear-logs", variant="default")
                yield Button("Copy", id="copy-logs", variant="default")
                yield Button("Save", id="save-logs", variant="default")
                yield Button("Pager", id="view-pager", variant="default")
                yield Button("Auto-scroll: ON", id="toggle-scroll", variant="primary")
                yield Static("", id="log-count")

            with Horizontal(classes="log-filters"):
                yield Checkbox("DEBUG", value=True, id="filter-debug")
                yield Checkbox("INFO", value=True, id="filter-info")
                yield Checkbox("WARN", value=True, id="filter-warning")
                yield Checkbox("ERROR", value=True, id="filter-error")
                yield Input(placeholder="search…", id="log-search")

        # Log display area
        rich_log = RichLog(
            highlight=True,
            markup=True,
            max_lines=self.max_lines,
            wrap=True,
            id="attack-log-display",
        )
        yield rich_log

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.update_log_count(0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "clear-logs":
            self.clear_logs()
        elif event.button.id == "copy-logs":
            ok = self.copy_logs()
            self.notify(
                "Logs copied to clipboard!" if ok else "Nothing to copy",
                title="Copy",
                severity="information" if ok else "warning",
            )
        elif event.button.id == "save-logs":
            path = self.save_logs_to_file()
            if path:
                self.notify(f"Saved to {path}", title="Save", severity="information")
            else:
                self.notify("Nothing to save", title="Save", severity="warning")
        elif event.button.id == "view-pager":
            self.view_in_pager()
        elif event.button.id == "toggle-scroll":
            self.toggle_auto_scroll()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """React to level-filter toggles by re-rendering the visible log."""
        mapping = {
            "filter-debug": "DEBUG",
            "filter-info": "INFO",
            "filter-warning": "WARNING",
            "filter-error": "ERROR",
        }
        level = mapping.get(event.checkbox.id or "")
        if level is None:
            return
        self._level_enabled[level] = bool(event.value)
        self._rerender()

    def on_input_changed(self, event: Input.Changed) -> None:
        """React to the search input (case-insensitive substring filter)."""
        if event.input.id == "log-search":
            self._search_query = (event.value or "").strip().lower()
            self._rerender()

    _LEVEL_COLORS = {
        "DEBUG": "dim",
        "INFO": "cyan",
        "WARNING": "yellow",
        "ERROR": "bold red",
        "CRITICAL": "bold red on white",
    }

    def _format_record(self, level: str, message: str) -> str:
        """Render one (level, message) record as Rich markup."""
        if level == "HEADER":
            # Pre-formatted banner — write through unchanged.
            return message
        color = self._LEVEL_COLORS.get(level, "white")
        escaped = _escape(message)
        if level in ("ERROR", "CRITICAL"):
            return f"[{color}]🔴 {escaped}[/{color}]"
        if level == "WARNING":
            return f"[{color}]⚠️  {escaped}[/{color}]"
        if level == "DEBUG":
            return f"[{color}]🔍 {escaped}[/{color}]"
        return f"[{color}]{escaped}[/{color}]"

    def _record_visible(self, level: str, message: str) -> bool:
        """Apply level + search filters. Headers are always visible."""
        if level != "HEADER":
            normalized = "ERROR" if level == "CRITICAL" else level
            if not self._level_enabled.get(normalized, True):
                return False
        if self._search_query and self._search_query not in message.lower():
            return False
        return True

    def _rerender(self) -> None:
        """Rewrite the RichLog from the structured buffer."""
        try:
            log_widget = self.query_one("#attack-log-display", RichLog)
        except Exception:
            return
        log_widget.clear()
        visible = 0
        for level, message in self._records:
            if not self._record_visible(level, message):
                continue
            log_widget.write(self._format_record(level, message))
            visible += 1
        if self._auto_scroll:
            log_widget.scroll_end(animate=False)
        self.update_log_count(visible)

    def add_log(self, message: str, level: str = "INFO") -> None:
        """Append a log message; respects current level/search filters."""
        self._records.append((level, message))
        # Keep the structured buffer bounded.
        if len(self._records) > self.max_lines:
            del self._records[: len(self._records) - self.max_lines]

        if not self._record_visible(level, message):
            return

        try:
            log_widget = self.query_one("#attack-log-display", RichLog)
        except Exception:
            return
        log_widget.write(self._format_record(level, message))
        if self._auto_scroll:
            log_widget.scroll_end(animate=False)
        self.update_log_count(
            sum(1 for lv, msg in self._records if self._record_visible(lv, msg))
        )

    def add_step_header(self, step_name: str, step_number: int = 0) -> None:
        """Append a step banner. Always visible regardless of level filters."""
        separator = "─" * 60
        escaped_step_name = _escape(step_name)
        if step_number > 0:
            banner = (
                f"\n[bold magenta]{separator}\n"
                f"🎯 STEP {step_number}: {escaped_step_name}\n"
                f"{separator}[/bold magenta]\n"
            )
        else:
            banner = (
                f"\n[bold magenta]{separator}\n"
                f"🎯 {escaped_step_name}\n"
                f"{separator}[/bold magenta]\n"
            )
        self._records.append(("HEADER", banner))
        try:
            log_widget = self.query_one("#attack-log-display", RichLog)
        except Exception:
            return
        log_widget.write(banner)
        if self._auto_scroll:
            log_widget.scroll_end(animate=False)

    def clear_logs(self) -> None:
        """Clear all log messages from the viewer."""
        try:
            log_widget = self.query_one("#attack-log-display", RichLog)
            log_widget.clear()
        except Exception:
            pass
        self._records.clear()
        self.update_log_count(0)

    def _filtered_plaintext(self) -> str:
        """Return the plain text of currently visible records."""
        import re

        lines: list[str] = []
        for level, message in self._records:
            if not self._record_visible(level, message):
                continue
            if level == "HEADER":
                # Strip Rich markup tags for the plaintext copy.
                lines.append(re.sub(r"\[/?[^]]+\]", "", message).strip("\n"))
            else:
                lines.append(f"[{level}] {message}")
        return "\n".join(lines)

    def save_logs_to_file(self) -> "Optional[str]":
        """Save current (filtered) log text to a timestamped temp file."""
        from datetime import datetime
        import os
        import tempfile

        text = self._filtered_plaintext()
        if not text:
            return None
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(tempfile.gettempdir(), f"hackagent_logs_{ts}.log")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return path
        except Exception:
            return None

    def copy_logs(self) -> bool:
        """Copy currently visible logs to the clipboard.

        Uses the shared clipboard helper (OSC 52 → OS tools → pyperclip → file).

        Returns:
            True if logs were copied successfully, False otherwise.
        """
        from hackagent.cli.tui.widgets.clipboard import copy_to_clipboard

        log_text = self._filtered_plaintext()
        if not log_text:
            return False
        try:
            app = self.app
        except Exception:
            app = None
        return copy_to_clipboard(app, log_text)

    def view_in_pager(self) -> None:
        """View currently visible logs in $PAGER / less for navigation."""
        log_text = self._filtered_plaintext()
        if not log_text:
            return

        try:
            import tempfile
            import subprocess
            import os

            temp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".log", delete=False
            )
            temp_file.write(log_text)
            temp_file.close()

            # Suspend the TUI and open in pager
            self.app.suspend()

            # Try less first (with mouse support), fall back to more
            pager = os.environ.get("PAGER", "less")
            if pager == "less":
                # Enable mouse, color, and exit if content fits on screen
                subprocess.run(["less", "-R", "-X", "--mouse", temp_file.name])
            else:
                subprocess.run([pager, temp_file.name])

            # Clean up
            os.unlink(temp_file.name)

            # Resume the TUI
            self.app.refresh()

        except Exception:
            self.app.refresh()  # Make sure we resume even on error
            pass

    def toggle_auto_scroll(self) -> None:
        """Toggle automatic scrolling to latest logs."""
        self._auto_scroll = not self._auto_scroll
        button = self.query_one("#toggle-scroll", Button)
        button.label = f"Auto-scroll: {'ON' if self._auto_scroll else 'OFF'}"
        button.variant = "primary" if self._auto_scroll else "default"

    def update_log_count(self, count: int) -> None:
        """
        Update the log count display.

        Args:
            count: Number of log lines currently displayed
        """
        if self.show_controls:
            count_widget = self.query_one("#log-count", Static)
            count_widget.update(f"[dim]Lines: {count}/{self.max_lines}[/dim]")

    def get_log_text(self) -> str:
        """All log text as a plain string — currently visible records only."""
        return self._filtered_plaintext()

    def load_logs_from_buffer(self, buffer: list[tuple[str, str]]) -> None:
        """
        Load logs from a buffer (e.g., from TUILogHandler).

        Args:
            buffer: List of (message, level) tuples
        """
        for message, level in buffer:
            self.add_log(message, level)  # add_log will handle line count
