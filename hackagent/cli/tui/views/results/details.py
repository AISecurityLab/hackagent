# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Detail-panel rendering for a selected run in the results tab."""

import datetime as dt_module
from typing import Any

from dateutil import tz
from textual.containers import Vertical
from textual.widgets import Collapsible, Static

from hackagent.cli.tui.theme import (
    classify_evaluation_status,
    classify_run_status,
)
from hackagent.cli.tui.views.results.formatters import (
    _escape,
    _format_local_datetime,
    _format_result_full_details,
)
from hackagent.cli.tui.views.results.formatters.run_report import (
    build_run_report_header,
)


class ResultsDetailsMixin:
    """Right-hand detail panel rendering for
    :class:`~hackagent.cli.tui.views.results.tab.ResultsTab`."""

    def _show_result_summary(self, run: Any) -> None:
        """Render a concise run summary in the right-side header panel."""
        header_widget = self.query_one("#run-header-static", Static)

        status_display = "Unknown"
        if hasattr(run, "status"):
            status_val = run.status
            status_display = (
                status_val.value if hasattr(status_val, "value") else str(status_val)
            )

        created = "Unknown"
        ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
        if ts:
            created = _format_local_datetime(
                ts, fmt="%Y-%m-%d %H:%M:%S", fallback=str(ts)
            )

        run_cfg = getattr(run, "run_config", None)
        eval_summary = (
            run_cfg.get("evaluation_summary", {}) if isinstance(run_cfg, dict) else {}
        )
        total_attacks = int(eval_summary.get("total_attacks", 0) or 0)
        asr = float(eval_summary.get("overall_success_rate", 0.0) or 0.0) * 100.0
        mv_asr = float(eval_summary.get("majority_vote_asr", 0.0) or 0.0) * 100.0
        fleiss = eval_summary.get("fleiss_kappa")
        strictness = eval_summary.get("per_judge_strictness")
        is_multi_judge = bool(eval_summary.get("is_multi_judge"))

        summary = (
            f"[bold cyan]▌ Selected Run[/bold cyan]\n"
            f"  🆔 [dim]{str(getattr(run, 'id', ''))[:8]}...[/dim]  "
            f"📅 {_escape(created)}  "
            f"Status: [bold]{_escape(status_display)}[/bold]\n"
        )
        if eval_summary:
            summary += (
                f"\n[bold bright_green]▌ Evaluation Summary[/bold bright_green]\n"
                f"  Total: [bold]{total_attacks}[/bold]  "
                f"ASR: [bold]{asr:.1f}%[/bold]  "
                f"Majority ASR: [bold]{mv_asr:.1f}%[/bold]"
            )
            if fleiss is not None:
                try:
                    summary += f"  Fleiss κ: [bold]{float(fleiss):.3f}[/bold]"
                except (TypeError, ValueError):
                    summary += f"  Fleiss κ: [bold]{_escape(str(fleiss))}[/bold]"
            summary += "\n"

            if is_multi_judge and isinstance(strictness, dict):
                judge_keys = [k for k in strictness.keys() if k != "bias_gap"]
                if judge_keys:
                    parts = []
                    # Judge columns follow the "eval_<judge_name>" naming
                    # convention (see _is_canonical_eval_vote_column in
                    # hackagent/attacks/evaluator/metrics.py); sorted for a
                    # stable, deterministic display order.
                    for jk in sorted(judge_keys):
                        try:
                            val = float(strictness.get(jk, 0.0) or 0.0)
                            judge_name = _escape(
                                jk.replace("eval_", "").replace("_", " ")
                            )
                            parts.append(f"{judge_name}: [bold]{val:.3f}[/bold]")
                        except (TypeError, ValueError):
                            continue
                    if parts:
                        bias_gap = strictness.get("bias_gap")
                        bias_gap_str = ""
                        if bias_gap is not None:
                            try:
                                bias_gap_str = (
                                    f"  Bias gap: [bold]{float(bias_gap):.3f}[/bold]"
                                )
                            except (TypeError, ValueError):
                                pass
                        summary += (
                            f"  [dim]Strictness — {'  '.join(parts)}[/dim]"
                            f"{bias_gap_str}\n"
                        )
        else:
            summary += "\n[dim]No evaluation summary synced yet for this run.[/dim]\n"

        header_widget.update(summary)

    def _show_result_details(self) -> None:
        """Show details of the selected run and its results using collapsible widgets.

        Each result is displayed as a collapsible item that expands on click.
        """
        if not self.selected_result:
            return

        run = self.selected_result  # This is a Run object now
        header_widget = self.query_one("#run-header-static", Static)
        results_container = self.query_one("#results-container", Vertical)

        # Show loading indicator immediately for responsive UI
        header_widget.update("[cyan]⏳ Loading run details...[/cyan]")
        results_container.remove_children()

        # Fetch full run details via backend
        try:
            from uuid import UUID

            backend = self.create_backend()
            run_id = run.id if isinstance(run.id, UUID) else UUID(str(run.id))
            run = backend.get_run(run_id)
        except Exception as e:
            header_widget.update(
                f"[yellow]⚠️ Could not fetch full details: {_escape(str(e))}[/yellow]\n\n[dim]Showing cached data...[/dim]"
            )
            return

        # Format creation date from timestamp/created_at
        created = "Unknown"
        ts = getattr(run, "timestamp", None) or getattr(run, "created_at", None)
        if ts:
            created = _format_local_datetime(
                ts, fmt="%Y-%m-%d %H:%M:%S", fallback=str(ts)
            )

        # Resolve agent name
        if hasattr(run, "agent_name") and run.agent_name:
            agent_display = run.agent_name
        elif hasattr(run, "agent_id"):
            agent_display = self._agent_map.get(
                str(run.agent_id), str(run.agent_id)[:8] + "..."
            )
        else:
            agent_display = "Unknown"

        # Resolve organisation name
        org_display = getattr(run, "organization_name", None) or "Local"

        # Fetch results for this run when they are not embedded
        run_results: list[Any] = []
        if hasattr(run, "results") and run.results:
            run_results = list(run.results)
        else:
            try:
                from uuid import UUID as _UUID

                _rid = run.id if isinstance(run.id, _UUID) else _UUID(str(run.id))
                _backend = self.create_backend()
                _res_page = _backend.list_results(run_id=_rid, page=1, page_size=500)
                run_results = list(_res_page.items)
            except Exception:
                pass

        # Get status from Run
        status_display = "Unknown"
        if hasattr(run, "status"):
            status_val = run.status
            if hasattr(status_val, "value"):
                status_display = status_val.value
            else:
                status_display = str(status_val)

        # Status colour and icon from the shared run-state vocabulary
        run_state = classify_run_status(getattr(run, "status", None))
        status_color = run_state.color
        status_icon = run_state.icon

        # Attack config from attack record
        attack_config = {}
        attack_type_display = ""
        try:
            _att_id = getattr(run, "attack_id", None)
            if _att_id:
                attack_type_display = self._attack_map.get(str(_att_id), "")
                # Try to get full attack config from local backend
                _att_backend = self.create_backend()
                _att_page = _att_backend.list_attacks(page=1, page_size=500)
                for _att in _att_page.items:
                    if str(_att.id) == str(_att_id):
                        attack_config = (
                            getattr(_att, "configuration", None)
                            or getattr(_att, "config", None)
                            or {}
                        )
                        if isinstance(attack_config, str):
                            import json as _json

                            attack_config = _json.loads(attack_config)
                        if not attack_type_display:
                            attack_type_display = getattr(_att, "type", "") or ""
                        break
        except Exception:
            pass

        header = build_run_report_header(
            run,
            created=created,
            agent_display=agent_display,
            org_display=org_display,
            status_display=status_display,
            status_icon=status_icon,
            status_color=status_color,
            run_results=run_results,
            attack_type_display=attack_type_display,
            attack_config=attack_config if isinstance(attack_config, dict) else {},
        )

        # Update header widget
        header_widget.update(header)

        # Clear and rebuild results container with collapsible items
        results_container.remove_children()

        if run_results:
            # Test Results section header (matches remote dashboard)
            results_container.mount(
                Static(
                    f"\n[bold cyan]╔{'═' * 46}╗[/bold cyan]\n"
                    f"[bold cyan]║[/bold cyan] [bold]📋 Test Results[/bold] [dim]— click a row to inspect[/dim]{' ' * 8}[bold cyan]║[/bold cyan]\n"
                    f"[bold cyan]╚{'═' * 46}╝[/bold cyan]\n"
                )
            )

            # Pre-fetch traces for all results from the backend
            _backend_for_traces = self.create_backend()
            _traces_by_result: dict[str, list] = {}
            for _r in run_results:
                try:
                    from uuid import UUID as _UUID2

                    _rid2 = _r.id if isinstance(_r.id, _UUID2) else _UUID2(str(_r.id))
                    _traces_by_result[str(_r.id)] = _backend_for_traces.list_traces(
                        _rid2
                    )
                except Exception:
                    _traces_by_result[str(_r.id)] = []

            # Create collapsible for each result
            for idx, result in enumerate(run_results, 1):
                outcome = classify_evaluation_status(
                    getattr(result, "evaluation_status", None)
                )
                css_class = f"result-collapsible {outcome.css_class}"

                # Resolve traces — embedded or pre-fetched
                result_traces = _traces_by_result.get(str(result.id)) or []

                trace_count_str = (
                    f" \U0001f50d {len(result_traces)}" if result_traces else ""
                )
                title = f"Result #{idx}{trace_count_str}    {outcome.render()}"

                # Create collapsible with full details inside
                collapsible = Collapsible(
                    Static(
                        _format_result_full_details(
                            result,
                            idx,
                            self.MAX_TRACES_PER_RESULT,
                            traces=result_traces,
                        ),
                        classes="result-details",
                    ),
                    title=title,
                    collapsed=True,
                    classes=css_class,
                )
                results_container.mount(collapsible)

            # Add tips at the bottom - compact
            results_container.mount(
                Static(
                    "\n[dim]─────────────────────────────────────[/dim]\n"
                    "[dim]💡 F5=Refresh • Export: CSV/JSON • Click row=select run[/dim]\n"
                )
            )

        else:
            # No results yet - show informative message
            self._show_no_results_message(run, status_display, results_container)

    def _show_no_results_message(
        self, run: Any, status_display: str, container: Vertical
    ) -> None:
        """Show appropriate message when run has no results.

        Args:
            run: The run object
            status_display: Current run status string
            container: Container to add the message to
        """
        message = "\n[bold yellow]⏳ No Results Yet[/bold yellow]\n"
        message += "[dim]─────────────────────────────────────[/dim]\n\n"

        if status_display == "PENDING":
            run_age = None
            if hasattr(run, "timestamp") and run.timestamp:
                try:
                    now = dt_module.datetime.now(tz.UTC)
                    run_timestamp = (
                        run.timestamp
                        if run.timestamp.tzinfo
                        else run.timestamp.replace(tzinfo=tz.UTC)
                    )
                    run_age = (now - run_timestamp).total_seconds() / 60
                except Exception:
                    pass

            if run_age and run_age > 5:
                message += "[bold yellow]⚠️  Stale Run Detected[/bold yellow]\n\n"
                message += f"[dim]This run was created {int(run_age)} minutes ago but has no results.[/dim]\n"
                message += "[dim]This typically means:[/dim]\n"
                message += (
                    "[dim]  • [bold]The client was interrupted or killed[/bold][/dim]\n"
                )
                message += "[dim]  • The attack process crashed before creating results[/dim]\n"
                message += "[dim]  • The run was never properly started[/dim]\n\n"
                message += "[bold red]⚡ Action Needed:[/bold red]\n"
                message += "[yellow]This run should be marked as FAILED or CANCELLED.[/yellow]\n"
                message += (
                    f"[dim]  hackagent run update {run.id} --status FAILED[/dim]\n"
                )
            else:
                message += "[bold yellow]⏳ This run is pending[/bold yellow]\n\n"
                message += "[dim]The attack has been initiated but results are not yet available.[/dim]\n"
                message += "[dim]Results will appear here once agent interactions complete.[/dim]\n"

        elif status_display == "RUNNING":
            message += "[bold cyan]🔄 Run is active[/bold cyan]\n\n"
            message += "[dim]Results will be added as the attack progresses...[/dim]\n"

        elif status_display == "COMPLETED":
            message += "[bold yellow]⚠️  Run completed with no results[/bold yellow]\n\n"
            message += "[dim]This might happen if:[/dim]\n"
            message += "[dim]  • The attack configuration didn't generate any test cases[/dim]\n"
            message += (
                "[dim]  • Agent calls failed before results could be created[/dim]\n"
            )

        elif status_display == "FAILED":
            message += "[bold red]❌ Run failed[/bold red]\n\n"
            message += "[dim]The run encountered errors before results could be created.[/dim]\n"

        else:
            message += (
                f"[bold yellow]Status: {_escape(status_display)}[/bold yellow]\n\n"
            )
            message += "[dim]No results have been recorded for this run yet.[/dim]\n"

        container.mount(Static(message))
