# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Results table rendering for the results tab."""

import datetime as dt_module
from datetime import datetime

from textual.containers import Vertical
from textual.widgets import DataTable, Static

from hackagent.cli.tui.theme import (
    MITIGATED,
    NOT_EVALUATED,
    VULNERABLE,
    classify_evaluation_status,
    classify_run_status,
)
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
                # Run state icon, colour-coded from the shared vocabulary
                status_display = classify_run_status(
                    getattr(run, "status", None)
                ).render_icon()

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

                # Vulnerable/mitigated ratio — prefer nested results, fall back to cache
                if hasattr(run, "results") and run.results:
                    total_results = len(run.results)
                    outcomes = [
                        classify_evaluation_status(
                            getattr(r, "evaluation_status", None)
                        )
                        for r in run.results
                    ]
                    vulnerable_count = sum(1 for o in outcomes if o is VULNERABLE)
                    mitigated_count = sum(1 for o in outcomes if o is MITIGATED)
                else:
                    (
                        vulnerable_count,
                        mitigated_count,
                        total_results,
                    ) = self._result_counts.get(str(run.id), (0, 0, 0))

                # Format as vulnerable/mitigated ratio with matching colours
                if total_results > 0:
                    results_display = (
                        f"[{VULNERABLE.color}]{vulnerable_count}[/{VULNERABLE.color}]"
                        f"/[{MITIGATED.color}]{mitigated_count}[/{MITIGATED.color}]"
                    )
                else:
                    results_display = "[dim]0/0[/dim]"

                # Get the run ID for stable row key lookup
                run_id_str = str(run.id) if hasattr(run, "id") else str(id(run))

                # Store in mapping for later lookup
                self._run_id_map[run_id_str] = run

                # Columns: #, State, Agent, Attack, Vulnerable/Mitigated, Created
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
            total_vulnerable = 0
            total_mitigated = 0
            total_unevaluated = 0
            for run in self.results_data:
                if hasattr(run, "results") and run.results:
                    for result in run.results:
                        outcome = classify_evaluation_status(
                            getattr(result, "evaluation_status", None)
                        )
                        if outcome is VULNERABLE:
                            total_vulnerable += 1
                        elif outcome is MITIGATED:
                            total_mitigated += 1
                        else:
                            total_unevaluated += 1
                else:
                    v, m, t = self._result_counts.get(str(run.id), (0, 0, 0))
                    total_vulnerable += v
                    total_mitigated += m
                    total_unevaluated += max(0, t - v - m)

            total_results = total_vulnerable + total_mitigated + total_unevaluated
            robustness = (
                (total_mitigated / total_results * 100) if total_results > 0 else 0
            )

            # Show enhanced summary with a visual outcome bar
            header_widget = self.query_one("#run-header-static", Static)

            # Create visual outcome bar
            bar_width = 30
            vulnerable_blocks = int(
                (total_vulnerable / total_results * bar_width)
                if total_results > 0
                else 0
            )
            mitigated_blocks = int(
                (total_mitigated / total_results * bar_width)
                if total_results > 0
                else 0
            )
            unevaluated_blocks = bar_width - vulnerable_blocks - mitigated_blocks

            outcome_bar = (
                f"[{VULNERABLE.color}]{'█' * vulnerable_blocks}[/{VULNERABLE.color}]"
                f"[{MITIGATED.color}]{'█' * mitigated_blocks}[/{MITIGATED.color}]"
                f"[{NOT_EVALUATED.color}]{'░' * unevaluated_blocks}[/{NOT_EVALUATED.color}]"
            )

            header_widget.update(
                f"[bold cyan]📊 Attack Results Summary[/bold cyan]\n"
                f"[dim]{'─' * 40}[/dim]\n\n"
                f"  [bold]Runs:[/bold] [bright_white]{len(self.results_data)}[/bright_white]    "
                f"[bold]Total Results:[/bold] [bright_white]{total_results}[/bright_white]\n\n"
                f"  {outcome_bar}\n"
                f"  [{VULNERABLE.color}]{VULNERABLE.icon} {total_vulnerable}[/{VULNERABLE.color}] {VULNERABLE.label.lower()}   "
                f"[{MITIGATED.color}]{MITIGATED.icon} {total_mitigated}[/{MITIGATED.color}] {MITIGATED.label.lower()}   "
                f"[{NOT_EVALUATED.color}]{NOT_EVALUATED.icon} {total_unevaluated} not evaluated[/{NOT_EVALUATED.color}]\n\n"
                f"  [bold]Robustness:[/bold] [{'green' if robustness >= 75 else 'yellow' if robustness >= 50 else 'red'}]{robustness:.1f}%[/]\n\n"
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
