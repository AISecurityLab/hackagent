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
Results Tab

View and analyze attack results.
"""

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Label, Select, Static

from hackagent.cli.config import CLIConfig


class ResultsTab(Container):
    """Results tab for viewing attack results."""

    DEFAULT_CSS = ""

    BINDINGS = [
        Binding("enter", "view_result", "View Details"),
        Binding("s", "show_summary", "Summary"),
    ]

    def __init__(self, cli_config: CLIConfig):
        """Initialize results tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__()
        self.cli_config = cli_config
        self.results_data = []
        self.selected_result = None

    def compose(self) -> ComposeResult:
        """Compose the results layout."""
        # Title
        yield Static(
            "[bold cyan]━━━ Attack Results ━━━[/bold cyan]", id="results-title"
        )

        # Summary statistics with icons
        yield Static("[bold yellow]📊 Statistics[/bold yellow]")
        with Horizontal():
            yield Static("📊 [bold]Total:[/bold] [cyan]0[/cyan]", id="total-stat")
            yield Static(
                "✅ [bold]Completed:[/bold] [green]0[/green]", id="completed-stat"
            )
            yield Static(
                "🔄 [bold]Running:[/bold] [yellow]0[/yellow]", id="running-stat"
            )
            yield Static("❌ [bold]Failed:[/bold] [red]0[/red]", id="failed-stat")

        # Toolbar
        with Horizontal():
            yield Button("🔄 Refresh", id="refresh-results", variant="primary")
            yield Label("Filter:")
            yield Select(
                [
                    ("All", "all"),
                    ("Pending", "pending"),
                    ("Running", "running"),
                    ("Completed", "completed"),
                    ("Failed", "failed"),
                ],
                id="status-filter",
                value="all",
            )
            yield Label("Limit:")
            yield Select(
                [("10", "10"), ("25", "25"), ("50", "50"), ("100", "100")],
                id="limit-select",
                value="25",
            )

        # Results table
        yield Static("\n[bold yellow]📋 Results[/bold yellow]")
        table = DataTable(zebra_stripes=True, cursor_type="row")
        table.add_columns("ID", "Agent", "Attack Type", "Status", "Created")
        yield table

        # Details section with scrolling
        yield Static("\n[bold yellow]📝 Details & Logs[/bold yellow]")
        with VerticalScroll():
            yield Static(
                "[dim]Select a result to view details and logs[/dim]",
                id="result-details",
            )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Show loading message immediately
        try:
            details_widget = self.query_one("#result-details", Static)
            details_widget.update("[cyan]Loading results from API...[/cyan]")
        except Exception:
            pass

        # Initial load - call refresh_data directly to populate initial state
        try:
            self.refresh_data()
        except Exception as e:
            # If initial load fails, show error
            try:
                details_widget = self.query_one("#result-details", Static)
                details_widget.update(
                    f"[red]Failed to load data: {str(e)}[/red]\n\n[dim]Press F5 to retry[/dim]"
                )
            except Exception:
                pass

        # Periodically refresh results so running experiments are reflected
        # in the UI automatically.
        try:
            # Refresh every 5 seconds to show live updates
            # set_interval runs on the main thread, so refresh_data can update UI directly
            self.set_interval(5, self.refresh_data, name="results-refresh")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-results":
            self.refresh_data()
            self.app.show_success("Results refreshed")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select dropdown changes."""
        if event.select.id in ["status-filter", "limit-select"]:
            self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the results table."""
        table = self.query_one(DataTable)
        row_key = event.row_key
        row_index = table.get_row_index(row_key)

        if row_index < len(self.results_data):
            self.selected_result = self.results_data[row_index]
            self._show_result_details()

    def refresh_data(self) -> None:
        """Refresh results data from API."""
        try:
            from hackagent.api.result import result_list
            from hackagent.client import AuthenticatedClient

            # Get filter values
            status_sel = self.query_one("#status-filter", Select).value
            limit_sel = self.query_one("#limit-select", Select).value

            # Ensure we have strings (Select.value can be None/NoSelection)
            status_filter = str(status_sel) if status_sel is not None else "all"
            try:
                limit = int(limit_sel) if limit_sel is not None else 25
            except Exception:
                limit = 25

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

            # Build query parameters - don't pass limit to API, we'll limit client-side
            params = {}
            if status_filter and status_filter != "all":
                params["evaluation_status"] = status_filter.upper()

            response = result_list.sync_detailed(client=client)

            if response.status_code == 200 and response.parsed:
                # Get all results and filter client-side
                all_results = response.parsed.results if response.parsed.results else []

                # Apply limit client-side
                self.results_data = all_results[:limit] if all_results else []

                if not self.results_data:
                    self._show_empty_state(
                        "No results found. Run an attack to see results here."
                    )
                else:
                    self._update_table()
                    self._update_summary_stats()
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
                    f"Failed to fetch results: {response.status_code}"
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
                    f"Error loading results: {error_type}\n{error_msg}"
                )

    def _show_empty_state(self, message: str) -> None:
        """Show an empty state message when no data is available.

        Args:
            message: Message to display
        """
        table = self.query_one(DataTable)
        table.clear()

        # Update stats to zero
        self.query_one("#total-stat", Static).update("[bold]Total:[/bold] 0")
        self.query_one("#completed-stat", Static).update(
            "[bold]Completed:[/bold] [green]0[/green]"
        )
        self.query_one("#running-stat", Static).update(
            "[bold]Running:[/bold] [yellow]0[/yellow]"
        )
        self.query_one("#failed-stat", Static).update(
            "[bold]Failed:[/bold] [red]0[/red]"
        )

        # Show message in details area
        details_widget = self.query_one("#result-details", Static)
        details_widget.update(
            f"[yellow]{message}[/yellow]\n\n[dim]Press F5 or click Refresh to retry[/dim]"
        )

    def _update_table(self) -> None:
        """Update the results table with current data."""
        try:
            table = self.query_one(DataTable)
            table.clear()

            for result in self.results_data:
                # Format creation date
                created = "Unknown"
                if hasattr(result, "created_at") and result.created_at:
                    try:
                        if isinstance(result.created_at, datetime):
                            created = result.created_at.strftime("%Y-%m-%d %H:%M")
                        else:
                            created = str(result.created_at)[:16]
                    except (AttributeError, ValueError, TypeError):
                        created = str(result.created_at)[:16]

                # Get status
                status_display = "Unknown"
                if hasattr(result, "evaluation_status"):
                    status_val = result.evaluation_status
                    if hasattr(status_val, "value"):
                        status_display = status_val.value
                    else:
                        status_display = str(status_val)

                table.add_row(
                    str(result.id)[:8] + "...",
                    getattr(result, "agent_name", "Unknown"),
                    getattr(result, "attack_type", "Unknown"),
                    status_display,
                    created,
                )

            # Show success message
            details_widget = self.query_one("#result-details", Static)
            details_widget.update(
                f"[green]✓ Loaded {len(self.results_data)} result(s)[/green]\n\n[dim]Select a result to view details[/dim]"
            )

        except Exception as e:
            # If table update fails, show error
            details_widget = self.query_one("#result-details", Static)
            details_widget.update(f"[red]Error updating table: {str(e)}[/red]")

    def _update_summary_stats(self) -> None:
        """Update summary statistics."""
        total = len(self.results_data)
        completed = 0
        running = 0
        failed = 0

        for result in self.results_data:
            if hasattr(result, "evaluation_status"):
                status = (
                    result.evaluation_status.value
                    if hasattr(result.evaluation_status, "value")
                    else str(result.evaluation_status)
                )
                status = status.upper()

                if status == "COMPLETED":
                    completed += 1
                elif status == "RUNNING":
                    running += 1
                elif status == "FAILED":
                    failed += 1

        self.query_one("#total-stat", Static).update(
            f"📊 [bold]Total:[/bold] [cyan]{total}[/cyan]"
        )
        self.query_one("#completed-stat", Static).update(
            f"✅ [bold]Completed:[/bold] [green]{completed}[/green]"
        )
        self.query_one("#running-stat", Static).update(
            f"🔄 [bold]Running:[/bold] [yellow]{running}[/yellow]"
        )
        self.query_one("#failed-stat", Static).update(
            f"❌ [bold]Failed:[/bold] [red]{failed}[/red]"
        )

    def _show_result_details(self) -> None:
        """Show details of the selected result."""
        if not self.selected_result:
            return

        result = self.selected_result
        details_widget = self.query_one("#result-details", Static)

        # Fetch full result details from API including run information
        try:
            import httpx

            from hackagent.api.result import result_retrieve
            from hackagent.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
                timeout=httpx.Timeout(5.0, connect=5.0),  # 5 second timeout
            )

            response = result_retrieve.sync_detailed(client=client, id=str(result.id))

            if response.status_code == 200 and response.parsed:
                result = response.parsed  # Use full result with all details
        except Exception:
            # If fetch fails, continue with cached result
            pass

        # Format creation date
        created = "Unknown"
        if hasattr(result, "created_at") and result.created_at:
            try:
                if isinstance(result.created_at, datetime):
                    created = result.created_at.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created = str(result.created_at)
            except (AttributeError, ValueError, TypeError):
                created = str(result.created_at)

        # Get status
        status_display = "Unknown"
        if hasattr(result, "evaluation_status"):
            status_val = result.evaluation_status
            if hasattr(status_val, "value"):
                status_display = status_val.value
            else:
                status_display = str(status_val)

        # Status color and icon based on status
        status_color = "yellow"
        status_icon = "🔄"
        if status_display.upper() == "COMPLETED":
            status_color = "green"
            status_icon = "✅"
        elif status_display.upper() == "FAILED":
            status_color = "red"
            status_icon = "❌"
        elif status_display.upper() == "RUNNING":
            status_color = "cyan"
            status_icon = "⚡"
        elif status_display.upper() == "PENDING":
            status_color = "yellow"
            status_icon = "⏳"

        details = f"""[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]
[bold cyan]📋 RESULT DETAILS[/bold cyan]
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]

[bold yellow]Basic Information[/bold yellow]
  🆔 [bold]ID:[/bold] [dim]{result.id}[/dim]
  🤖 [bold]Agent:[/bold] [cyan]{getattr(result, "agent_name", "Unknown")}[/cyan]
  ⚔️  [bold]Attack Type:[/bold] [green]{getattr(result, "attack_type", "Unknown")}[/green]
  {status_icon} [bold]Status:[/bold] [{status_color}]{status_display}[/{status_color}]
  📅 [bold]Created:[/bold] {created}
"""

        # Add run information if available
        if hasattr(result, "run") and result.run:
            run = result.run
            details += "\n[bold yellow]⚡ Execution Details[/bold yellow]\n"
            if hasattr(run, "id"):
                details += f"  🆔 [bold]Run ID:[/bold] [dim]{run.id}[/dim]\n"
            if hasattr(run, "status"):
                run_status = (
                    run.status.value
                    if hasattr(run.status, "value")
                    else str(run.status)
                )
                details += f"  📊 [bold]Run Status:[/bold] {run_status}\n"
            if hasattr(run, "progress"):
                progress = run.progress
                progress_bar = "█" * int(progress / 10) + "░" * (
                    10 - int(progress / 10)
                )
                details += f"  📈 [bold]Progress:[/bold] {progress}% [{progress_bar}]\n"
            if hasattr(run, "started_at") and run.started_at:
                details += f"  ⏰ [bold]Started:[/bold] {run.started_at}\n"
            if hasattr(run, "completed_at") and run.completed_at:
                details += f"  🏁 [bold]Completed:[/bold] {run.completed_at}\n"
            if hasattr(run, "error_message") and run.error_message:
                details += f"  ⚠️  [bold]Error:[/bold] [red]{run.error_message}[/red]\n"

        # Add attack configuration
        if hasattr(result, "attack_config") and result.attack_config:
            details += "\n[bold cyan]═══ Attack Configuration ═══[/bold cyan]\n"
            try:
                import json

                if isinstance(result.attack_config, dict):
                    config_str = json.dumps(result.attack_config, indent=2)
                    if len(config_str) > 300:
                        config_str = config_str[:300] + "..."
                    details += f"[dim]{config_str}[/dim]\n"
                else:
                    details += f"[dim]{str(result.attack_config)[:300]}[/dim]\n"
            except Exception:
                details += f"[dim]{str(result.attack_config)[:300]}[/dim]\n"

        # Add goals if available
        if hasattr(result, "goals") and result.goals:
            goals = result.goals if isinstance(result.goals, list) else [result.goals]
            details += "\n[bold cyan]═══ Attack Goals ═══[/bold cyan]\n"
            for i, goal in enumerate(goals[:5], 1):
                details += f"  {i}. [dim]{str(goal)[:150]}[/dim]\n"
            if len(goals) > 5:
                details += f"  [yellow]... and {len(goals) - 5} more goals[/yellow]\n"

        # Add run configuration if available
        if hasattr(result, "run_config") and result.run_config:
            details += "\n[bold cyan]═══ Run Configuration ═══[/bold cyan]\n"
            try:
                import json

                if isinstance(result.run_config, dict):
                    run_config_str = json.dumps(result.run_config, indent=2)
                    if len(run_config_str) > 300:
                        run_config_str = run_config_str[:300] + "..."
                    details += f"[dim]{run_config_str}[/dim]\n"
                else:
                    details += f"[dim]{str(result.run_config)[:300]}[/dim]\n"
            except Exception:
                details += f"[dim]{str(result.run_config)[:300]}[/dim]\n"

        # Show logs if available - THIS IS THE MOST IMPORTANT PART
        if hasattr(result, "logs") and result.logs:
            details += (
                "\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n"
            )
            details += "[bold cyan]📝 EXECUTION LOGS[/bold cyan]\n"
            details += (
                "[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n\n"
            )

            # Parse and display logs line by line with better formatting
            logs_str = str(result.logs)
            log_lines = logs_str.split("\n")

            # Show all logs if running, or last 30 lines if completed
            if status_display.upper() == "RUNNING":
                display_lines = log_lines  # Show everything for running attacks
                details += (
                    "[yellow]⚡ LIVE LOGS (Auto-refreshing every 5s)[/yellow]\n\n"
                )
            else:
                display_lines = log_lines[-30:] if len(log_lines) > 30 else log_lines
                if len(log_lines) > 30:
                    details += f"[dim]... ({len(log_lines) - 30} earlier lines)[/dim]\n"

            for line in display_lines:
                line = line.strip()
                if not line:
                    continue
                # Color code log levels
                if "ERROR" in line.upper() or "FAIL" in line.upper():
                    details += f"[red]❌ {line}[/red]\n"
                elif "WARN" in line.upper():
                    details += f"[yellow]⚠️  {line}[/yellow]\n"
                elif "SUCCESS" in line.upper() or "COMPLETE" in line.upper():
                    details += f"[green]✅ {line}[/green]\n"
                elif "INFO" in line.upper() or "START" in line.upper():
                    details += f"[cyan]ℹ️  {line}[/cyan]\n"
                else:
                    details += f"[dim]{line}[/dim]\n"

        # Show result data if available
        if hasattr(result, "data") and result.data:
            details += "\n[bold yellow]📊 Result Data[/bold yellow]\n"
            try:
                import json

                if isinstance(result.data, dict):
                    data_str = json.dumps(result.data, indent=2)
                    # Show first 800 chars for result data
                    if len(data_str) > 800:
                        data_str = (
                            data_str[:800]
                            + "\n[yellow]... (truncated, see full results in API)[/yellow]"
                        )
                    details += f"[dim]{data_str}[/dim]"
                else:
                    details += f"[dim]{str(result.data)[:800]}[/dim]"
            except Exception:
                details += f"[dim]{str(result.data)[:800]}[/dim]"

        details += (
            "\n\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n"
        )
        details += "[dim]💡 Tip: This view auto-refreshes every 5 seconds for running attacks\n"
        details += "Press F5 to refresh manually, or select another result[/dim]"

        details_widget.update(details)
