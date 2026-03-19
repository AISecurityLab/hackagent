# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Dashboard Tab

Overview and statistics for HackAgent.
"""

from typing import Any
import json

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Tree

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.base import BaseTab


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
            "\n[bold yellow]📝 Recent Activity & Traces[/bold yellow]",
            id="activity-header",
        )

        yield Tree("Activity Log", id="activity-tree")
        with VerticalScroll(id="activity-scroll"):
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
            from hackagent.server.api.agent import agent_list
            from hackagent.server.api.result import result_list

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
                self.query_one("#activity-tree", Tree).display = False
                self.query_one("#activity-scroll").display = True
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
            self.query_one("#activity-tree", Tree).display = False
            self.query_one("#activity-scroll").display = True
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
                activity_log.update(
                    f"[red]Error updating stats: {_escape(str(e))}[/red]"
                )
            except Exception:
                pass

    def _update_activity_log(self, agents: list, results: list) -> None:
        """Update activity log with recent items.

        Args:
            agents: List of agents
            results: List of results
        """
        try:
            tree = self.query_one("#activity-tree", Tree)
            self.query_one("#activity-scroll").display = False
            tree.display = True

            # Clear existing data
            tree.clear()
            tree.root.expand()

            # Add recent agents
            if agents:
                agents_node = tree.root.add(
                    "[bold cyan]🤖 Recent Agents[/bold cyan]", expand=True
                )
                for i, agent in enumerate(agents[:3], 1):
                    agent_type = (
                        agent.agent_type.value
                        if hasattr(agent.agent_type, "value")
                        else agent.agent_type
                    )
                    agent_name = _escape(agent.name) if agent.name else "Unnamed"
                    agents_node.add_leaf(
                        f"{i}. [cyan]{agent_name}[/cyan] [dim]({_escape(agent_type)})[/dim]"
                    )

            # Add recent results and their traces
            if results:
                results_node = tree.root.add(
                    "[bold green]📋 Recent Results & Traces[/bold green]", expand=True
                )
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
                    result_label = f"{i}. [yellow]{_escape(attack_type)}[/yellow] → [{status_color}]{_escape(status)}[/{status_color}]"

                    res_node = results_node.add(result_label, expand=(i == 1))

                    # Add nested traces if available
                    traces = getattr(result, "traces", [])
                    if not traces:
                        res_node.add_leaf("[dim]No traces available[/dim]")
                    else:
                        for trace_idx, trace in enumerate(traces, 1):
                            step_type = getattr(trace, "step_type", "Unknown")
                            step_type_str = (
                                step_type.value
                                if hasattr(step_type, "value")
                                else str(step_type)
                            )

                            content = getattr(trace, "content", None)
                            preview = ""
                            if content:
                                try:
                                    if isinstance(content, str):
                                        c_dict = json.loads(content)
                                    else:
                                        c_dict = content

                                    if isinstance(c_dict, dict):
                                        if "thought" in c_dict:
                                            preview = f": {_escape(str(c_dict['thought'])[:60])}..."
                                        elif "tool_name" in c_dict:
                                            preview = f" ([bright_magenta]🔧 {_escape(str(c_dict['tool_name']))}[/bright_magenta])"
                                        elif "response" in c_dict:
                                            preview = f": {_escape(str(c_dict['response'])[:60])}..."
                                    else:
                                        preview = f": {_escape(str(content)[:60])}..."
                                except Exception:
                                    preview = f": {_escape(str(content)[:60])}..."

                            trace_label = (
                                f"└─ [magenta]{step_type_str}[/magenta]{preview}"
                            )

                            # Expand first few traces
                            trace_node = res_node.add(
                                trace_label, expand=(trace_idx <= 3)
                            )

                            # Add full content as leaf
                            if content:
                                try:
                                    content_str = (
                                        json.dumps(content, indent=2)
                                        if isinstance(content, dict)
                                        else str(content)
                                    )
                                    # limit leaf content to prevent slowing down TUI too much
                                    content_str = content_str[:1000] + (
                                        "..." if len(content_str) > 1000 else ""
                                    )
                                    trace_node.add_leaf(
                                        f"[dim]{_escape(content_str)}[/dim]"
                                    )
                                except Exception:
                                    pass

        except Exception as e:
            # Fallback to static log on error
            try:
                self.query_one("#activity-tree", Tree).display = False
                self.query_one("#activity-scroll").display = True
                activity_log = self.query_one("#activity-log", Static)
                activity_log.update(
                    f"[red]Error rendering traces: {_escape(str(e))}[/red]"
                )
            except Exception:
                pass
