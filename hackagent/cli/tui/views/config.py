# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Config Tab

Manage HackAgent configuration settings.
"""

import importlib.metadata

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static

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

            yield Static(
                "[green]🗄️ Mode:[/green] [bold]Local[/bold] — results stored in local SQLite database",
                classes="status-indicator",
                id="mode-indicator",
            )

        with Horizontal(classes="button-group"):
            yield Button("Save Configuration", id="save-config", variant="primary")
            yield Button("Reset to Defaults", id="reset-config", variant="error")
            yield Button("Validate Config", id="validate-config", variant="success")

        with Vertical(classes="config-section"):
            yield Static("[bold]System Information[/bold]")

            yield Static(
                f"""[dim]Python Version:[/dim] {self._get_python_version()}
[dim]CLI Version:[/dim] {importlib.metadata.version("hackagent")}
[dim]Dependencies:[/dim] {self._check_dependencies()}
[dim]Local DB:[/dim] ~/.local/share/hackagent/hackagent.db""",
                classes="info-box",
                id="system-info",
            )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        self._load_config()
        self._update_status()
        self._update_mode_indicator()

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
        """Load current configuration."""
        pass

    def _update_status(self) -> None:
        """Update configuration status display."""
        status_widget = self.query_one("#config-status", Static)

        if self.cli_config.default_config_path.exists():
            status_widget.update("[green]✅ Configuration file exists[/green]")
        else:
            status_widget.update(
                "[yellow]⚠️ No configuration file found. Save to create one.[/yellow]"
            )

    def _update_mode_indicator(self) -> None:
        """Show storage mode — always local."""
        try:
            mode_widget = self.query_one("#mode-indicator", Static)
            from pathlib import Path

            db_path = Path("~/.local/share/hackagent/hackagent.db").expanduser()
            db_exists = (
                "[green]✓ exists[/green]"
                if db_path.exists()
                else "[yellow]not yet created[/yellow]"
            )
            mode_widget.update(
                f"[cyan]💾 Mode:[/cyan] [bold]Local[/bold] — SQLite at {db_path} ({db_exists})"
            )
        except Exception:
            pass

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            self.cli_config.save()
            self._update_status()
            self._update_mode_indicator()
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

            self._load_config()
            self._update_status()

        except Exception:
            pass

    def _get_python_version(self) -> str:
        """Get Python version string."""
        import sys

        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_required_packages(self) -> list[str]:
        """Get required packages from installed package metadata."""
        import re
        from importlib.metadata import requires

        # Map package distribution names to import names
        package_to_import = {
            "pyyaml": "yaml",
            "python-dateutil": "dateutil",
        }

        try:
            # Get dependencies from installed package metadata
            deps = requires("hackagent")
            if not deps:
                return []

            packages = []
            for dep in deps:
                # Skip optional dependencies (those with extras like "; extra == ...")
                if "extra" in dep:
                    continue
                # Get package name before version specifier
                pkg_name = re.split(r"[<>=!~\[;\s]", dep)[0].strip()
                if pkg_name:
                    # Map to import name if needed
                    import_name = package_to_import.get(pkg_name.lower(), pkg_name)
                    packages.append(import_name)

            return packages
        except Exception:
            return []

    def _check_dependencies(self) -> str:
        """Check if required dependencies are installed."""
        import importlib.util

        required_packages = self._get_required_packages()
        if not required_packages:
            return "[yellow]⚠️ Could not read package dependencies[/yellow]"

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
