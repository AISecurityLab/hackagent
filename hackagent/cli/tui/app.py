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
Main TUI Application

Full-screen tabbed interface for HackAgent.
"""

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Static, TabbedContent, TabPane

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.tabs.agents import AgentsTab
from hackagent.cli.tui.tabs.attacks import AttacksTab
from hackagent.cli.tui.tabs.config import ConfigTab
from hackagent.cli.tui.tabs.dashboard import DashboardTab
from hackagent.cli.tui.tabs.results import ResultsTab


class HackAgentHeader(Container):
    """Custom header with ASCII logo"""

    DEFAULT_CSS = """
    HackAgentHeader {
        dock: top;
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


class HackAgentTUI(App):
    """HackAgent Terminal User Interface Application"""

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: #8b0000;  /* dark red - HackAgent brand color */
        color: #ffffff;
        height: 3;
    }

    Footer {
        background: #2b0000;  /* darker red */
        color: #ffffff;
    }

    TabbedContent {
        height: 100%;
        border: solid #ff0000;  /* red - HackAgent brand color */
    }

    TabPane {
        padding: 1 2;
    }

    TabbedContent > ContentSwitcher > * > * {
        background: $surface;
    }

    Tabs {
        background: #2b0000;
    }

    Tab {
        color: #cccccc;
        background: #2b0000;
    }

    Tab.-active {
        color: #ffffff;
        background: #8b0000;  /* dark red when active */
        text-style: bold;
    }

    Tab:hover {
        background: #5b0000;
    }

    .title-bar {
        dock: top;
        width: 100%;
        background: #8b0000;
        color: #ffffff;
        height: 3;
        content-align: center middle;
    }

    .section {
        border: solid #ff0000;
        padding: 1;
        margin: 1;
        height: auto;
    }

    .info-box {
        background: $panel;
        border: solid #ff0000;
        padding: 1;
        margin: 1;
    }

    Button {
        margin: 1;
    }

    Button.-primary {
        background: #8b0000;
        color: #ffffff;
    }

    Button.-primary:hover {
        background: #ff0000;
    }

    DataTable {
        height: 100%;
    }

    DataTable > .datatable--header {
        background: #8b0000;
        color: #ffffff;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #5b0000;
    }
    """

    TITLE = "🔴 HACKAGENT 🔴 - AI Security Testing Toolkit"
    SUB_TITLE = "Red Team Security Interface"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("d", "switch_tab('dashboard')", "Dashboard", show=False),
        Binding("a", "switch_tab('agents')", "Agents", show=False),
        Binding("k", "switch_tab('attacks')", "Attacks", show=False),
        Binding("r", "switch_tab('results')", "Results", show=False),
        Binding("c", "switch_tab('config')", "Config", show=False),
        Binding("f5", "refresh", "Refresh", show=True),
    ]

    def __init__(
        self,
        cli_config: CLIConfig,
        initial_tab: str = "dashboard",
        initial_data: dict = None,
    ):
        """Initialize the TUI application.

        Args:
            cli_config: CLI configuration object
            initial_tab: Which tab to show initially (default: "dashboard")
            initial_data: Initial data to pre-fill in the tab (default: None)
        """
        super().__init__()
        self.cli_config = cli_config
        self.initial_tab = initial_tab
        self.initial_data = initial_data or {}
        self.dark = True  # Use dark theme by default

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield HackAgentHeader()

        with TabbedContent(initial=self.initial_tab):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardTab(self.cli_config)

            with TabPane("Agents", id="agents"):
                yield AgentsTab(self.cli_config)

            with TabPane("Attacks", id="attacks"):
                yield AttacksTab(self.cli_config, initial_data=self.initial_data)

            with TabPane("Results", id="results"):
                yield ResultsTab(self.cli_config)

            with TabPane("Config", id="config"):
                yield ConfigTab(self.cli_config)

        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab.

        Args:
            tab_id: ID of the tab to switch to
        """
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id

    def action_refresh(self) -> None:
        """Refresh the current tab's data."""
        tabs = self.query_one(TabbedContent)
        active_pane = tabs.get_pane(tabs.active)
        if active_pane and hasattr(active_pane, "refresh_data"):
            # Get the first child of the TabPane (our custom tab widget)
            for child in active_pane.children:
                if hasattr(child, "refresh_data"):
                    child.refresh_data()
                    self.notify("Data refreshed", severity="information")
                    break

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE

    def show_success(self, message: str) -> None:
        """Show success notification with checkmark."""
        self.notify(f"✅ {message}", severity="information", timeout=3)

    def show_error(self, message: str) -> None:
        """Show error notification with X mark."""
        self.notify(f"❌ {message}", severity="error", timeout=5)

    def show_warning(self, message: str) -> None:
        """Show warning notification with warning sign."""
        self.notify(f"⚠️ {message}", severity="warning", timeout=4)

    def show_info(self, message: str) -> None:
        """Show info notification with info icon."""
        self.notify(f"ℹ️ {message}", severity="information", timeout=3)
