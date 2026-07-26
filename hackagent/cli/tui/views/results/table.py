# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Results table rendering for the results tab."""

import datetime as dt_module
from datetime import datetime

from textual.containers import Vertical
from textual.widgets import DataTable, Static

from hackagent.cli.tui.views.results.formatters import (
    _coerce_datetime,
    _escape,
    _format_local_datetime,
)


class ResultsTableMixin:
    """Run-list table rendering for
    :class:`~hackagent.cli.tui.views.results.tab.ResultsTab`."""

    def _update_table(self) -> None:
        """Update the results table with current data."""
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear()

            # Clear and rebuild the run ID mapping
            self._run_id_map.clear()

            # Sort runs by timestamp (oldest first) to assign stable numbers
            def get_timestamp(run):
                # Support both API response objects (timestamp) and RunRecord (created_at)
                ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
                dt = _coerce_datetime(ts)
                if dt is not None:
                    return dt
                return datetime.min.replace(tzinfo=dt_module.timezone.utc)

            # Newest first; #1 is the most recent run by request.
            sorted_runs = sorted(self.results_data, key=get_timestamp, reverse=True)
            numbered_runs = list(enumerate(sorted_runs, start=1))

            for idx, run in numbered_runs:
                # Get status with color coding from Run.status
                status_display = "Unknown"
                if hasattr(run, "status"):
                    status_val = run.status
                    if hasattr(status_val, "value"):
                        status_display = status_val.value
                    else:
                        status_display = str(status_val)

                    # Color code based on status - show only emoji
                    status_upper = status_display.upper()
                    if status_upper == "COMPLETED":
                        status_display = "[green]✅[/green]"
                    elif status_upper == "RUNNING":
                        status_display = "[cyan]🔄[/cyan]"
                    elif status_upper == "FAILED":
                        status_display = "[red]❌[/red]"
                    elif status_upper == "PENDING":
                        status_display = "[yellow]⏳[/yellow]"
                    else:
                        status_display = "[dim]❓[/dim]"

                # Get agent name — prefer explicit name, otherwise resolve agent_id
                if hasattr(run, "agent_name") and run.agent_name:
                    agent_name = run.agent_name
                elif hasattr(run, "agent_id"):
                    agent_name = self._agent_map.get(
                        str(run.agent_id), str(run.agent_id)[:8] + "..."
                    )
                else:
                    agent_name = "Unknown"
                if len(agent_name) > 20:
                    agent_name = agent_name[:17] + "..."

                # Resolve attack name/type
                attack_name = "Unknown"
                run_cfg = getattr(run, "run_config", None)
                if isinstance(run_cfg, dict):
                    attack_name = str(
                        run_cfg.get("attack_type") or run_cfg.get("type") or attack_name
                    )

                attack_ref = getattr(run, "attack", None) or getattr(
                    run, "attack_id", None
                )
                if attack_ref:
                    attack_name = self._attack_map.get(str(attack_ref), attack_name)

                if len(attack_name) > 16:
                    attack_name = attack_name[:13] + "..."

                # Get created time from timestamp/created_at
                created_time = "N/A"
                ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
                if ts:
                    created_time = _format_local_datetime(
                        ts, fmt="%m/%d %H:%M", fallback=str(ts)[:10]
                    )

                # Calculate success/failure ratio — prefer nested results, fall back to cache
                if hasattr(run, "results") and run.results:
                    total_results = len(run.results)
                    success_count = sum(
                        1
                        for r in run.results
                        if "SUCCESSFUL"
                        in str(getattr(r, "evaluation_status", "")).upper()
                        and "JAILBREAK"
                        in str(getattr(r, "evaluation_status", "")).upper()
                    )
                    fail_count = sum(
                        1
                        for r in run.results
                        if "FAILED" in str(getattr(r, "evaluation_status", "")).upper()
                        and "JAILBREAK"
                        in str(getattr(r, "evaluation_status", "")).upper()
                    )
                else:
                    success_count, fail_count, total_results = self._result_counts.get(
                        str(run.id), (0, 0, 0)
                    )

                # Format results as success/fail ratio with colors
                if total_results > 0:
                    results_display = (
                        f"[green]{success_count}[/green]/[red]{fail_count}[/red]"
                    )
                else:
                    results_display = "[dim]0/0[/dim]"

                # Get the run ID for stable row key lookup
                run_id_str = str(run.id) if hasattr(run, "id") else str(id(run))

                # Store in mapping for later lookup
                self._run_id_map[run_id_str] = run

                # Add row with columns: #, Status, Agent, Success/Fail, Created
                # Use the full run ID string as the row key for stable selection
                table.add_row(
                    str(idx),
                    status_display,
                    _escape(agent_name),
                    _escape(attack_name),
                    results_display,
                    created_time,
                    key=run_id_str,
                )

            # Calculate overall statistics — use cached counts when results are not embedded
            total_success = 0
            total_failed = 0
            total_pending = 0
            for run in self.results_data:
                if hasattr(run, "results") and run.results:
                    for result in run.results:
                        eval_status = str(getattr(result, "evaluation_status", ""))
                        if hasattr(getattr(result, "evaluation_status", None), "value"):
                            eval_status = result.evaluation_status.value
                        if (
                            "SUCCESSFUL" in eval_status.upper()
                            and "JAILBREAK" in eval_status.upper()
                        ):
                            total_success += 1
                        elif (
                            "FAILED" in eval_status.upper()
                            and "JAILBREAK" in eval_status.upper()
                        ):
                            total_failed += 1
                        else:
                            total_pending += 1
                else:
                    s, f, t = self._result_counts.get(str(run.id), (0, 0, 0))
                    total_success += s
                    total_failed += f
                    total_pending += max(0, t - s - f)

            total_results = total_success + total_failed + total_pending
            success_rate = (
                (total_success / total_results * 100) if total_results > 0 else 0
            )

            # Show enhanced summary with visual success bar
            header_widget = self.query_one("#run-header-static", Static)

            # Create visual progress bar
            bar_width = 30
            success_blocks = int(
                (total_success / total_results * bar_width) if total_results > 0 else 0
            )
            failed_blocks = int(
                (total_failed / total_results * bar_width) if total_results > 0 else 0
            )
            pending_blocks = bar_width - success_blocks - failed_blocks

            progress_bar = (
                f"[green]{'█' * success_blocks}[/green]"
                f"[red]{'█' * failed_blocks}[/red]"
                f"[yellow]{'░' * pending_blocks}[/yellow]"
            )

            header_widget.update(
                f"[bold cyan]📊 Attack Results Summary[/bold cyan]\n"
                f"[dim]{'─' * 40}[/dim]\n\n"
                f"  [bold]Runs:[/bold] [bright_white]{len(self.results_data)}[/bright_white]    "
                f"[bold]Total Results:[/bold] [bright_white]{total_results}[/bright_white]\n\n"
                f"  {progress_bar}\n"
                f"  [green]✅ {total_success}[/green] successful   "
                f"[red]❌ {total_failed}[/red] failed   "
                f"[yellow]⏳ {total_pending}[/yellow] pending\n\n"
                f"  [bold]Success Rate:[/bold] [{'green' if success_rate >= 50 else 'yellow' if success_rate >= 25 else 'red'}]{success_rate:.1f}%[/]\n\n"
                f"[dim]💡 Click a row to view detailed results[/dim]"
            )

            # Clear results container when showing table
            results_container = self.query_one("#results-container", Vertical)
            results_container.remove_children()

        except Exception as e:
            # If table update fails, show error
            header_widget = self.query_one("#run-header-static", Static)
            header_widget.update(
                f"[red]❌ Error updating table: {_escape(str(e))}[/red]"
            )
