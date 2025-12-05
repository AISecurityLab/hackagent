# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Attack Log Viewer Component

A reusable Textual widget for displaying live attack execution logs
with syntax highlighting, auto-scrolling, and filtering capabilities.
"""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Button, RichLog, Static


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
        self._line_count = 0  # Track line count internally
        self._log_buffer: list[str] = []  # Store log messages for copying
        self._log_file = None  # File handle for continuous logging
        self._log_file_path = None  # Path to the log file
        self._initialize_log_file()

    def compose(self) -> ComposeResult:
        """Compose the log viewer layout."""
        # Header
        yield Static(
            f"[bold cyan]{self.log_title}[/bold cyan]",
            classes="log-header",
        )

        # Control buttons (optional)
        if self.show_controls:
            with Container(classes="log-controls"):
                yield Button("Clear Logs", id="clear-logs", variant="default")
                yield Button("Auto-scroll: ON", id="toggle-scroll", variant="primary")
                yield Static("", id="log-count")
                yield Static("", id="log-file-path", classes="log-file-info")

        # Log display area
        rich_log = RichLog(
            highlight=True,
            markup=True,
            max_lines=self.max_lines,
            wrap=True,
            id="attack-log-display",
        )
        yield rich_log

    def _initialize_log_file(self) -> None:
        """Initialize log file for continuous writing."""
        try:
            import os
            from datetime import datetime

            # Create logs directory
            log_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(log_dir, exist_ok=True)

            # Create log file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._log_file_path = os.path.join(log_dir, f"attack_logs_{timestamp}.log")
            self._log_file = open(
                self._log_file_path, "w", buffering=1
            )  # Line buffered

        except Exception:
            # If file creation fails, just continue without file logging
            self._log_file = None
            self._log_file_path = None

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.update_log_count(0)
        if self._log_file_path and self.show_controls:
            self._update_log_file_path_display()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "clear-logs":
            self.clear_logs()
        elif event.button.id == "toggle-scroll":
            self.toggle_auto_scroll()

    def add_log(self, message: str, level: str = "INFO") -> None:
        """
        Add a log message to the viewer with appropriate styling.

        Args:
            message: The log message to display
            level: Log level (INFO, WARNING, ERROR, DEBUG)
        """
        log_widget = self.query_one("#attack-log-display", RichLog)

        # Color code based on log level
        level_colors = {
            "DEBUG": "dim",
            "INFO": "cyan",
            "WARNING": "yellow",
            "ERROR": "bold red",
            "CRITICAL": "bold red on white",
        }

        color = level_colors.get(level, "white")

        # Format the message with color
        if level in ["ERROR", "CRITICAL"]:
            formatted_message = f"[{color}]🔴 {message}[/{color}]"
        elif level == "WARNING":
            formatted_message = f"[{color}]⚠️  {message}[/{color}]"
        elif level == "DEBUG":
            formatted_message = f"[{color}]🔍 {message}[/{color}]"
        else:  # INFO and default
            formatted_message = f"[{color}]{message}[/{color}]"

        # Add to log display
        log_widget.write(formatted_message)

        # Store in buffer for copying (strip Rich markup)
        plain_message = message  # Store the original message without formatting
        log_entry = f"[{level}] {plain_message}"
        self._log_buffer.append(log_entry)

        # Write to log file immediately
        if self._log_file:
            try:
                self._log_file.write(log_entry + "\n")
                self._log_file.flush()  # Ensure it's written immediately
            except Exception:
                pass  # Silently continue if file write fails

        # Auto-scroll to bottom if enabled
        if self._auto_scroll:
            log_widget.scroll_end(animate=False)

        # Update log count
        self._line_count += 1
        self.update_log_count(self._line_count)

    def add_step_header(self, step_name: str, step_number: int = 0) -> None:
        """
        Add a prominent step header to visually separate pipeline steps.

        Args:
            step_name: Name of the step
            step_number: Step number (0 for no number)
        """
        log_widget = self.query_one("#attack-log-display", RichLog)

        # Create a visual separator
        separator = "─" * 60
        if step_number > 0:
            header = f"\n[bold magenta]{separator}\n🎯 STEP {step_number}: {step_name}\n{separator}[/bold magenta]\n"
        else:
            header = f"\n[bold magenta]{separator}\n🎯 {step_name}\n{separator}[/bold magenta]\n"

        log_widget.write(header)

        if self._auto_scroll:
            log_widget.scroll_end(animate=False)

    def clear_logs(self) -> None:
        """Clear all log messages from the viewer."""
        log_widget = self.query_one("#attack-log-display", RichLog)
        log_widget.clear()
        self._line_count = 0
        self._log_buffer.clear()

        # Close current log file and create a new one
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass

        self._initialize_log_file()
        if self._log_file_path:
            self._update_log_file_path_display()

        self.update_log_count(0)

    def copy_logs(self) -> None:
        """Copy all log messages to clipboard or save to file."""
        if not self._log_buffer:
            return

        log_text = "\n".join(self._log_buffer)

        # Try multiple clipboard methods
        copied = False

        # Method 1: Try subprocess clipboard tools first (more reliable in containers/SSH)
        try:
            import subprocess
            import platform

            system = platform.system()
            if system == "Linux":
                # Try xclip first, then xsel
                try:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=log_text.encode(),
                        check=True,
                        stderr=subprocess.DEVNULL,
                        timeout=2,
                    )
                    copied = True
                except (
                    FileNotFoundError,
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ):
                    try:
                        subprocess.run(
                            ["xsel", "--clipboard", "--input"],
                            input=log_text.encode(),
                            check=True,
                            stderr=subprocess.DEVNULL,
                            timeout=2,
                        )
                        copied = True
                    except (
                        FileNotFoundError,
                        subprocess.CalledProcessError,
                        subprocess.TimeoutExpired,
                    ):
                        pass
            elif system == "Darwin":  # macOS
                subprocess.run(
                    ["pbcopy"], input=log_text.encode(), check=True, timeout=2
                )
                copied = True
            elif system == "Windows":
                subprocess.run(["clip"], input=log_text.encode(), check=True, timeout=2)
                copied = True

            if copied:
                pass
        except Exception:
            pass

        # Method 2: Try pyperclip as fallback (if subprocess failed)
        if not copied:
            try:
                import pyperclip

                pyperclip.copy(log_text)
                copied = True
            except ImportError:
                pass
            except Exception:
                pass

        # Fallback: Save to file
        if not copied:
            try:
                import os

                # Create a more permanent location in the project
                log_dir = os.path.join(os.getcwd(), "logs")
                os.makedirs(log_dir, exist_ok=True)

                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = os.path.join(log_dir, f"attack_logs_{timestamp}.log")

                with open(log_file, "w") as f:
                    f.write(log_text)
            except Exception:
                pass

    def view_in_pager(self) -> None:
        """View logs in a pager (less) for easy selection and navigation."""
        if not self._log_buffer:
            return

        try:
            import tempfile
            import subprocess
            import os

            # Save to temporary file
            log_text = "\n".join(self._log_buffer)
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

    def _update_log_file_path_display(self) -> None:
        """Update the log file path display."""
        if self.show_controls and self._log_file_path:
            try:
                path_widget = self.query_one("#log-file-path", Static)
                path_widget.update(f"[dim]📄 Logs: {self._log_file_path}[/dim]")
            except Exception:
                pass  # Widget might not be mounted yet

    def get_log_text(self) -> str:
        """
        Get all log text as a plain string (for export).

        Returns:
            All log messages as plain text
        """
        return "\n".join(self._log_buffer)

    def load_logs_from_buffer(self, buffer: list[tuple[str, str]]) -> None:
        """
        Load logs from a buffer (e.g., from TUILogHandler).

        Args:
            buffer: List of (message, level) tuples
        """
        for message, level in buffer:
            self.add_log(message, level)  # add_log will handle line count
