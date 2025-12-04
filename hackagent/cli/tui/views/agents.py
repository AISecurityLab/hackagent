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
Agents Tab

Manage and view AI agents.
"""

from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Static

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.base import BaseTab


class AgentsTab(BaseTab):
    """Agents tab for managing AI agents."""

    DEFAULT_CSS = """
    AgentsTab {
        layout: vertical;
    }
    
    AgentsTab .section-header {
        background: $panel;
        color: $accent;
        text-style: bold;
        padding: 0 1;
        height: 1;
        border-bottom: solid $primary;
    }
    
    AgentsTab .toolbar {
        height: 3;
        padding: 1;
        background: $panel;
        border-bottom: solid $primary;
    }
    
    AgentsTab .stats-bar {
        height: 3;
        background: $panel;
        padding: 0 2;
        border-bottom: solid $primary;
    }
    
    AgentsTab #agents-table {
        height: 2fr;
        min-height: 10;
        border: solid $primary;
    }
    
    AgentsTab #agent-details-container {
        height: 1fr;
        min-height: 10;
        max-height: 25;
        background: $panel;
        border: solid $accent;
        margin: 1;
    }
    
    AgentsTab .agent-details {
        padding: 1 2;
    }
    
    AgentsTab .empty-state {
        height: 100%;
        content-align: center middle;
        background: $panel;
    }
    """

    BINDINGS = [
        Binding("n", "new_agent", "New Agent"),
        Binding("d", "delete_agent", "Delete Agent"),
        Binding("enter", "view_agent", "View Details"),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, cli_config: CLIConfig):
        """Initialize agents tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__(cli_config)
        self.agents_data: list[Any] = []
        self.selected_agent: Any = None

    def compose(self) -> ComposeResult:
        """Compose the agents layout."""
        # Title section
        yield Static(
            "🤖 [bold cyan]Agent Management[/bold cyan]", classes="section-header"
        )

        # Statistics bar
        yield Static(
            "📊 [cyan]Total Agents:[/cyan] [yellow]0[/yellow] | "
            "🟢 [green]Active:[/green] [yellow]0[/yellow] | "
            "⚡ [magenta]Last Updated:[/magenta] [dim]Never[/dim]",
            id="agents-stats",
            classes="stats-bar",
        )

        # Toolbar with action buttons
        with Horizontal(classes="toolbar"):
            yield Button("🔄 Refresh", id="refresh-agents", variant="primary")
            yield Button("➕ New Agent", id="new-agent", variant="success")
            yield Button("🗑️  Delete", id="delete-agent", variant="error")

        # Agents table
        table: DataTable = DataTable(
            id="agents-table", zebra_stripes=True, cursor_type="row"
        )
        table.add_columns("ID", "Name", "Type", "Endpoint", "Status", "Created")
        yield table

        # Details panel
        with VerticalScroll(classes="agent-details", id="agent-details-container"):
            yield Static(
                "[dim italic]💡 Select an agent from the table above to view detailed information[/dim]",
                id="agent-details",
            )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Show loading message immediately
        try:
            details_widget = self.query_one("#agent-details", Static)
            details_widget.update("⏳ [cyan]Loading agents from API...[/cyan]")

            stats_widget = self.query_one("#agents-stats", Static)
            stats_widget.update(
                "📊 [cyan]Total Agents:[/cyan] [yellow]...[/yellow] | "
                "🟢 [green]Active:[/green] [yellow]...[/yellow] | "
                "⚡ [magenta]Status:[/magenta] [cyan]Loading...[/cyan]"
            )
        except Exception:
            pass

        # Call base class mount which handles initial refresh
        super().on_mount()

        # Enable auto-refresh every 10 seconds
        self.enable_auto_refresh(interval=10.0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-agents":
            self.action_refresh()
        elif event.button.id == "new-agent":
            self._show_info_message("➕ Create new agent feature coming soon!")
        elif event.button.id == "delete-agent":
            if self.selected_agent:
                self._show_info_message(
                    f"🗑️  Delete agent '{self.selected_agent.name}' - feature coming soon!"
                )
            else:
                self._show_info_message("⚠️ Please select an agent to delete")

    def action_refresh(self) -> None:
        """Action to manually refresh agents data."""
        try:
            stats_widget = self.query_one("#agents-stats", Static)
            stats_widget.update(
                "📊 [cyan]Total Agents:[/cyan] [yellow]...[/yellow] | "
                "🟢 [green]Active:[/green] [yellow]...[/yellow] | "
                "⚡ [magenta]Status:[/magenta] [cyan]Refreshing...[/cyan]"
            )
        except Exception:
            pass
        self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the agents table."""
        table = self.query_one(DataTable)
        row_key = event.row_key
        row_index = table.get_row_index(row_key)

        if row_index < len(self.agents_data):
            self.selected_agent = self.agents_data[row_index]
            self._show_agent_details()

    def refresh_data(self) -> None:
        """Refresh agents data from API."""
        try:
            from hackagent.api.agent import agent_list

            # Validate configuration
            if not self.cli_config.api_key:
                self._show_empty_state(
                    "🔑 [bold yellow]API Key Not Configured[/bold yellow]\n\n"
                    "[cyan]To get started:[/cyan]\n"
                    "1. Run: [bold]hackagent config set --api-key YOUR_KEY[/bold]\n"
                    "2. Press [bold]F5[/bold] to refresh\n\n"
                    "[dim]Need an API key? Visit the HackAgent dashboard[/dim]"
                )
                return

            # Create API client with timeout
            client = self.create_api_client()

            # Fetch agents
            response = agent_list.sync_detailed(client=client)

            if response.status_code == 200 and response.parsed:
                self.agents_data = (
                    response.parsed.results if response.parsed.results else []
                )

                # Always update the table, even if empty
                if not self.agents_data:
                    # Clear table and show empty message
                    table = self.query_one("#agents-table", DataTable)
                    table.clear()

                    # Update stats
                    stats_widget = self.query_one("#agents-stats", Static)
                    stats_widget.update(
                        "📊 [cyan]Total Agents:[/cyan] [yellow]0[/yellow] | "
                        "🟢 [green]Active:[/green] [yellow]0[/yellow] | "
                        "⚡ [magenta]Status:[/magenta] [green]Loaded[/green]"
                    )

                    details_widget = self.query_one("#agent-details", Static)
                    details_widget.update(
                        "📭 [bold cyan]No Agents Found[/bold cyan]\n\n"
                        "[yellow]Get started by creating your first agent:[/yellow]\n\n"
                        "• Click [bold]➕ New Agent[/bold] button above\n"
                        "• Or use the CLI: [bold]hackagent agent create[/bold]\n\n"
                        "[dim]Agents are AI systems that you can test for security vulnerabilities[/dim]"
                    )
                else:
                    self._update_table()
            elif response.status_code == 401:
                error_msg = self.handle_api_error(Exception("401"), "Authentication")
                self._show_empty_state(error_msg)
            elif response.status_code == 403:
                self._show_empty_state(
                    "🚫 [bold red]Access Forbidden[/bold red]\n\n"
                    "[yellow]Your API key doesn't have permission to view agents[/yellow]\n\n"
                    "Contact your administrator or check your API key permissions"
                )
            else:
                error_status = f"API error: {response.status_code}"
                self._show_empty_state(
                    f"⚠️ [bold red]API Error[/bold red]\n\n{error_status}\n\n[dim]Press F5 to retry[/dim]"
                )

        except Exception as e:
            error_msg = self.handle_api_error(e, "Loading agents")
            self._show_empty_state(error_msg)

    def _show_empty_state(self, message: str) -> None:
        """Show an empty state message when no data is available.

        Args:
            message: Message to display
        """
        table = self.query_one("#agents-table", DataTable)
        table.clear()

        # Update stats bar
        try:
            stats_widget = self.query_one("#agents-stats", Static)
            stats_widget.update(
                "📊 [cyan]Total Agents:[/cyan] [red]0[/red] | "
                "🟢 [green]Active:[/green] [red]0[/red] | "
                "⚡ [magenta]Status:[/magenta] [red]Error[/red]"
            )
        except Exception:
            pass

        # Show message in details area
        details_widget = self.query_one("#agent-details", Static)
        details_widget.update(message)

    def _show_info_message(self, message: str) -> None:
        """Show an informational message in the details panel.

        Args:
            message: Message to display
        """
        details_widget = self.query_one("#agent-details", Static)
        details_widget.update(
            f"\n{message}\n\n[dim]This message will be replaced when you select an agent[/dim]"
        )

    def _update_table(self) -> None:
        """Update the agents table with current data."""
        details_widget = self.query_one("#agent-details", Static)
        try:
            table = self.query_one("#agents-table", DataTable)
            table.clear()

            rows_added = 0
            active_count = 0

            for agent in self.agents_data:
                # Format creation date
                created = "Unknown"
                if hasattr(agent, "created_at") and agent.created_at:
                    try:
                        if isinstance(agent.created_at, datetime):
                            created = agent.created_at.strftime("%Y-%m-%d %H:%M")
                        else:
                            created = str(agent.created_at)[:16]
                    except (AttributeError, ValueError, TypeError):
                        created = str(agent.created_at)[:16]

                # Get agent type
                agent_type = "Unknown"
                try:
                    agent_type = (
                        agent.agent_type.value
                        if hasattr(agent.agent_type, "value")
                        else str(agent.agent_type)
                    )
                except Exception:
                    agent_type = "Unknown"

                # Get endpoint
                endpoint = "N/A"
                try:
                    if agent.endpoint:
                        endpoint = (
                            (agent.endpoint[:35] + "...")
                            if len(agent.endpoint) > 35
                            else agent.endpoint
                        )
                except Exception:
                    endpoint = "N/A"

                # Determine status
                status = "🟢 Active"
                if hasattr(agent, "endpoint") and agent.endpoint:
                    active_count += 1
                else:
                    status = "⚪ Inactive"

                table.add_row(
                    str(agent.id)[:8] + "...",
                    agent.name or "Unnamed",
                    agent_type,
                    endpoint,
                    status,
                    created,
                )
                rows_added += 1

            # Update statistics bar
            from datetime import datetime as dt

            current_time = dt.now().strftime("%H:%M:%S")

            stats_widget = self.query_one("#agents-stats", Static)
            stats_widget.update(
                f"📊 [cyan]Total Agents:[/cyan] [green]{rows_added}[/green] | "
                f"🟢 [green]Active:[/green] [green]{active_count}[/green] | "
                f"⚡ [magenta]Last Updated:[/magenta] [yellow]{current_time}[/yellow]"
            )

            # Show success message
            inactive_count = rows_added - active_count
            details_widget.update(
                f"✅ [bold green]Successfully loaded {rows_added} agent(s)[/bold green]\n\n"
                f"[cyan]Agent Summary:[/cyan]\n"
                f"• Total: [yellow]{rows_added}[/yellow]\n"
                f"• Active (with endpoint): [green]{active_count}[/green]\n"
                f"• Inactive: [yellow]{inactive_count}[/yellow]\n\n"
                f"[dim italic]💡 Click on any agent in the table to view detailed information[/dim]"
            )

        except Exception as e:
            # If table update fails, show detailed error
            import traceback
            from rich.markup import escape

            error_details = traceback.format_exc()
            error_msg = escape(str(e))
            escaped_details = escape(error_details[:400])

            details_widget.update(
                f"❌ [bold red]Error updating table[/bold red]\n\n"
                f"[yellow]{type(e).__name__}:[/yellow] {error_msg}\n\n"
                f"[dim]Debug info:\n{escaped_details}[/dim]"
            )

    def _show_agent_details(self) -> None:
        """Show details of the selected agent."""
        if not self.selected_agent:
            return

        agent = self.selected_agent
        details_widget = self.query_one("#agent-details", Static)

        # Format creation date
        created = "Unknown"
        if hasattr(agent, "created_at") and agent.created_at:
            try:
                if isinstance(agent.created_at, datetime):
                    created = agent.created_at.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created = str(agent.created_at)
            except (AttributeError, ValueError, TypeError):
                created = str(agent.created_at)

        # Get agent type
        agent_type = "Unknown"
        try:
            agent_type = (
                agent.agent_type.value
                if hasattr(agent.agent_type, "value")
                else str(agent.agent_type)
            )
        except Exception:
            agent_type = "Unknown"

        # Determine status emoji
        status_icon = "🟢" if (hasattr(agent, "endpoint") and agent.endpoint) else "⚪"
        status_text = "Active" if status_icon == "🟢" else "Inactive"

        # Build details view with better formatting
        details = f"""╭─ [bold cyan]🤖 Agent Details[/bold cyan] ─────────────────────────────────────╮

{status_icon} [bold yellow]Status:[/bold yellow] {status_text}

[bold cyan]━━━ Basic Information ━━━[/bold cyan]

  [bold]🆔 ID:[/bold]
     {agent.id}
  
  [bold]📛 Name:[/bold]
     {agent.name or "[dim]Unnamed[/dim]"}
  
  [bold]🏷️  Type:[/bold]
     {agent_type}
  
  [bold]📅 Created:[/bold]
     {created}

[bold cyan]━━━ Configuration ━━━[/bold cyan]

  [bold]🌐 Endpoint:[/bold]
     {agent.endpoint or "[dim]Not specified[/dim]"}
  
  [bold]📝 Description:[/bold]
     {agent.description or "[dim]No description provided[/dim]"}
"""

        if hasattr(agent, "organization") and agent.organization:
            details += f"\n  [bold]🏢 Organization:[/bold]\n     {agent.organization}\n"

        # Add metadata section if available
        if hasattr(agent, "metadata") and agent.metadata:
            details += "\n[bold cyan]━━━ Metadata ━━━[/bold cyan]\n\n"
            try:
                import json

                metadata_str = json.dumps(agent.metadata, indent=2)
                details += f"  {metadata_str}\n"
            except Exception:
                details += f"  {str(agent.metadata)}\n"

        details += "\n╰────────────────────────────────────────────────────────────╯\n"
        details += (
            "\n[dim italic]💡 Press 'd' to delete this agent or 'F5' to refresh[/dim]"
        )

        details_widget.update(details)
