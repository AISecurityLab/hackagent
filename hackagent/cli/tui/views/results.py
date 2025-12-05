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
import json
from typing import Any
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Label, Select, Static

from hackagent.cli.config import CLIConfig


class ResultsTab(Container):
    """Results tab for viewing attack results with split view."""

    DEFAULT_CSS = """
    ResultsTab {
        layout: horizontal;
    }
    
    ResultsTab #results-left-panel {
        width: 30%;
        border-right: solid $primary;
    }
    
    ResultsTab #results-right-panel {
        width: 70%;
    }
    
    ResultsTab #results-table {
        height: 100%;
    }
    """

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
        self.results_data: list[Any] = []
        self.selected_result: Any = None

    def compose(self) -> ComposeResult:
        """Compose the results layout with horizontal split."""
        # Left side - Results list (30%)
        with VerticalScroll(id="results-left-panel"):
            yield Static(
                "[bold cyan]🎯 Attack Results[/bold cyan]",
                classes="section-header",
            )

            with Horizontal(classes="toolbar"):
                yield Button("🔄 Refresh", id="refresh-results", variant="primary")
                yield Button("📊 CSV", id="export-csv", variant="default")
                yield Button("📄 JSON", id="export-json", variant="default")

            with Horizontal(classes="toolbar"):
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
            yield DataTable(zebra_stripes=True, cursor_type="row", id="results-table")

        # Right side - Details view (70%)
        with VerticalScroll(id="results-right-panel"):
            yield Static(
                "[bold cyan]📋 Result Details[/bold cyan]",
                classes="section-header",
            )
            yield Static(
                "[dim]💡 Select a result from the list to view full details and logs[/dim]",
                id="result-details",
            )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Initialize table columns
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            table.add_columns("ID", "Status", "Agent", "Created", "Results")
        except Exception as e:
            self.app.notify(f"Failed to initialize table: {str(e)}", severity="error")

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
                    f"[red]Failed to load data: {str(e)}[/red]\n\n[dim]Press 🔄 Refresh button or F5 to retry[/dim]"
                )
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "refresh-results":
            self.refresh_data()
        elif event.button.id == "export-csv":
            self._export_results_csv()
        elif event.button.id == "export-json":
            self._export_results_json()

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
            from hackagent.api.run import run_list
            from hackagent.client import AuthenticatedClient

            # Get filter values
            status_sel = self.query_one("#status-filter", Select).value
            limit_sel = self.query_one("#limit-select", Select).value

            # Ensure we have strings (Select.value can be None/NoSelection)
            status_filter = str(status_sel) if status_sel is not None else "all"
            limit = 25
            if limit_sel is not None:
                try:
                    limit = int(str(limit_sel))
                except (ValueError, TypeError):
                    limit = 25

            # Validate configuration
            if not self.cli_config.api_key:
                self._show_empty_state("API key not configured")
                return

            import httpx

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
                timeout=httpx.Timeout(5.0, connect=5.0),  # 5 second timeout
            )

            # Build query parameters with status filter if not "all"
            kwargs = {"client": client, "page_size": limit}
            if status_filter and status_filter != "all":
                # Map filter values to API enum
                from hackagent.models.run_list_status import RunListStatus

                status_map = {
                    "pending": RunListStatus.PENDING,
                    "running": RunListStatus.RUNNING,
                    "completed": RunListStatus.COMPLETED,
                    "failed": RunListStatus.FAILED,
                }
                if status_filter.lower() in status_map:
                    kwargs["status"] = status_map[status_filter.lower()]

            response = run_list.sync_detailed(**kwargs)

            if response.status_code == 200 and response.parsed:
                # Get all runs - these contain agent_name, attack info, etc.
                all_runs = response.parsed.results if response.parsed.results else []

                self.results_data = all_runs if all_runs else []

                if not self.results_data:
                    self._show_empty_state(
                        "No runs found. Execute an attack to see results here."
                    )
                else:
                    self._update_table()
            elif response.status_code == 401:
                self._show_empty_state("Authentication failed")
            elif response.status_code == 403:
                self._show_empty_state("Access forbidden")
            else:
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
                    "🔒 Authentication Failed\n\nYour API key is invalid.\nRun: hackagent config set --api-key YOUR_KEY"
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
        table = self.query_one("#results-table", DataTable)
        table.clear()

        # Show message in details area
        details_widget = self.query_one("#result-details", Static)
        details_widget.update(
            f"[yellow]{message}[/yellow]\n\n[dim]💡 Tip: Press F5 or click 🔄 Refresh to retry[/dim]"
        )

    def _update_table(self) -> None:
        """Update the results table with current data."""
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear()

            for run in self.results_data:
                # Get status with color coding from Run.status
                status_display = "Unknown"
                if hasattr(run, "status"):
                    status_val = run.status
                    if hasattr(status_val, "value"):
                        status_display = status_val.value
                    else:
                        status_display = str(status_val)

                    # Color code based on status
                    status_upper = status_display.upper()
                    if status_upper == "COMPLETED":
                        status_display = f"[green]✅ {status_display}[/green]"
                    elif status_upper == "RUNNING":
                        status_display = f"[cyan]🔄 {status_display}[/cyan]"
                    elif status_upper == "FAILED":
                        status_display = f"[red]❌ {status_display}[/red]"
                    elif status_upper == "PENDING":
                        status_display = f"[yellow]⏳ {status_display}[/yellow]"
                    else:
                        status_display = f"❓ {status_display}"

                # Get agent name - directly available in Run model
                agent_name = run.agent_name if hasattr(run, "agent_name") else "Unknown"

                # Get created time from timestamp
                created_time = "N/A"
                if hasattr(run, "timestamp") and run.timestamp:
                    try:
                        dt = (
                            run.timestamp
                            if isinstance(run.timestamp, datetime)
                            else datetime.fromisoformat(
                                str(run.timestamp).replace("Z", "+00:00")
                            )
                        )
                        created_time = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        created_time = str(run.timestamp)[:16]

                # Get results count as a metric
                results_count = (
                    len(run.results) if hasattr(run, "results") and run.results else 0
                )
                results_display = f"{results_count} results"

                # Add row with all columns: ID, Status, Agent, Created, Results
                table.add_row(
                    str(run.id)[:8] + "...",
                    status_display,
                    agent_name,
                    created_time,
                    results_display,
                )

            # Show success message
            details_widget = self.query_one("#result-details", Static)
            details_widget.update(
                f"[green]✅ Loaded {len(self.results_data)} run(s)[/green]\n\n"
                f"[dim]💡 Click any row to view full details including:\n"
                f"   • Agent: {self.results_data[0].agent_name if self.results_data else 'N/A'}\n"
                f"   • Organization: {self.results_data[0].organization_name if self.results_data else 'N/A'}\n"
                f"   • Run configuration\n"
                f"   • All result evaluations\n"
                f"   • Execution traces & logs[/dim]"
            )

        except Exception as e:
            # If table update fails, show error
            details_widget = self.query_one("#result-details", Static)
            details_widget.update(f"[red]❌ Error updating table: {str(e)}[/red]")

    def _parse_agent_actions(self, logs_str: str) -> list[dict[str, Any]]:
        """Parse agent actions from log strings.

        Args:
            logs_str: Raw log string

        Returns:
            List of parsed action dictionaries
        """
        import re

        actions = []
        lines = logs_str.split("\n")

        for i, line in enumerate(lines):
            # HTTP requests
            if "HTTP" in line and (
                "POST" in line or "GET" in line or "PUT" in line or "DELETE" in line
            ):
                method_match = re.search(r"(GET|POST|PUT|DELETE|PATCH)", line)
                url_match = re.search(r"(https?://[^\s]+)", line)
                if method_match and url_match:
                    actions.append(
                        {
                            "type": "http_request",
                            "method": method_match.group(1),
                            "url": url_match.group(1),
                            "line_num": i + 1,
                        }
                    )

            # Tool/Function calls
            elif "Tool:" in line or "Function:" in line or "🔧" in line:
                tool_match = re.search(r"(?:Tool|Function):\s*([\w_]+)", line)
                if tool_match:
                    tool_name = tool_match.group(1)
                    # Look for arguments in next few lines
                    args = ""
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if "Arguments:" in lines[j] or "Input:" in lines[j]:
                            args = lines[j]
                            break
                    actions.append(
                        {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": args,
                            "line_num": i + 1,
                        }
                    )

            # ADK events
            elif "ADK" in line and (
                "tool_call" in line.lower() or "tool_result" in line.lower()
            ):
                if "tool_call" in line.lower():
                    actions.append(
                        {"type": "adk_tool_call", "content": line, "line_num": i + 1}
                    )
                elif "tool_result" in line.lower():
                    actions.append(
                        {"type": "adk_tool_result", "content": line, "line_num": i + 1}
                    )

            # Model queries
            elif "Querying model" in line or "LLM" in line:
                model_match = re.search(r"model[\s:]+([\w-]+)", line)
                if model_match:
                    actions.append(
                        {
                            "type": "llm_query",
                            "model": model_match.group(1),
                            "line_num": i + 1,
                        }
                    )

        return actions

    def _show_result_details(self) -> None:
        """Show details of the selected run and its results."""
        if not self.selected_result:
            return

        run = self.selected_result  # This is a Run object now
        details_widget = self.query_one("#result-details", Static)

        # Fetch full run details from API including all results and traces
        try:
            import httpx

            from hackagent.api.run import run_retrieve
            from hackagent.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=self.cli_config.base_url,
                token=self.cli_config.api_key,
                prefix="Bearer",
                timeout=httpx.Timeout(
                    10.0, connect=10.0
                ),  # 10 second timeout for detailed data
            )

            run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
            response = run_retrieve.sync_detailed(client=client, id=run_id)

            if response.status_code == 200 and response.parsed:
                run = (
                    response.parsed
                )  # Use full run with all details, results, and traces
        except Exception as e:
            # If fetch fails, continue with cached run but show warning
            details_widget.update(
                f"[yellow]⚠️ Could not fetch full details: {str(e)}[/yellow]\n\n[dim]Showing cached data...[/dim]"
            )
            return

        # Format creation date
        created = "Unknown"
        if hasattr(run, "timestamp") and run.timestamp:
            try:
                if isinstance(run.timestamp, datetime):
                    created = run.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created = str(run.timestamp)
            except (AttributeError, ValueError, TypeError):
                created = str(run.timestamp)

        # Get status from Run
        status_display = "Unknown"
        if hasattr(run, "status"):
            status_val = run.status
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

        # Get results count and evaluation summary
        results_count = (
            len(run.results) if hasattr(run, "results") and run.results else 0
        )

        # Count evaluation statuses
        eval_summary = {
            "SUCCESSFUL_JAILBREAK": 0,
            "FAILED_JAILBREAK": 0,
            "NOT_EVALUATED": 0,
            "ERROR": 0,
            "OTHER": 0,
        }
        if hasattr(run, "results") and run.results:
            for result in run.results:
                if hasattr(result, "evaluation_status"):
                    eval_status = (
                        result.evaluation_status.value
                        if hasattr(result.evaluation_status, "value")
                        else str(result.evaluation_status)
                    )
                    if (
                        "SUCCESSFUL" in eval_status.upper()
                        and "JAILBREAK" in eval_status.upper()
                    ):
                        eval_summary["SUCCESSFUL_JAILBREAK"] += 1
                    elif (
                        "FAILED" in eval_status.upper()
                        and "JAILBREAK" in eval_status.upper()
                    ):
                        eval_summary["FAILED_JAILBREAK"] += 1
                    elif "NOT_EVALUATED" in eval_status.upper():
                        eval_summary["NOT_EVALUATED"] += 1
                    elif "ERROR" in eval_status.upper():
                        eval_summary["ERROR"] += 1
                    else:
                        eval_summary["OTHER"] += 1

        details = f"""[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]
[bold bright_white]  RUN DETAILS[/bold bright_white]
[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]

[bold bright_cyan]▌ Overview[/bold bright_cyan]
  🆔 [bold]Run ID:[/bold] [dim]{run.id}[/dim]
  🤖 [bold]Agent:[/bold] [bright_cyan]{run.agent_name}[/bright_cyan]
  🏢 [bold]Organization:[/bold] [bright_cyan]{run.organization_name}[/bright_cyan]
  👤 [bold]Owner:[/bold] {run.owner_username or "N/A"}
  {status_icon} [bold]Status:[/bold] [bright_{status_color}]{status_display}[/bright_{status_color}]
  📊 [bold]Results:[/bold] [bright_yellow]{results_count}[/bright_yellow]
  📅 [bold]Created:[/bold] {created}

[bold bright_green]▌ Evaluation Summary[/bold bright_green]
  ✅ [bold]Successful Jailbreaks:[/bold] [bright_green]{eval_summary["SUCCESSFUL_JAILBREAK"]}[/bright_green]
  ❌ [bold]Failed Jailbreaks:[/bold] [bright_red]{eval_summary["FAILED_JAILBREAK"]}[/bright_red]
  ⏸️  [bold]Not Evaluated:[/bold] [bright_yellow]{eval_summary["NOT_EVALUATED"]}[/bright_yellow]
  ⚠️  [bold]Errors:[/bold] [bright_red]{eval_summary["ERROR"]}[/bright_red]
"""

        # Add run configuration if available
        if hasattr(run, "run_config") and run.run_config:
            details += (
                "\n[bold bright_yellow]▌ Run Configuration[/bold bright_yellow]\n"
            )
            try:
                if isinstance(run.run_config, dict):
                    run_config_str = json.dumps(run.run_config, indent=2)
                    # Color-code for readability
                    lines = run_config_str.split("\n")
                    for line in lines:
                        if ":" in line and '"' in line:
                            key_part, value_part = line.split(":", 1)
                            details += f"[bright_yellow]{key_part}[/bright_yellow]:[bright_white]{value_part}[/bright_white]\n"
                        else:
                            details += f"{line}\n"
                else:
                    details += f"{str(run.run_config)}\n"
            except Exception:
                details += f"{str(run.run_config)}\n"

        # Add run notes if available
        if hasattr(run, "run_notes") and run.run_notes:
            details += f"\n[bold bright_magenta]▌ Notes[/bold bright_magenta]\n{run.run_notes}\n"

        # Show all results with their traces and logs
        if hasattr(run, "results") and run.results:
            details += "\n[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]\n"
            details += f"[bold bright_white]  RESULTS & TRACES ({len(run.results)})[/bold bright_white]\n"
            details += "[bold bright_white]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold bright_white]\n\n"

            for idx, result in enumerate(run.results, 1):
                # Result header
                eval_status = "N/A"
                if hasattr(result, "evaluation_status"):
                    eval_status = (
                        result.evaluation_status.value
                        if hasattr(result.evaluation_status, "value")
                        else str(result.evaluation_status)
                    )

                # Color code the result status
                if (
                    "SUCCESSFUL" in eval_status.upper()
                    and "JAILBREAK" in eval_status.upper()
                ):
                    status_color = "green"
                    status_icon = "✅"
                elif (
                    "FAILED" in eval_status.upper()
                    and "JAILBREAK" in eval_status.upper()
                ):
                    status_color = "red"
                    status_icon = "❌"
                elif "ERROR" in eval_status.upper():
                    status_color = "red"
                    status_icon = "⚠️"
                else:
                    status_color = "yellow"
                    status_icon = "ℹ️"

                details += f"\n[bold bright_cyan]▌ Result #{idx}[/bold bright_cyan]\n"
                details += f"  🆔 [bold]ID:[/bold] [dim]{result.id}[/dim]\n"
                details += f"  {status_icon} [bold]Evaluation:[/bold] [bright_{status_color}]{eval_status}[/bright_{status_color}]\n"

                if hasattr(result, "prompt_name") and result.prompt_name:
                    details += f"  📝 [bold]Prompt:[/bold] [bright_cyan]{result.prompt_name}[/bright_cyan]\n"

                if hasattr(result, "latency_ms") and result.latency_ms:
                    details += f"  ⏱️  [bold]Latency:[/bold] [bright_magenta]{result.latency_ms}ms[/bright_magenta]\n"

                if (
                    hasattr(result, "response_status_code")
                    and result.response_status_code
                ):
                    details += f"  🌐 [bold]HTTP Status:[/bold] [bright_green]{result.response_status_code}[/bright_green]\n"

                # Show evaluation notes if any
                if hasattr(result, "evaluation_notes") and result.evaluation_notes:
                    details += f"  💬 [bold]Notes:[/bold] {result.evaluation_notes}\n"

                # Show evaluation metrics if any
                if hasattr(result, "evaluation_metrics") and result.evaluation_metrics:
                    details += "  📊 [bold]Metrics:[/bold]\n"
                    try:
                        if isinstance(result.evaluation_metrics, dict):
                            for key, value in result.evaluation_metrics.items():
                                details += f"     • {key}: [bright_cyan]{value}[/bright_cyan]\n"
                        else:
                            details += f"     {str(result.evaluation_metrics)}\n"
                    except Exception:
                        details += f"     {str(result.evaluation_metrics)}\n"

                # Show request payload if available
                if hasattr(result, "request_payload") and result.request_payload:
                    details += (
                        "\n  [bold bright_cyan]📤 Request Payload:[/bold bright_cyan]\n"
                    )
                    try:
                        if isinstance(result.request_payload, dict):
                            payload_str = json.dumps(result.request_payload, indent=2)
                            lines = payload_str.split("\n")
                            for line in lines[:30]:  # Show more lines
                                if ":" in line and '"' in line:
                                    key_part, value_part = line.split(":", 1)
                                    details += f"     [yellow]{key_part}:[/yellow][bright_white]{value_part}[/bright_white]\n"
                                else:
                                    details += f"     {line}\n"
                            if len(lines) > 30:
                                details += f"     [dim]... ({len(lines) - 30} more lines)[/dim]\n"
                        else:
                            details += f"     {str(result.request_payload)[:500]}\n"
                    except Exception:
                        details += f"     {str(result.request_payload)[:500]}\n"

                # Show response body if available
                if hasattr(result, "response_body") and result.response_body:
                    details += (
                        "\n  [bold bright_green]📥 Response Body:[/bold bright_green]\n"
                    )
                    response_lines = str(result.response_body).split("\n")
                    for line in response_lines[:30]:  # Show more lines
                        if line.strip():
                            details += f"     {line}\n"
                    if len(response_lines) > 30:
                        details += f"     [dim]... ({len(response_lines) - 30} more lines)[/dim]\n"

                # Show traces for this result - organized by type
                if hasattr(result, "traces") and result.traces:
                    # Sort traces by sequence number to show chronological order
                    sorted_traces = sorted(
                        result.traces,
                        key=lambda t: t.sequence if hasattr(t, "sequence") else 0,
                    )

                    details += "\n[bold bright_magenta]▌ 🔍 EXECUTION TRACES ({} steps)[/bold bright_magenta]\n\n".format(
                        len(sorted_traces)
                    )

                    for trace in sorted_traces:
                        # Get step type with proper field name
                        step_type = "OTHER"
                        step_icon = "📋"
                        step_color = "bright_cyan"

                        if hasattr(trace, "step_type"):
                            step_val = trace.step_type
                            step_type = (
                                step_val.value
                                if hasattr(step_val, "value")
                                else str(step_val)
                            )

                            # Assign icons and colors based on step type
                            if step_type == "TOOL_CALL":
                                step_icon = "🔧"
                                step_color = "bright_green"
                            elif step_type == "TOOL_RESPONSE":
                                step_icon = "📥"
                                step_color = "bright_cyan"
                            elif step_type == "AGENT_THOUGHT":
                                step_icon = "🧠"
                                step_color = "bright_magenta"
                            elif step_type == "AGENT_RESPONSE_CHUNK":
                                step_icon = "💬"
                                step_color = "bright_white"
                            elif step_type == "MCP_STEP":
                                step_icon = "🔗"
                                step_color = "bright_yellow"
                            elif step_type == "A2A_COMM":
                                step_icon = "🤝"
                                step_color = "bright_yellow"

                        # Get sequence number
                        seq = trace.sequence if hasattr(trace, "sequence") else "?"

                        # Get timestamp
                        trace_time = ""
                        if hasattr(trace, "timestamp"):
                            try:
                                if isinstance(trace.timestamp, datetime):
                                    trace_time = trace.timestamp.strftime(
                                        "%H:%M:%S.%f"
                                    )[:-3]
                                else:
                                    dt = datetime.fromisoformat(
                                        str(trace.timestamp).replace("Z", "+00:00")
                                    )
                                    trace_time = dt.strftime("%H:%M:%S.%f")[:-3]
                            except Exception:
                                trace_time = str(trace.timestamp)[:12]

                        # Format the trace header
                        details += f"[{step_color}]╭───[/] [bold {step_color}]Step {seq}[/bold {step_color}] [{step_color}]{step_icon} {step_type}[/]\n"
                        if trace_time:
                            details += (
                                f"[{step_color}]│[/] [dim]⏰ {trace_time}[/dim]\n"
                            )

                        # Get and format content
                        if hasattr(trace, "content") and trace.content:
                            content = trace.content

                            # Try to parse JSON content for better display
                            try:
                                if isinstance(content, str):
                                    content_obj = json.loads(content)
                                elif isinstance(content, dict):
                                    content_obj = content
                                else:
                                    content_obj = None

                                if content_obj:
                                    # Show key fields based on step type
                                    if step_type == "TOOL_CALL" and isinstance(
                                        content_obj, dict
                                    ):
                                        if (
                                            "name" in content_obj
                                            or "tool" in content_obj
                                        ):
                                            tool_name = content_obj.get(
                                                "name"
                                            ) or content_obj.get("tool")
                                            details += f"[{step_color}]│[/] [bold bright_cyan]Tool:[/bold bright_cyan] [bright_white]{tool_name}[/bright_white]\n"
                                        if (
                                            "arguments" in content_obj
                                            or "input" in content_obj
                                        ):
                                            args = content_obj.get(
                                                "arguments"
                                            ) or content_obj.get("input")
                                            args_str = (
                                                json.dumps(args, indent=2)
                                                if isinstance(args, dict)
                                                else str(args)
                                            )
                                            details += f"[{step_color}]│[/] [bold]Arguments:[/bold]\n"
                                            for line in args_str.split("\n")[
                                                :20
                                            ]:  # Show more lines
                                                if ":" in line and '"' in line:
                                                    details += f"[{step_color}]│[/]   [yellow]{line}[/yellow]\n"
                                                else:
                                                    details += (
                                                        f"[{step_color}]│[/]   {line}\n"
                                                    )

                                    elif step_type == "TOOL_RESPONSE" and isinstance(
                                        content_obj, dict
                                    ):
                                        if (
                                            "result" in content_obj
                                            or "output" in content_obj
                                        ):
                                            result_data = content_obj.get(
                                                "result"
                                            ) or content_obj.get("output")
                                            result_str = (
                                                json.dumps(result_data, indent=2)
                                                if isinstance(result_data, dict)
                                                else str(result_data)
                                            )
                                            details += f"[{step_color}]│[/] [bold bright_green]Result:[/bold bright_green]\n"
                                            for line in result_str.split("\n")[:20]:
                                                if ":" in line and '"' in line:
                                                    details += f"[{step_color}]│[/]   [bright_green]{line}[/bright_green]\n"
                                                else:
                                                    details += (
                                                        f"[{step_color}]│[/]   {line}\n"
                                                    )

                                    elif step_type == "AGENT_THOUGHT":
                                        # Show thinking/reasoning
                                        thought_text = (
                                            content_obj
                                            if isinstance(content_obj, str)
                                            else str(content_obj)
                                        )
                                        details += f"[{step_color}]│[/] [bold bright_magenta]Thought:[/bold bright_magenta]\n"
                                        for line in thought_text.split("\n")[:10]:
                                            if line.strip():
                                                details += f"[{step_color}]│[/]   {line[:200]}\n"

                                    elif step_type == "AGENT_RESPONSE_CHUNK":
                                        # Show agent response
                                        response_text = (
                                            content_obj
                                            if isinstance(content_obj, str)
                                            else str(content_obj)
                                        )
                                        details += f"[{step_color}]│[/] [bold bright_white]Response:[/bold bright_white]\n"
                                        for line in response_text.split("\n")[:15]:
                                            if line.strip():
                                                details += f"[{step_color}]│[/]   {line[:200]}\n"

                                    else:
                                        # Generic JSON display
                                        content_str = json.dumps(content_obj, indent=2)
                                        details += f"[{step_color}]│[/] [bold]Content:[/bold]\n"
                                        lines = content_str.split("\n")
                                        for line in lines[:20]:
                                            if ":" in line and '"' in line:
                                                details += f"[{step_color}]│[/]   [yellow]{line}[/yellow]\n"
                                            else:
                                                details += (
                                                    f"[{step_color}]│[/]   {line}\n"
                                                )
                                        if len(lines) > 20:
                                            details += f"[{step_color}]│[/]   [dim]... ({len(lines) - 20} more lines)[/dim]\n"
                                else:
                                    # Not JSON, show as plain text
                                    content_str = str(content)
                                    for line in content_str.split("\n")[:15]:
                                        if line.strip():
                                            details += (
                                                f"[{step_color}]│[/]   {line[:200]}\n"
                                            )

                            except (json.JSONDecodeError, TypeError):
                                # Not JSON, show as plain text
                                content_str = str(content)
                                lines = content_str.split("\n")
                                details += f"[{step_color}]│[/] [bold]Content:[/bold]\n"
                                for line in lines[:15]:
                                    if line.strip():
                                        details += (
                                            f"[{step_color}]│[/]   {line[:200]}\n"
                                        )
                                if len(lines) > 15:
                                    details += f"[{step_color}]│[/]   [dim]... ({len(lines) - 15} more lines)[/dim]\n"

                        details += f"[{step_color}]╰───────────────────────────────────────────────[/]\n\n"

                details += "\n"

        # Fallback: Show logs if available but no results (legacy support)
        elif hasattr(run, "logs") and run.logs:
            logs_str = str(result.logs)
            log_lines = logs_str.split("\n")

            # Parse agent actions from logs
            actions = self._parse_agent_actions(logs_str)

            # Show Agent Actions section if any were found
            if actions:
                details += "\n[bold magenta]╔════════════════════════════════════════╗[/bold magenta]\n"
                details += "[bold magenta]║      🔧 AGENT ACTIONS ({})      ║[/bold magenta]\n".format(
                    len(actions)
                )
                details += "[bold magenta]╚════════════════════════════════════════╝[/bold magenta]\n\n"

                for idx, action in enumerate(actions, 1):
                    if action["type"] == "http_request":
                        details += f"[bold yellow]━━━ Action {idx}: HTTP Request ━━━[/bold yellow]\n"
                        details += f"  🌐 [bold cyan]{action['method']}[/bold cyan] [blue]{action['url']}[/blue]\n"
                        details += f"  [dim]Line: {action['line_num']}[/dim]\n\n"

                    elif action["type"] == "tool_call":
                        details += f"[bold green]━━━ Action {idx}: Tool Call ━━━[/bold green]\n"
                        details += (
                            f"  🔧 [bold cyan]{action['tool_name']}[/bold cyan]\n"
                        )
                        if action.get("arguments"):
                            details += f"  [yellow]{action['arguments']}[/yellow]\n"
                        details += f"  [dim]Line: {action['line_num']}[/dim]\n\n"

                    elif action["type"] == "adk_tool_call":
                        details += f"[bold blue]━━━ Action {idx}: ADK Tool Call ━━━[/bold blue]\n"
                        details += f"  🤖 [cyan]{action['content']}[/cyan]\n"
                        details += f"  [dim]Line: {action['line_num']}[/dim]\n\n"

                    elif action["type"] == "adk_tool_result":
                        details += f"[bold blue]━━━ Action {idx}: ADK Tool Result ━━━[/bold blue]\n"
                        details += f"  📤 [green]{action['content']}[/green]\n"
                        details += f"  [dim]Line: {action['line_num']}[/dim]\n\n"

                    elif action["type"] == "llm_query":
                        details += f"[bold magenta]━━━ Action {idx}: LLM Query ━━━[/bold magenta]\n"
                        details += f"  🧠 [cyan]Model: {action['model']}[/cyan]\n"
                        details += f"  [dim]Line: {action['line_num']}[/dim]\n\n"

            # Show Full Execution Logs
            details += (
                "\n[bold cyan]╔════════════════════════════════════════╗[/bold cyan]\n"
            )
            details += "[bold cyan]║      📝 FULL EXECUTION LOGS      ║[/bold cyan]\n"
            details += (
                "[bold cyan]╚════════════════════════════════════════╝[/bold cyan]\n\n"
            )

            # SHOW ALL LOGS - user can scroll
            display_lines = log_lines
            if status_display.upper() == "RUNNING":
                details += "[bold yellow]⚡ LIVE LOGS[/bold yellow] [dim](Auto-refreshing every 5s)[/dim]\n\n"
            else:
                details += f"[dim]Total: {len(log_lines)} lines | Actions detected: {len(actions)}[/dim]\n\n"

            # Process and display log lines with enhanced formatting
            for line_num, line in enumerate(display_lines, 1):
                line = line.strip()
                if not line:
                    continue

                # Add line numbers for context
                line_prefix = f"[dim]{line_num:4d}[/dim] "

                # Enhanced color coding with more patterns
                if "ERROR" in line.upper() or "FAIL" in line.upper() or "❌" in line:
                    details += f"{line_prefix}[bold red]❌ {line}[/bold red]\n"
                elif "CRITICAL" in line.upper():
                    details += f"{line_prefix}[bold red on white]🔥 {line}[/bold red on white]\n"
                elif "WARN" in line.upper() or "WARNING" in line.upper():
                    details += f"{line_prefix}[bold yellow]⚠️  {line}[/bold yellow]\n"
                elif (
                    "SUCCESS" in line.upper()
                    or "COMPLETE" in line.upper()
                    or "✅" in line
                ):
                    details += f"{line_prefix}[bold green]✅ {line}[/bold green]\n"
                elif "HTTP" in line.upper() or "🌐" in line:
                    details += f"{line_prefix}[bold cyan]🌐 {line}[/bold cyan]\n"
                elif "Tool" in line or "Function" in line or "🔧" in line:
                    details += f"{line_prefix}[bold green]🔧 {line}[/bold green]\n"
                elif "ADK" in line or "🤖" in line:
                    details += f"{line_prefix}[bold blue]🤖 {line}[/bold blue]\n"
                elif "LLM" in line or "model" in line.lower():
                    details += f"{line_prefix}[bold magenta]🧠 {line}[/bold magenta]\n"
                elif "INFO" in line.upper() or "START" in line.upper():
                    details += f"{line_prefix}[cyan]ℹ️  {line}[/cyan]\n"
                elif "DEBUG" in line.upper():
                    details += f"{line_prefix}[dim]🔍 {line}[/dim]\n"
                elif line.startswith(">") or line.startswith("+"):
                    details += f"{line_prefix}[green]{line}[/green]\n"
                elif line.startswith("<") or line.startswith("-"):
                    details += f"{line_prefix}[red]{line}[/red]\n"
                else:
                    details += f"{line_prefix}[dim]{line}[/dim]\n"

        # Show result data if available - SHOW ALL DATA
        if hasattr(result, "data") and result.data:
            details += "\n[bold yellow]━━━ Result Data ━━━[/bold yellow]\n"
            try:
                if isinstance(result.data, dict):
                    data_str = json.dumps(result.data, indent=2)
                    # Color-code JSON for better readability - SHOW ALL
                    lines = data_str.split("\n")
                    formatted_lines = []
                    for line in lines:  # Show ALL lines
                        if ":" in line and '"' in line:
                            # Color keys and values differently
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                key = parts[0]
                                value = parts[1]
                                formatted_lines.append(
                                    f"[bold yellow]{key}[/bold yellow]:[cyan]{value}[/cyan]"
                                )
                            else:
                                formatted_lines.append(f"[dim]{line}[/dim]")
                        elif line.strip() in ["{", "}", "[", "]", ","]:
                            formatted_lines.append(f"[dim]{line}[/dim]")
                        else:
                            formatted_lines.append(f"{line}")
                    details += "\n".join(formatted_lines) + "\n"
                else:
                    details += f"[dim]{str(result.data)}[/dim]\n"  # Show all
            except Exception:
                details += f"[dim]{str(result.data)}[/dim]\n"

        details += (
            "\n\n[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]\n"
        )
        details += "[bold]💡 Quick Tips:[/bold]\n"
        details += "  • [dim]This view auto-refreshes every 5 seconds[/dim]\n"
        details += "  • [dim]Press [cyan]F5[/cyan] to refresh manually[/dim]\n"
        details += "  • [dim]Use [cyan]📊 Export[/cyan] buttons to save results[/dim]\n"
        details += "  • [dim]Select another row to view different results[/dim]\n"

        details_widget.update(details)

    def _export_results_csv(self) -> None:
        """Export results to CSV file."""
        try:
            import csv
            from pathlib import Path

            if not self.results_data:
                self.notify("No results to export", severity="warning")
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hackagent_results_{timestamp}.csv"
            filepath = Path.cwd() / filename

            # Write CSV
            with open(filepath, "w", newline="") as csvfile:
                fieldnames = [
                    "ID",
                    "Agent",
                    "Attack Type",
                    "Status",
                    "Created",
                    "Duration",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for result in self.results_data:
                    # Get status
                    status = "Unknown"
                    if hasattr(result, "evaluation_status"):
                        status_val = result.evaluation_status
                        status = (
                            status_val.value
                            if hasattr(status_val, "value")
                            else str(status_val)
                        )

                    # Get created date
                    created = "Unknown"
                    if hasattr(result, "created_at") and result.created_at:
                        created = str(result.created_at)

                    # Calculate duration
                    duration = "N/A"
                    if hasattr(result, "run") and result.run:
                        run = result.run
                        if (
                            hasattr(run, "started_at")
                            and run.started_at
                            and hasattr(run, "completed_at")
                            and run.completed_at
                        ):
                            try:
                                if isinstance(run.started_at, datetime) and isinstance(
                                    run.completed_at, datetime
                                ):
                                    delta = run.completed_at - run.started_at
                                    duration = f"{delta.total_seconds():.1f}s"
                            except Exception:
                                pass

                    writer.writerow(
                        {
                            "ID": str(result.id),
                            "Agent": getattr(result, "agent_name", "Unknown"),
                            "Attack Type": getattr(result, "attack_type", "Unknown"),
                            "Status": status,
                            "Created": created,
                            "Duration": duration,
                        }
                    )

            self.notify(
                f"✅ Exported {len(self.results_data)} results to {filename}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"❌ Export failed: {str(e)}", severity="error")

    def _export_results_json(self) -> None:
        """Export results to JSON file."""
        try:
            from pathlib import Path

            if not self.results_data:
                self.notify("No results to export", severity="warning")
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hackagent_results_{timestamp}.json"
            filepath = Path.cwd() / filename

            # Convert results to dict
            results_list = []
            for result in self.results_data:
                result_dict = {
                    "id": str(result.id),
                    "agent_name": getattr(result, "agent_name", None),
                    "attack_type": getattr(result, "attack_type", None),
                    "created_at": str(result.created_at)
                    if hasattr(result, "created_at")
                    else None,
                }

                # Add status
                if hasattr(result, "evaluation_status"):
                    status_val = result.evaluation_status
                    result_dict["status"] = (
                        status_val.value
                        if hasattr(status_val, "value")
                        else str(status_val)
                    )

                # Add run information
                if hasattr(result, "run") and result.run:
                    result_dict["run"] = {
                        "id": str(result.run.id) if hasattr(result.run, "id") else None,
                        "status": str(result.run.status)
                        if hasattr(result.run, "status")
                        else None,
                        "started_at": str(result.run.started_at)
                        if hasattr(result.run, "started_at")
                        else None,
                        "completed_at": str(result.run.completed_at)
                        if hasattr(result.run, "completed_at")
                        else None,
                    }

                # Add config and data if available
                if hasattr(result, "attack_config"):
                    result_dict["attack_config"] = result.attack_config
                if hasattr(result, "data"):
                    result_dict["data"] = result.data
                if hasattr(result, "logs"):
                    result_dict["logs"] = str(result.logs)

                results_list.append(result_dict)

            # Write JSON
            with open(filepath, "w") as jsonfile:
                json.dump(
                    {
                        "exported_at": datetime.now().isoformat(),
                        "total_results": len(results_list),
                        "results": results_list,
                    },
                    jsonfile,
                    indent=2,
                )

            self.notify(
                f"✅ Exported {len(results_list)} results to {filename}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"❌ Export failed: {str(e)}", severity="error")
