# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base Tab Class

Base class for all TUI tabs with common functionality.
"""

import httpx
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from hackagent.cli.config import CLIConfig
from hackagent.client import AuthenticatedClient


class HackAgentHeader(Container):
    """Custom header with ASCII logo"""

    DEFAULT_CSS = """
    HackAgentHeader {
        width: 100%;
        height: 7;
        padding: 0 1;
    }

    HackAgentHeader Static {
        color: #ff0000;
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        from hackagent.utils import HACKAGENT

        # Display the ASCII logo as-is (now side-by-side format)
        logo_text = Text(HACKAGENT, style="bold red")
        yield Static(logo_text)


class BaseTab(Container):
    """Base class for all TUI tabs.

    Provides common functionality:
    - CLI configuration access
    - API client creation with timeout
    - Error handling helpers
    - Refresh mechanism

    Subclasses should implement refresh_data() method.
    """

    # Default API timeout (can be overridden by subclasses)
    API_TIMEOUT = 5.0

    def __init__(self, cli_config: CLIConfig, **kwargs):
        """Initialize base tab.

        Args:
            cli_config: CLI configuration instance
            **kwargs: Additional arguments passed to Container
        """
        super().__init__(**kwargs)
        self.cli_config = cli_config
        self._refresh_interval = None

    def create_api_client(self, timeout: float | None = None) -> AuthenticatedClient:
        """Create an authenticated API client with timeout.

        Args:
            timeout: Optional timeout override (uses API_TIMEOUT by default)

        Returns:
            Configured AuthenticatedClient instance
        """
        if timeout is None:
            timeout = self.API_TIMEOUT

        return AuthenticatedClient(
            base_url=self.cli_config.base_url,
            token=self.cli_config.api_key,
            prefix="Bearer",
            timeout=httpx.Timeout(timeout, connect=timeout),
        )

    def handle_api_error(self, error: Exception, context: str = "API call") -> str:
        """Format API error messages for display.

        Args:
            error: The exception that occurred
            context: Description of what operation failed

        Returns:
            Formatted error message
        """
        from rich.markup import escape

        if isinstance(error, httpx.TimeoutException):
            return f"[red]Timeout:[/red] {context} took too long"
        elif isinstance(error, httpx.HTTPStatusError):
            if error.response.status_code == 401:
                return (
                    "[red]Authentication Failed[/red]\n\n"
                    "[yellow]Your API key is invalid or expired[/yellow]\n\n"
                    "[cyan]To fix:[/cyan]\n"
                    "Run: hackagent config set --api-key YOUR_KEY\n\n"
                    "[dim]Press F5 to retry after updating[/dim]"
                )
            else:
                return f"[red]HTTP {error.response.status_code}:[/red] {context} failed"
        else:
            # Escape error message to prevent Rich markup issues
            error_text = escape(str(error))
            return f"[red]Error:[/red] {error_text}"

    def refresh_data(self) -> None:
        """Refresh tab data from API.

        Should be overridden by subclasses that need data refresh functionality.
        Default implementation does nothing.
        """
        pass

    def enable_auto_refresh(self, interval: float = 5.0) -> None:
        """Enable automatic data refresh at specified interval.

        Args:
            interval: Refresh interval in seconds (default: 5.0)
        """
        if self._refresh_interval is not None:
            # Remove existing refresh timer
            self._refresh_interval = None

        self._refresh_interval = self.set_interval(
            interval, self.refresh_data, name=f"{self.__class__.__name__}-refresh"
        )

    def disable_auto_refresh(self) -> None:
        """Disable automatic data refresh."""
        if self._refresh_interval is not None:
            self._refresh_interval = None

    def on_mount(self) -> None:
        """Called when tab is mounted.

        Subclasses can override to add custom mounting behavior,
        but should call super().on_mount() to ensure proper initialization.
        """
        # Defer initial load to ensure DOM is ready
        self.call_after_refresh(self.refresh_data)
