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

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Button, DataTable, Static

from hackagent.cli.config import CLIConfig


class AgentsTab(Container):
    """Agents tab for managing AI agents."""

    DEFAULT_CSS = ""

    BINDINGS = [
        Binding("n", "new_agent", "New Agent"),
        Binding("d", "delete_agent", "Delete Agent"),
        Binding("enter", "view_agent", "View Details"),
    ]

    def __init__(self, cli_config: CLIConfig):
        """Initialize agents tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__()
        self.cli_config = cli_config
        self.agents_data = []
        self.selected_agent = None

    def compose(self) -> ComposeResult:
        """Compose the agents layout."""
        with Horizontal(classes="toolbar"):
            yield Button("Refresh", id="refresh-agents", variant="primary")
            yield Button("New Agent", id="new-agent", variant="success")
            yield Button("Delete", id="delete-agent", variant="error")

        table = DataTable(classes="agents-table", zebra_stripes=True, cursor_type="row")
        table.add_columns("ID", "Name", "Type", "Endpoint", "Created")
        yield table

        yield Static(
            "[dim]Select an agent to view details[/dim]",
            classes="agent-details",
            id="agent-details",
        )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Show loading message immediately
        try:
            details_widget = self.query_one("#agent-details", Static)
            details_widget.update("[cyan]Loading agents from API...[/cyan]")
        except Exception:
            pass

        # Initial load - call refresh_data directly to populate initial state
        try:
            self.refresh_data()
        except Exception as e:
            # If initial load fails, show error
            try:
                details_widget = self.query_one("#agent-details", Static)
                details_widget.update(
                    f"[red]Failed to load data: {str(e)}[/red]\n\n[dim]Press F5 to retry[/dim]"
                )
            except Exception:
                pass

        # Auto-refresh every 5 seconds
        try:
            self.set_interval(5, self.refresh_data, name="agents-refresh")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-agents":
            self.refresh_data()
            self.app.show_success("Agents refreshed")
        elif event.button.id == "new-agent":
            self.app.show_info("Create new agent feature coming soon!")
        elif event.button.id == "delete-agent":
            if self.selected_agent:
                self.app.show_info("Delete agent feature coming soon!")
            else:
                self.app.show_warning("Please select an agent first")

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
            from hackagent.client import AuthenticatedClient

            # Validate configuration
            if not self.cli_config.api_key:
                self.app.show_error(
                    "API key not configured. Run 'hackagent init' to set up."
                )
                self._show_empty_state("API key not configured")
                return

            import httpx

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
                timeout=httpx.Timeout(5.0, connect=5.0),  # 5 second timeout
            )

            response = agent_list.sync_detailed(client=client)

            if response.status_code == 200 and response.parsed:
                self.agents_data = (
                    response.parsed.results if response.parsed.results else []
                )

                # Show loading status
                details_widget = self.query_one("#agent-details", Static)
                details_widget.update(
                    f"[cyan]Fetched {len(self.agents_data)} agents from API...[/cyan]"
                )

                if not self.agents_data:
                    self._show_empty_state(
                        "No agents found. Create an agent to get started."
                    )
                else:
                    self._update_table()
            elif response.status_code == 401:
                self.app.show_error("Authentication failed. Check your API key.")
                self._show_empty_state("Authentication failed")
            elif response.status_code == 403:
                self.app.show_error("Access forbidden. Check your API key permissions.")
                self._show_empty_state("Access forbidden")
            else:
                error_msg = f"API error: {response.status_code}"
                if hasattr(response, "content"):
                    error_msg += f" - {response.content[:200]}"
                self.app.show_error(error_msg)
                self._show_empty_state(
                    f"Failed to fetch agents: {response.status_code}"
                )

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # Provide helpful error messages
            if "timeout" in error_msg.lower() or "TimeoutException" in error_type:
                self._show_empty_state(
                    f"⚠️ Connection Timeout\n\n"
                    f"Cannot reach API: {self.cli_config.base_url}\n"
                    f"Check your network connection and retry."
                )
            elif "401" in error_msg or "authentication" in error_msg.lower():
                self._show_empty_state(
                    "🔒 Authentication Failed\n\n"
                    "Your API key is invalid.\n"
                    "Run: hackagent config set --api-key YOUR_KEY"
                )
            else:
                self._show_empty_state(
                    f"Error loading agents: {error_type}\n{error_msg}"
                )

    def _show_empty_state(self, message: str) -> None:
        """Show an empty state message when no data is available.

        Args:
            message: Message to display
        """
        table = self.query_one(DataTable)
        table.clear()

        # Show message in details area
        details_widget = self.query_one("#agent-details", Static)
        details_widget.update(
            f"[yellow]{message}[/yellow]\n\n[dim]Press F5 or click Refresh to retry[/dim]"
        )

    def _update_table(self) -> None:
        """Update the agents table with current data."""
        details_widget = self.query_one("#agent-details", Static)
        try:
            table = self.query_one(DataTable)

            # Debug: Show we're starting the update
            details_widget.update(
                f"[cyan]Updating table with {len(self.agents_data)} agents...[/cyan]"
            )

            table.clear()

            rows_added = 0
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
                            (agent.endpoint[:40] + "...")
                            if len(agent.endpoint) > 40
                            else agent.endpoint
                        )
                except Exception:
                    endpoint = "N/A"

                table.add_row(
                    str(agent.id)[:8] + "...",
                    agent.name or "Unnamed",
                    agent_type,
                    endpoint,
                    created,
                )
                rows_added += 1

            # Show success message
            details_widget.update(
                f"[green]✓ Successfully loaded {rows_added} agent(s)[/green]\n\n[dim]Select an agent to view details[/dim]"
            )

        except Exception as e:
            # If table update fails, show detailed error
            import traceback

            error_details = traceback.format_exc()
            details_widget.update(
                f"[red]Error updating table:[/red]\n"
                f"[yellow]{type(e).__name__}: {str(e)}[/yellow]\n\n"
                f"[dim]{error_details[:500]}[/dim]"
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

        details = f"""[bold cyan]Agent Details[/bold cyan]

[bold]ID:[/bold] {agent.id}
[bold]Name:[/bold] {agent.name or "Unnamed"}
[bold]Type:[/bold] {agent.agent_type.value if hasattr(agent.agent_type, "value") else str(agent.agent_type)}
[bold]Endpoint:[/bold] {agent.endpoint or "Not specified"}
[bold]Description:[/bold] {agent.description or "No description"}
[bold]Created:[/bold] {created}
"""
        if hasattr(agent, "organization") and agent.organization:
            details += f"[bold]Organization:[/bold] {agent.organization}\n"

        details_widget.update(details)
