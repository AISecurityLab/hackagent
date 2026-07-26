# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Results Tab

View and analyze attack results.

Rendering helpers live in ``formatters/``; the heavier panels are split into
mixins (``table.py``, ``details.py``, ``export.py``) that this router composes.
"""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Label, Select, Static

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.base import BaseTab
from hackagent.cli.tui.views.results.details import ResultsDetailsMixin
from hackagent.cli.tui.views.results.export import ResultsExportMixin
from hackagent.cli.tui.views.results.formatters import _escape
from hackagent.cli.tui.views.results.table import ResultsTableMixin


class ResultsTab(
    ResultsTableMixin,
    ResultsDetailsMixin,
    ResultsExportMixin,
    BaseTab,
):
    """Results tab for viewing attack results with split view."""

    DEFAULT_CSS = """
    ResultsTab {
        layout: horizontal;
    }
    
    ResultsTab #results-left-panel {
        width: 35%;
        border-right: solid $primary;
    }
    
    ResultsTab #results-right-panel {
        width: 65%;
    }
    
    ResultsTab #results-table {
        height: 100%;
    }
    
    ResultsTab #run-header-static {
        margin-bottom: 1;
        padding: 0 1;
    }
    
    ResultsTab #results-container {
        height: auto;
        padding: 0 1;
    }
    
    ResultsTab .result-collapsible {
        margin: 0 0 1 0;
        padding: 0;
    }
    
    ResultsTab .result-collapsible > CollapsibleTitle {
        padding: 1 2;
        background: $surface;
    }
    
    ResultsTab .result-collapsible.-success > CollapsibleTitle {
        background: $success-darken-3;
        color: $text;
    }
    
    ResultsTab .result-collapsible.-failed > CollapsibleTitle {
        background: $error-darken-3;
        color: $text;
    }
    
    ResultsTab .result-collapsible.-pending > CollapsibleTitle {
        background: $warning-darken-3;
        color: $text;
    }
    
    ResultsTab .result-details {
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface-darken-1;
    }
    
    ResultsTab .stats-bar {
        height: 3;
        margin: 1 0;
        padding: 0 1;
    }
    
    ResultsTab .success-bar {
        background: $success;
        height: 1;
    }
    
    ResultsTab .failed-bar {
        background: $error;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "view_result", "View Details"),
        Binding("s", "show_summary", "Summary"),
        Binding("c", "toggle_compare", "Compare Runs"),
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("pageup", "prev_page", "Previous Page", show=False),
        Binding("pagedown", "next_page", "Next Page", show=False),
        Binding("[", "prev_page", "Previous Page"),
        Binding("]", "next_page", "Next Page"),
    ]

    # Maximum number of results to display in detail view to prevent UI freeze
    MAX_RESULTS_DISPLAY = 10
    # Maximum number of traces per result to display
    MAX_TRACES_PER_RESULT = 5
    # Maximum content length for truncation
    MAX_CONTENT_LENGTH = 500

    def __init__(self, cli_config: CLIConfig):
        """Initialize results tab.

        Args:
            cli_config: CLI configuration object
        """
        super().__init__(cli_config)
        self.results_data: list[Any] = []
        self.selected_result: Any = None
        self._detail_page: int = 0  # Current page for result details pagination
        self._run_id_map: dict[str, Any] = {}  # Map run ID strings to run objects
        self._compare_runs: list[Any] = []  # Runs selected for comparison
        self._show_dashboard: bool = False  # Toggle dashboard view
        self._total_count: int = (
            0  # Total number of runs from API (for correct numbering)
        )
        # Enrichment caches (populated in refresh_data)
        self._agent_map: dict[str, str] = {}  # agent_id str -> agent name
        self._attack_map: dict[str, str] = {}  # attack_id str -> attack type
        self._result_counts: dict[
            str, tuple
        ] = {}  # run_id str -> (success, fail, total)

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
                yield Button("⚖️ Compare", id="compare-btn", variant="warning")
                yield Button("📈 Dashboard", id="dashboard-btn", variant="success")

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
            # Run header info (shows run overview when selected)
            yield Static(
                "[dim]💡 Select a run from the list to view details and results[/dim]",
                id="run-header-static",
            )
            # Container for collapsible result items
            yield Vertical(id="results-container")

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Initialize table columns with improved headers
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            table.add_columns("#", "⚡", "Agent", "Attack", "✅/❌", "Created")
        except Exception as e:
            self.app.notify(f"Failed to initialize table: {str(e)}", severity="error")

        # Show loading message immediately
        try:
            header_widget = self.query_one("#run-header-static", Static)
            header_widget.update("[cyan]Loading results from API...[/cyan]")
        except Exception:
            pass

        # Do not fetch on mount; BaseTab.on_show will lazily trigger first refresh.
        # This prevents hidden tab network calls from delaying TUI startup.

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
        row_key = event.row_key
        # The row key is the run ID string - use it to look up the run
        run_id_str = str(row_key.value) if hasattr(row_key, "value") else str(row_key)

        if run_id_str in self._run_id_map:
            self.selected_result = self._run_id_map[run_id_str]
            self._detail_page = 0  # Reset page when selecting new result
            # Show summary in right panel
            self._show_result_summary(self.selected_result)
            self._show_result_details()

    def action_show_summary(self) -> None:
        """Show a quick summary for the selected run."""
        if self.selected_result:
            self._show_result_summary(self.selected_result)

    def action_next_page(self) -> None:
        """Navigate to next page of results details."""
        if not self.selected_result:
            return
        run = self.selected_result
        if hasattr(run, "results") and run.results:
            total_results = len(run.results)
            total_pages = (
                total_results + self.MAX_RESULTS_DISPLAY - 1
            ) // self.MAX_RESULTS_DISPLAY
            if self._detail_page < total_pages - 1:
                self._detail_page += 1
                self._show_result_details()

    def action_prev_page(self) -> None:
        """Navigate to previous page of results details."""
        if self._detail_page > 0:
            self._detail_page -= 1
            self._show_result_details()

    def refresh_data(self) -> None:
        """Refresh results data from API."""
        try:
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

            backend = self.create_backend()

            # Fetch runs via backend
            runs_result = backend.list_runs(page=1, page_size=limit)
            all_runs = runs_result.items

            # Build agent name cache (RunRecord only has agent_id)
            self._agent_map.clear()
            try:
                agents_result = backend.list_agents(page=1, page_size=500)
                for ag in agents_result.items:
                    self._agent_map[str(ag.id)] = ag.name
            except Exception:
                pass

            # Build attack type cache for showing human-readable attack names
            self._attack_map.clear()
            try:
                attacks_result = backend.list_attacks(page=1, page_size=500)
                for attack in attacks_result.items:
                    self._attack_map[str(attack.id)] = str(attack.type)
            except Exception:
                pass

            # Build result-count cache for runs that don't carry nested results
            self._result_counts.clear()
            for run in all_runs:
                if not hasattr(run, "results") or run.results is None:
                    try:
                        from uuid import UUID as _UUID

                        rid = (
                            run.id if isinstance(run.id, _UUID) else _UUID(str(run.id))
                        )
                        res_page = backend.list_results(
                            run_id=rid, page=1, page_size=500
                        )
                        success = sum(
                            1
                            for r in res_page.items
                            if "SUCCESSFUL"
                            in str(getattr(r, "evaluation_status", "")).upper()
                            and "JAILBREAK"
                            in str(getattr(r, "evaluation_status", "")).upper()
                        )
                        fail = sum(
                            1
                            for r in res_page.items
                            if "FAILED"
                            in str(getattr(r, "evaluation_status", "")).upper()
                            and "JAILBREAK"
                            in str(getattr(r, "evaluation_status", "")).upper()
                        )
                        self._result_counts[str(run.id)] = (
                            success,
                            fail,
                            len(res_page.items),
                        )
                    except Exception:
                        self._result_counts[str(run.id)] = (0, 0, 0)

            # Filter by status if requested
            if status_filter and status_filter != "all":
                all_runs = [
                    r
                    for r in all_runs
                    if str(r.status).upper() == status_filter.upper()
                ]

            self.results_data = all_runs if all_runs else []
            self._total_count = len(self.results_data)

            if not self.results_data:
                self._show_empty_state(
                    "No runs found. Execute an attack to see results here."
                )
            else:
                self._update_table()

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            self._show_empty_state(f"Error loading results: {error_type}\n{error_msg}")

    def _show_empty_state(self, message: str) -> None:
        """Show an empty state message when no data is available.

        Args:
            message: Message to display
        """
        table = self.query_one("#results-table", DataTable)
        table.clear()

        # Show message in header area and clear results container
        header_widget = self.query_one("#run-header-static", Static)
        header_widget.update(
            f"[yellow]{_escape(message)}[/yellow]\n\n[dim]💡 Tip: Press F5 or click 🔄 Refresh to retry[/dim]"
        )

        # Clear results container
        results_container = self.query_one("#results-container", Vertical)
        results_container.remove_children()
