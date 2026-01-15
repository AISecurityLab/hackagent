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
Dashboard Tab

Overview and statistics for HackAgent.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.base import BaseTab


class DashboardTab(BaseTab):
    """Dashboard tab showing overview and statistics."""

    DEFAULT_CSS = ""

    def __init__(self, cli_config: CLIConfig):
        """Initialize dashboard tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__(cli_config)
        self.stats = {
            "agents": 0,
            "attacks": 0,
            "results": 0,
            "success_rate": 0.0,
        }

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        # Title section
        yield Static(
            "[bold cyan]━━━ Dashboard Overview ━━━[/bold cyan]", id="dashboard-title"
        )

        # Statistics section with better formatting
        yield Static("[bold yellow]📊 Statistics[/bold yellow]", id="stats-header")

        with Horizontal():
            with Vertical():
                yield Static("🤖 [bold]Agents[/bold]\n[cyan]0[/cyan]", id="stat-agents")
                yield Static(
                    "⚔️  [bold]Attacks[/bold]\n[green]0[/green]", id="stat-attacks"
                )
            with Vertical():
                yield Static(
                    "📋 [bold]Results[/bold]\n[yellow]0[/yellow]", id="stat-results"
                )
                yield Static(
                    "✓ [bold]Success Rate[/bold]\n[magenta]0%[/magenta]",
                    id="stat-success",
                )

        # Activity section
        yield Static(
            "\n[bold yellow]📝 Recent Activity[/bold yellow]", id="activity-header"
        )

        with VerticalScroll():
            yield Static("[dim]Waiting for data...[/dim]", id="activity-log")

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Call base class mount to handle initial refresh
        super().on_mount()

        # Enable auto-refresh every 5 seconds
        self.enable_auto_refresh(interval=5.0)

    def refresh_data(self) -> None:
        """Refresh dashboard data from API."""
        try:
            from hackagent.api.agent import agent_list
            from hackagent.api.result import result_list

            # Validate configuration
            if not self.cli_config.api_key:
                activity_log = self.query_one("#activity-log", Static)
                activity_log.update(
                    "[red]API key not configured[/red]\n\n"
                    "[yellow]Run 'hackagent init' to set up your API key[/yellow]\n\n"
                    "[dim]You need to configure your HackAgent API key before you can use the TUI.[/dim]"
                )
                return

            # Create API client using base class method
            client = self.create_api_client()

            agents_data = []
            results_data = []

            # Fetch agents count
            agents_response = agent_list.sync_detailed(client=client)
            if agents_response.status_code == 200 and agents_response.parsed:
                agents_data = (
                    agents_response.parsed.results
                    if agents_response.parsed.results
                    else []
                )
                self.stats["agents"] = len(agents_data)
            elif agents_response.status_code == 401:
                activity_log = self.query_one("#activity-log", Static)
                activity_log.update(
                    "[red]Authentication failed[/red]\n\n"
                    "[yellow]Your API key is invalid or expired[/yellow]\n\n"
                    "[dim]Run 'hackagent config set --api-key YOUR_KEY' to update[/dim]"
                )
                return
            elif agents_response.status_code == 403:
                activity_log = self.query_one("#activity-log", Static)
                activity_log.update(
                    "[red]Access forbidden[/red]\n\n"
                    "[yellow]Your API key doesn't have permission to access this resource[/yellow]"
                )
                return

            # Fetch results count
            results_response = result_list.sync_detailed(client=client)
            if results_response.status_code == 200 and results_response.parsed:
                results_data = (
                    results_response.parsed.results
                    if results_response.parsed.results
                    else []
                )
                self.stats["results"] = len(results_data)

                # Calculate success rate
                if results_data:
                    completed = sum(
                        1
                        for r in results_data
                        if hasattr(r, "evaluation_status")
                        and str(
                            r.evaluation_status.value
                            if hasattr(r.evaluation_status, "value")
                            else r.evaluation_status
                        ).upper()
                        == "COMPLETED"
                    )
                    self.stats["success_rate"] = (
                        (completed / len(results_data)) * 100
                        if len(results_data) > 0
                        else 0
                    )

            # Update stat cards
            self._update_stat_cards()

            # Update activity log
            if not agents_data and not results_data:
                activity_log = self.query_one("#activity-log", Static)
                activity_log.update(
                    "[yellow]No data found[/yellow]\n\n"
                    "[dim]Create agents and run attacks to see activity here.[/dim]\n\n"
                    "[cyan]Quick Start:[/cyan]\n"
                    "1. Go to Agents tab to create an agent\n"
                    "2. Go to Attacks tab to run security tests\n"
                    "3. Check Results tab to see outcomes"
                )
            else:
                self._update_activity_log(agents_data, results_data)

        except Exception as e:
            # Display error in activity log with helpful context
            activity_log = self.query_one("#activity-log", Static)

            error_type = type(e).__name__
            error_msg = str(e)

            # Provide context-specific help
            if "timeout" in error_msg.lower() or "TimeoutException" in error_type:
                activity_log.update(
                    f"[red]⚠️ Connection Timeout[/red]\n\n"
                    f"[yellow]Cannot reach HackAgent API:[/yellow]\n{self.cli_config.base_url}\n\n"
                    f"[cyan]Possible causes:[/cyan]\n"
                    f"• API server is down or unreachable\n"
                    f"• Network connection issues\n"
                    f"• Firewall blocking the connection\n\n"
                    f"[dim]Press F5 to retry when connection is restored[/dim]\n\n"
                    f"[bold]Offline Mode:[/bold]\n"
                    f"You can still use the Attacks tab with local agents\n"
                    f"(results won't be synced to the platform)"
                )
            elif "401" in error_msg or "authentication" in error_msg.lower():
                activity_log.update(
                    "[red]Authentication Failed[/red]\n\n"
                    "[yellow]Your API key is invalid or expired[/yellow]\n\n"
                    "[cyan]To fix:[/cyan]\n"
                    "Run: hackagent config set --api-key YOUR_KEY\n\n"
                    "[dim]Press F5 to retry after updating[/dim]"
                )
            else:
                activity_log.update(
                    f"[red]Error loading data:[/red]\n{error_type}\n\n"
                    f"[yellow]Details:[/yellow]\n{error_msg}\n\n"
                    f"[dim]Press F5 to retry[/dim]"
                )

    def _update_stat_cards(self) -> None:
        """Update the statistics cards with current data."""
        try:
            # Get the values
            agents_val = self.stats.get("agents", 0)
            attacks_val = self.stats.get("attacks", 0)
            results_val = self.stats.get("results", 0)
            success_val = self.stats.get("success_rate", 0)

            # Update each stat widget by ID with icons and formatting
            stat_agents = self.query_one("#stat-agents", Static)
            stat_agents.update(f"🤖 [bold]Agents[/bold]\n[cyan]{agents_val}[/cyan]")

            stat_attacks = self.query_one("#stat-attacks", Static)
            stat_attacks.update(
                f"⚔️  [bold]Attacks[/bold]\n[green]{attacks_val}[/green]"
            )

            stat_results = self.query_one("#stat-results", Static)
            stat_results.update(
                f"📋 [bold]Results[/bold]\n[yellow]{results_val}[/yellow]"
            )

            stat_success = self.query_one("#stat-success", Static)
            stat_success.update(
                f"✓ [bold]Success Rate[/bold]\n[magenta]{success_val:.1f}%[/magenta]"
            )

        except Exception as e:
            # Show error in activity log if update fails
            try:
                activity_log = self.query_one("#activity-log", Static)
                activity_log.update(f"[red]Error updating stats: {str(e)}[/red]")
            except Exception:
                pass

    def _update_activity_log(self, agents: list, results: list) -> None:
        """Update activity log with recent items.

        Args:
            agents: List of agents
            results: List of results
        """
        activity_log = self.query_one("#activity-log", Static)
        log_lines = []

        # Add recent agents with icons
        if agents:
            log_lines.append("[bold cyan]🤖 Recent Agents:[/bold cyan]")
            for i, agent in enumerate(agents[:3], 1):
                agent_type = (
                    agent.agent_type.value
                    if hasattr(agent.agent_type, "value")
                    else agent.agent_type
                )
                log_lines.append(
                    f"  {i}. [cyan]{agent.name or 'Unnamed'}[/cyan] [dim]({agent_type})[/dim]"
                )
            log_lines.append("")

        # Add recent results with status colors
        if results:
            log_lines.append("[bold green]📋 Recent Results:[/bold green]")
            for i, result in enumerate(results[:5], 1):
                status = "Unknown"
                status_color = "dim"

                if hasattr(result, "evaluation_status"):
                    status = (
                        result.evaluation_status.value
                        if hasattr(result.evaluation_status, "value")
                        else str(result.evaluation_status)
                    )
                    # Color code based on status
                    if status.upper() == "COMPLETED":
                        status_color = "green"
                    elif status.upper() == "RUNNING":
                        status_color = "yellow"
                    elif status.upper() == "FAILED":
                        status_color = "red"

                attack_type = getattr(result, "attack_type", "Unknown")
                log_lines.append(
                    f"  {i}. [yellow]{attack_type}[/yellow] → [{status_color}]{status}[/{status_color}]"
                )

        if not log_lines:
            log_lines = ["[dim]No recent activity yet...[/dim]"]

        activity_log.update("\n".join(log_lines))
