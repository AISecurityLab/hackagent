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
Config Tab

Manage HackAgent configuration settings.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static

from hackagent.cli.config import CLIConfig


class ConfigTab(VerticalScroll):
    """Config tab for managing settings with vertical scrolling."""

    DEFAULT_CSS = ""

    BINDINGS = [
        Binding("s", "save_config", "Save"),
        Binding("t", "test_connection", "Test Connection"),
        Binding("r", "reset_config", "Reset"),
    ]

    def __init__(self, cli_config: CLIConfig):
        """Initialize config tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__()
        self.cli_config = cli_config

    def compose(self) -> ComposeResult:
        """Compose the config layout."""
        yield Static(
            "[bold cyan]HackAgent Configuration[/bold cyan]",
            classes="config-section",
        )

        with Vertical(classes="config-section"):
            yield Static("[bold]API Configuration[/bold]")

            with Vertical(classes="form-group"):
                yield Label("API Key:")
                yield Input(
                    placeholder="Your HackAgent API key",
                    id="api-key",
                    password=True,
                )

            with Vertical(classes="form-group"):
                yield Label("Base URL:")
                yield Input(
                    id="base_url",
                    placeholder="https://api.hackagent.dev",
                    classes="config-input",
                )

            with Vertical(classes="form-group"):
                yield Label("Output Format:")
                yield Select(
                    [("Table", "table"), ("JSON", "json"), ("CSV", "csv")],
                    id="output-format",
                    value=self.cli_config.output_format,
                )

        with Vertical(classes="config-section"):
            yield Static("[bold]Configuration File[/bold]")

            yield Static(
                f"[dim]Location:[/dim] {self.cli_config.default_config_path}",
                classes="info-box",
                id="config-file-location",
            )

            yield Static(
                "[dim]Status: Checking...[/dim]",
                classes="status-indicator",
                id="config-status",
            )

        with Horizontal(classes="button-group"):
            yield Button("Save Configuration", id="save-config", variant="primary")
            yield Button("Test Connection", id="test-connection", variant="default")
            yield Button("Reset to Defaults", id="reset-config", variant="error")
            yield Button("Validate Config", id="validate-config", variant="success")

        with Vertical(classes="config-section"):
            yield Static("[bold]System Information[/bold]")

            yield Static(
                f"""[dim]Python Version:[/dim] {self._get_python_version()}
[dim]CLI Version:[/dim] 0.2.5
[dim]Dependencies:[/dim] {self._check_dependencies()}""",
                classes="info-box",
                id="system-info",
            )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        self._load_config()
        self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "save-config":
            self._save_config()
        elif event.button.id == "test-connection":
            self._test_connection()
        elif event.button.id == "reset-config":
            self._reset_config()
        elif event.button.id == "validate-config":
            self._validate_config()

    def _load_config(self) -> None:
        """Load current configuration into form fields."""
        # Set API key (masked)
        if self.cli_config.api_key:
            self.query_one("#api-key", Input).value = self.cli_config.api_key

        # Set base URL
        self.query_one("#base_url", Input).value = self.cli_config.base_url

        # Set output format
        self.query_one("#output-format", Select).value = self.cli_config.output_format

    def _update_status(self) -> None:
        """Update configuration status display."""
        status_widget = self.query_one("#config-status", Static)

        if self.cli_config.default_config_path.exists():
            status_widget.update("[green]✅ Configuration file exists[/green]")
        else:
            status_widget.update(
                "[yellow]⚠️ No configuration file found. Save to create one.[/yellow]"
            )

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Get values from form
            api_key = self.query_one("#api-key", Input).value
            base_url = self.query_one("#base_url", Input).value
            output_format = self.query_one("#output-format", Select).value

            # Update config
            if api_key:
                self.cli_config.api_key = api_key
            if base_url:
                self.cli_config.base_url = base_url
            self.cli_config.output_format = output_format

            # Save to file
            self.cli_config.save()

            self._update_status()

        except Exception:
            pass

    def _test_connection(self) -> None:
        """Test API connection."""
        try:
            from hackagent.api.key import key_list
            from hackagent.client import AuthenticatedClient

            if not self.cli_config.api_key:
                return

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
            )

            key_list.sync_detailed(client=client)

        except Exception:
            pass

    def _validate_config(self) -> None:
        """Validate current configuration."""
        try:
            self.cli_config.validate()
        except ValueError:
            pass

    def _reset_config(self) -> None:
        """Reset configuration to defaults."""
        try:
            if self.cli_config.default_config_path.exists():
                self.cli_config.default_config_path.unlink()

            # Reset to defaults
            self.cli_config.base_url = "https://api.hackagent.dev"
            self.cli_config.output_format = "table"
            self.cli_config.api_key = None

            self._load_config()
            self._update_status()

        except Exception:
            pass

    def _get_python_version(self) -> str:
        """Get Python version string."""
        import sys

        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _check_dependencies(self) -> str:
        """Check if required dependencies are installed."""
        import importlib.util

        required_packages = ["pandas", "yaml", "litellm", "textual"]
        missing = [
            pkg for pkg in required_packages if importlib.util.find_spec(pkg) is None
        ]

        if not missing:
            return "[green]✅ All dependencies installed[/green]"
        else:
            return f"[yellow]⚠️ Some dependencies missing: {', '.join(missing)}[/yellow]"

    def refresh_data(self) -> None:
        """Refresh config data."""
        self._load_config()
        self._update_status()
