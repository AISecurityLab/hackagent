# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dashboard History/Reports views and per-goal rendering.

Provides ``DashboardReportsMixin`` for ``DashboardPage``. It powers the
History → Reports experience: aggregating runs per target agent, filtering the
goal history (search/status/category), and rendering individual goal rows and
their expandable detail panels.

Responsibilities:
    - Build and refresh the per-agent reports summary (tests, vulnerabilities,
      risk level via ASR).
    - Filter and render the goal history list and inline goal detail.
    - Manage the runs/reports bottom panels and their open/close lifecycle.

The heavy aggregation helpers it depends on (judge metrics, run summaries) live
in ``DashboardAnalysisDataMixin``; this mixin focuses on presentation.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
from typing import Any
from uuid import UUID

from nicegui import ui

from hackagent.attacks.evaluator.metrics import (
    calculate_fleiss_kappa,
    calculate_majority_vote_asr,
    calculate_per_judge_asr,
    calculate_per_judge_strictness,
)

from ._helpers import (
    _eval_color,
    _eval_label,
    _format_latency,
    _rel_time,
    _result_bucket,
    _serialize,
    _short_date,
)


class DashboardReportsMixin:
    """Dashboard History/Reports views and per-goal rendering."""

    def _on_goal_search_change(self, value: str) -> None:
        """Handle goal search input change."""
        self._history_goal_filter_search = (value or "").strip()
        self._render_filtered_history_goals()

    def _on_goal_status_change(self, value: str) -> None:
        """Handle goal status filter change."""
        self._history_goal_filter = value or ""
        self._render_filtered_history_goals()

    def _on_goal_category_change(self, value: str) -> None:
        """Handle goal category filter change."""
        self._history_goal_filter_category = value or ""
        self._render_filtered_history_goals()

    def _render_filtered_history_goals(self) -> None:
        """Re-render the goal list applying status, category, and search filters."""
        if self.history_results_list_area is None:
            return
        rows = self._history_goal_rows
        # Apply status filter
        if self._history_goal_filter:
            rows = [r for r in rows if r.get("_bucket") == self._history_goal_filter]
        # Apply category filter
        if self._history_goal_filter_category:
            rows = [
                r
                for r in rows
                if (r.get("_goal_category") or "") == self._history_goal_filter_category
            ]
        # Apply search filter
        if self._history_goal_filter_search:
            q = self._history_goal_filter_search.lower()
            rows = [
                r
                for r in rows
                if q in (r.get("goal") or "").lower()
                or q in (r.get("_goal_category") or "").lower()
                or q in (r.get("_goal_subcategory") or "").lower()
            ]

        self.history_results_list_area.clear()
        if not rows:
            with self.history_results_list_area:
                ui.label("No matching goals").classes(
                    "text-sm text-grey-5 italic py-4 w-full text-center"
                )
            return

        attack_type_str = self._history_dialog_attack_str
        detail_data = self._history_goal_detail_data

        with self.history_results_list_area:
            # Group by category
            cat_groups: dict[str, list[dict]] = {}
            for row in rows:
                cat = row.get("_goal_category") or "Uncategorised"
                cat_groups.setdefault(str(cat), []).append(row)

            for cat_label in sorted(cat_groups.keys()):
                rows_in_cat = cat_groups[cat_label]
                with ui.row().classes("items-center gap-2 mt-3 mb-1 px-1"):
                    ui.label(cat_label).classes(
                        "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                    )

                # Group by subcategory
                subcat_groups: dict[str, list[dict]] = {}
                for row in rows_in_cat:
                    sub = str(row.get("_goal_subcategory") or "")
                    if sub == "N/A":
                        sub = ""
                    subcat_groups.setdefault(sub, []).append(row)

                for sub_label in sorted(subcat_groups.keys()):
                    rows_in_sub = sorted(
                        subcat_groups[sub_label],
                        key=lambda r: str(r.get("goal") or "").lower(),
                    )
                    if sub_label:
                        with ui.row().classes("items-center gap-2 mt-2 mb-0.5 px-3"):
                            ui.label(sub_label).classes(
                                "text-[10px] font-semibold text-grey-5 "
                                "uppercase tracking-wide"
                            )

                    for _row in rows_in_sub:
                        _rid = str(_row.get("id") or "")
                        _data = detail_data.get(_rid)

                        def _make_click(
                            _r: dict = _row,
                            _d: object = _data,
                            _atk_str: str = attack_type_str,
                        ) -> None:
                            if self.history_detail_area is None:
                                return
                            self.history_detail_area.clear()
                            with self.history_detail_area:
                                self._render_history_goal_detail(_r, _d, _atk_str)

                        self._render_compact_card(_row, _make_click)

    def _render_history_goal_detail(
        self, row: dict, data: object, attack_type_str: str
    ) -> None:
        """Render a single goal detail in the right panel."""
        ha = attack_type_str.lower()
        if ha in ("static_template", "statictemplate"):
            self._render_static_template_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        elif ha == "bon":
            self._render_bon_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        elif ha == "pap":
            self._render_pap_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        elif ha == "pair":
            self._render_pair_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        elif ha == "tap":
            _nodes, _ds = data  # type: ignore[misc]
            self._render_tap_goal_card(row, _nodes, _ds, detail_mode=True)
        elif ha == "advprefix":
            _pr, _gs = data  # type: ignore[misc]
            self._render_advprefix_goal_card(row, _pr, _gs, detail_mode=True)
        elif ha == "autodanturbo":
            self._render_autodan_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        elif ha == "mml":
            self._render_mml_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        elif ha in ("fc", "tfc"):
            if ha == "fc":
                self._render_fc_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
            else:
                self._render_tfc_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
        else:
            _req, _resp, _gr_evt = data  # type: ignore[misc]
            self._render_generic_goal_card(
                row, _req, _resp, detail_mode=True, guardrail_event=_gr_evt
            )

    def _close_reports_detail(self) -> None:
        """Close the right detail panel and restore full-width report list."""
        self._reports_detail_visible = False
        if self._reports_detail_panel is not None:
            self._reports_detail_panel.style(
                "width: 0; min-width: 0; overflow: hidden; height: 100%;"
            )
        if self._reports_left_col is not None:
            self._reports_left_col.classes(remove="w-1/2", add="w-full")
        self._report_results_left_col = None
        self._report_goal_detail_panel = None
        self._report_current_run = None
        self._report_current_run_results = []

    def _open_runs_bottom_panel(self) -> None:
        """Show the inline bottom panel for run details.

        The panel is reparented to the currently active view so the run detail
        opens in place — both from the History view and from the Home
        "Recent Runs" panel — without navigating away.
        """
        if self._compare_bottom_panel is not None:
            self._compare_bottom_panel.classes(add="hidden")
        if self._runs_bottom_panel is not None:
            target_view = self.current_view.get("value", "dashboard")
            target_panel = self.all_panels.get(target_view) or self.all_panels.get(
                "runs"
            )
            if target_panel is not None:
                with contextlib.suppress(Exception):
                    self._runs_bottom_panel.move(target_panel)
            self._runs_bottom_panel.classes(remove="hidden")

    def _close_runs_bottom_panel(self) -> None:
        """Hide the inline bottom panel."""
        if self._runs_bottom_panel is not None:
            self._runs_bottom_panel.classes(add="hidden")

    def _close_report_goal_detail(self) -> None:
        """Close report goal detail panel inside the run report view."""
        if self._report_goal_detail_panel is not None:
            self._report_goal_detail_panel.style(
                "width: 0; min-width: 0; overflow: hidden; height: 100%;"
            )
        if self._report_results_left_col is not None:
            self._report_results_left_col.classes(remove="w-1/2", add="w-full")

    async def _open_report_goal_detail(self, row: dict) -> None:
        """Show Result / Traces / Config tabs for a report goal in side panel."""
        if self._report_goal_detail_panel is None:
            return

        if self._report_results_left_col is not None:
            self._report_results_left_col.classes(remove="w-full", add="w-1/2")
        self._report_goal_detail_panel.style(
            "width: 50%; min-width: 50%; height: 100%; overflow: hidden;"
        )

        self._report_goal_detail_panel.clear()
        with self._report_goal_detail_panel:
            with ui.scroll_area().classes("w-full h-full"):
                with ui.column().classes("w-full h-full gap-0"):
                    result_num = row.get("goal_number") or (
                        (row.get("goal_index", 0) or 0) + 1
                    )
                    with ui.row().classes(
                        "items-center justify-between w-full px-4 py-2 border-b shrink-0"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            eval_status = row.get("evaluation_status", "")
                            eval_notes = row.get("evaluation_notes")
                            bucket = _result_bucket(eval_status, eval_notes)
                            if bucket == "jailbreak":
                                ui.badge("Jailbreak", color="negative").classes(
                                    "text-xs"
                                )
                            elif bucket == "mitigated":
                                ui.badge("Mitigated", color="positive").classes(
                                    "text-xs"
                                )
                            elif bucket == "failed":
                                ui.badge("Error", color="warning").classes("text-xs")
                            else:
                                ui.badge("Pending", color="grey-6").classes("text-xs")

                            goal_text = str(row.get("goal") or "—")
                            if len(goal_text) > 80:
                                goal_text = goal_text[:80] + "…"
                            ui.label(
                                f"Result {result_num} of {len(self._report_current_run_results)}"
                            ).classes("font-semibold text-sm")
                            ui.label(goal_text).classes(
                                "text-xs text-grey-6 truncate max-w-md"
                            )

                        ui.button(
                            icon="close", on_click=self._close_report_goal_detail
                        ).props("flat round dense")

                    with (
                        ui.tabs()
                        .props("dense no-caps align=left")
                        .classes("w-full shrink-0") as detail_tabs
                    ):
                        ui.tab(name="result-tab", label="Result")
                        ui.tab(name="traces-tab", label="Traces")
                        ui.tab(name="config-tab", label="Config")

                    with ui.tab_panels(detail_tabs, value="result-tab").classes(
                        "w-full"
                    ):
                        with ui.tab_panel("result-tab").classes("w-full p-0"):
                            with ui.column().classes("w-full gap-4 p-4"):
                                self._render_result_tab(row)

                        with ui.tab_panel("traces-tab").classes("w-full p-0"):
                            traces_container = ui.column().classes("w-full gap-4 p-4")
                            with traces_container:
                                with ui.row().classes(
                                    "items-center gap-2 py-4 justify-center"
                                ):
                                    ui.spinner("dots")
                                    ui.label("Loading traces…").classes(
                                        "text-sm text-grey-6"
                                    )

                        with ui.tab_panel("config-tab").classes("w-full p-0"):
                            with ui.column().classes("w-full gap-4 p-4"):
                                self._render_config_tab(
                                    row, run=self._report_current_run
                                )

        _report_attack_str = str(
            (self._report_current_run or {}).get("attack_type") or "—"
        )
        if _report_attack_str == "—":
            _atk_id = str((self._report_current_run or {}).get("attack_id") or "")
            if _atk_id:
                _report_attack_str = self._attack_type_map_for_ids({_atk_id}).get(
                    _atk_id, "—"
                )
        await self._load_attack_specific_traces(
            row, traces_container, _report_attack_str
        )

    # ── History: render Result tab ───────────────────────────────────────────

    async def _load_run_goals_inline(self, run: dict, goals_area: ui.column) -> None:
        """Load and render goals as a table inside the expanded run row."""
        run_id_raw = str(run.get("id") or "")
        goals_area.clear()

        with goals_area:
            with ui.row().classes("items-center gap-2 px-6 py-2"):
                ui.spinner("dots", size="sm")
                ui.label("Loading results…").classes("text-xs text-grey-6")

        try:
            run_uuid = UUID(run_id_raw)

            def _fetch():
                items = []
                page = 1
                while True:
                    rp = self.backend.list_results(
                        run_id=run_uuid, page=page, page_size=100
                    )
                    items.extend(rp.items)
                    total = int(rp.total or 0)
                    if (total > 0 and len(items) >= total) or not rp.items:
                        break
                    page += 1
                return items

            all_items = await asyncio.get_event_loop().run_in_executor(None, _fetch)

            sorted_items = sorted(
                all_items,
                key=lambda item: (
                    int(getattr(item, "goal_index", 0)),
                    getattr(item, "created_at", None),
                ),
            )

            goal_indices = [getattr(it, "goal_index", None) for it in sorted_items]
            valid_int_indices = [i for i in goal_indices if isinstance(i, int)]
            use_goal_index = len(valid_int_indices) == len(sorted_items) and len(
                set(valid_int_indices)
            ) == len(sorted_items)

            run_eval_summary = self._extract_run_evaluation_summary(run)
            summary_judge_count = int(run_eval_summary.get("judge_count") or 0)
            summary_is_multi = bool(run_eval_summary.get("is_multi_judge")) or (
                summary_judge_count > 1
            )

            computed_run_vote_columns: set[str] = set()
            for item in sorted_items:
                computed_run_vote_columns.update(
                    self._extract_eval_votes_from_result(_serialize(item)).keys()
                )

            run_judge_count = len(computed_run_vote_columns)
            is_multi_judge_run = (
                run_judge_count > 1 if run_judge_count > 0 else summary_is_multi
            )

            # Build judge metadata once per run so right-side detail cards can
            # render the same ID/name/type shown in multi-judge tables.
            run_judge_meta: dict[str, dict[str, Any]] = {}
            _run_atk_id = str(run.get("attack_id") or run.get("attack") or "")
            _run_atk_cfg = {}
            if _run_atk_id:
                _run_atk_cfg = self._attack_config_map_for_ids({_run_atk_id}).get(
                    _run_atk_id, {}
                )
            _run_judges_cfg = (
                _run_atk_cfg.get("judges") or []
                if isinstance(_run_atk_cfg, dict)
                else []
            )
            run_judge_meta, _ = self._build_judge_metadata(_run_judges_cfg)

            new_rows = []
            for idx, r in enumerate(sorted_items, start=1):
                d = _serialize(r)
                d["_rel"] = _rel_time(d.get("created_at"))
                goal_index = d.get("goal_index")
                if use_goal_index and isinstance(goal_index, int):
                    d["goal_number"] = int(goal_index) + 1
                else:
                    d["goal_number"] = idx
                d["_goal_category"] = self._extract_goal_classifier_label(d, "category")
                d["_goal_subcategory"] = self._extract_goal_classifier_label(
                    d, "subcategory"
                )

                d["_is_multi_judge"] = False
                d["_goal_multi_metrics"] = {}

                if is_multi_judge_run:
                    goal_multi_metrics = self._compute_goal_multi_judge_metrics(d)
                    if not goal_multi_metrics:
                        # Fallback: derive from evaluation_summary per_goal_metrics
                        _pgm = run_eval_summary.get("per_goal_metrics")
                        if isinstance(_pgm, dict):
                            _goal_text = str(d.get("goal") or "")
                            _goal_pgm = _pgm.get(_goal_text)
                            if isinstance(_goal_pgm, dict):
                                _pja = _goal_pgm.get("per_judge_asr")
                                if isinstance(_pja, dict) and _pja:
                                    # Convert ASR values (1.0/0.0 per single goal)
                                    # to binary votes
                                    _votes = {
                                        k: int(float(v) >= 0.5) for k, v in _pja.items()
                                    }
                                    _javg = (
                                        sum(_votes.values()) / len(_votes)
                                        if _votes
                                        else None
                                    )
                                    goal_multi_metrics = {
                                        "judge_count": len(_votes),
                                        "judge_votes": dict(sorted(_votes.items())),
                                        "judge_avg": _javg,
                                        "majority_vote_asr": _javg,
                                    }
                    if goal_multi_metrics:
                        if run_judge_meta:
                            goal_multi_metrics["judge_meta"] = run_judge_meta
                        d["_is_multi_judge"] = True
                        d["_goal_multi_metrics"] = goal_multi_metrics
                        majority_vote_asr = self._safe_float(
                            goal_multi_metrics.get("majority_vote_asr")
                        )
                        if majority_vote_asr is None:
                            majority_vote_asr = self._safe_float(
                                goal_multi_metrics.get("judge_avg")
                            )
                        majority_is_jailbreak = bool(
                            majority_vote_asr is not None and majority_vote_asr >= 0.5
                        )
                        d["majority_vote"] = 1 if majority_is_jailbreak else 0
                        d["success"] = majority_is_jailbreak
                        d["evaluation_status"] = (
                            "SUCCESSFUL_JAILBREAK"
                            if majority_is_jailbreak
                            else "FAILED_JAILBREAK"
                        )

                d["evaluation_label"] = _eval_label(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["evaluation_notes"] = d.get("evaluation_notes") or "—"
                d["_goal_latency_s"] = self._extract_goal_latency_seconds(d)
                d["_goal_latency"] = _format_latency(d.get("_goal_latency_s"))
                new_rows.append(d)

            result_ids: list[UUID] = []
            for row in new_rows:
                with contextlib.suppress(Exception):
                    result_ids.append(UUID(str(row.get("id") or "")))

            def _fetch_trace_counts(ids: list[UUID]) -> dict[str, int]:
                out: dict[str, int] = {}
                for rid in ids:
                    try:
                        traces = self.backend.list_traces(result_id=rid)
                        out[str(rid)] = len(traces or [])
                    except Exception:
                        out[str(rid)] = 0
                return out

            trace_count_map = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _fetch_trace_counts(result_ids),
            )
            for row in new_rows:
                row["_goal_traces_count"] = int(
                    trace_count_map.get(str(row.get("id") or ""), 0)
                )

            self._history_current_run_results = new_rows

            goals_area.clear()
            with goals_area:
                # Summary bar
                total = len(new_rows)
                jailbreak_count = sum(
                    1
                    for r in new_rows
                    if _result_bucket(
                        r.get("evaluation_status", ""), r.get("evaluation_notes")
                    )
                    == "jailbreak"
                )
                trace_total = sum(
                    int(r.get("_goal_traces_count") or 0) for r in new_rows
                )
                with ui.row().classes(
                    "items-center gap-3 px-6 py-2 bg-grey-1 dark:bg-grey-9 border-b"
                ):
                    ui.label(f"{total} results").classes("text-xs text-grey-6")
                    ui.label(f"{trace_total} traces").classes("text-xs text-grey-6")
                    if jailbreak_count > 0:
                        ui.badge(
                            f"{jailbreak_count} jailbreaks", color="negative"
                        ).classes("text-xs")

                    if is_multi_judge_run:
                        majority_asr = self._safe_float(
                            run_eval_summary.get("majority_vote_asr")
                        )
                        if majority_asr is None:
                            majority_asr = self._safe_float(
                                run_eval_summary.get("overall_majority_vote_asr")
                            )
                        if majority_asr is None:
                            run_vote_rows = []
                            for row in new_rows:
                                votes = self._extract_eval_votes_from_result(row)
                                if votes:
                                    run_vote_rows.append(dict(votes))
                            if run_vote_rows:
                                majority_asr = calculate_majority_vote_asr(
                                    run_vote_rows
                                )
                        fleiss_kappa = self._safe_float(
                            run_eval_summary.get("fleiss_kappa")
                        )
                        if fleiss_kappa is None:
                            fleiss_kappa = self._safe_float(
                                run_eval_summary.get("overall_fleiss_kappa")
                            )
                        if fleiss_kappa is None:
                            run_vote_rows = []
                            for row in new_rows:
                                votes = self._extract_eval_votes_from_result(row)
                                if votes:
                                    run_vote_rows.append(dict(votes))
                            if run_vote_rows:
                                fleiss_kappa = calculate_fleiss_kappa(run_vote_rows)

                        if majority_asr is not None:
                            ui.badge(
                                f"Majority ASR: {majority_asr * 100:.1f}%",
                                color="primary",
                            ).classes("text-xs")
                        if fleiss_kappa is not None:
                            ui.badge(
                                f"Fleiss κ: {fleiss_kappa:.4f}",
                                color="indigo",
                            ).classes("text-xs")

                        per_judge_asr = run_eval_summary.get("per_judge_asr")
                        if not isinstance(per_judge_asr, dict) or not per_judge_asr:
                            run_vote_rows = []
                            for row in new_rows:
                                votes = self._extract_eval_votes_from_result(row)
                                if votes:
                                    run_vote_rows.append(dict(votes))
                            if run_vote_rows:
                                per_judge_asr = calculate_per_judge_asr(run_vote_rows)

                        if isinstance(per_judge_asr, dict):
                            for judge_key in sorted(per_judge_asr.keys()):
                                asr_value = self._safe_float(per_judge_asr[judge_key])
                                if asr_value is None:
                                    continue
                                judge_name = self._judge_key_display_name(judge_key)
                                ui.badge(
                                    f"{judge_name} ASR: {asr_value * 100:.1f}%",
                                    color="orange",
                                ).classes("text-xs")

                        strictness = run_eval_summary.get("per_judge_strictness")
                        _has_judge_strictness = isinstance(strictness, dict) and any(
                            key != "bias_gap" for key in strictness.keys()
                        )
                        if not _has_judge_strictness:
                            run_vote_rows = []
                            for row in new_rows:
                                votes = self._extract_eval_votes_from_result(row)
                                if votes:
                                    run_vote_rows.append(dict(votes))
                            strictness = (
                                calculate_per_judge_strictness(run_vote_rows)
                                if run_vote_rows
                                else {}
                            )
                        if isinstance(strictness, dict):
                            for judge_key in sorted(
                                key for key in strictness.keys() if key != "bias_gap"
                            ):
                                value = self._safe_float(strictness.get(judge_key))
                                if value is not None:
                                    judge_name = self._judge_key_display_name(judge_key)
                                    ui.badge(
                                        f"{judge_name} strictness: {value:.4f}",
                                        color="teal",
                                    ).classes("text-xs")
                            bias_gap = self._safe_float(strictness.get("bias_gap"))
                            if bias_gap is not None:
                                ui.badge(
                                    f"Bias gap: {bias_gap:.4f}",
                                    color="purple",
                                ).classes("text-xs")

                # Goal cards (same visual language as report page)
                for row in new_rows:
                    self._render_goal_row(row)

        except Exception as exc:
            goals_area.clear()
            with goals_area:
                ui.label(f"Error loading results: {exc}").classes(
                    "text-xs text-negative px-6 py-2"
                )

    def _render_goal_row(self, row: dict) -> None:
        """Render a single goal card inside the expanded run."""
        eval_status = row.get("evaluation_status", "")
        eval_notes = row.get("evaluation_notes")
        bucket = _result_bucket(eval_status, eval_notes)
        eval_color = _eval_color(eval_status, eval_notes)
        eval_label_text = _eval_label(eval_status, eval_notes)
        goal_num = row.get("goal_number", "—")

        border_color = (
            "border-red-400"
            if bucket == "jailbreak"
            else "border-green-400"
            if bucket == "mitigated"
            else "border-orange-400"
            if bucket == "failed"
            else "border-grey-300"
        )

        with ui.card().tight().classes(f"w-full border-l-4 {border_color}"):
            with ui.column().classes("w-full gap-2 p-4"):
                ui.label(f"Goal #{goal_num}").classes("font-semibold text-sm")

                with ui.row().classes("items-center justify-between w-full gap-3"):
                    ui.badge(
                        self._goal_category_badge_text(row),
                        color="blue-7",
                    ).classes(
                        "text-sm px-3 py-2 font-medium max-w-full whitespace-normal break-words self-start"
                    ).style(
                        "display:inline-flex;width:fit-content;max-width:100%;overflow-wrap:anywhere;"
                    )

                    with ui.row().classes("items-center gap-3 shrink-0"):
                        ui.badge(
                            eval_label_text or "Pending", color=eval_color
                        ).classes("text-xs")
                        ui.badge(
                            f"Latency: {row.get('_goal_latency', '—')}", color="grey-7"
                        ).classes("text-xs")
                        ui.button(
                            "Details",
                            icon="open_in_new",
                            on_click=lambda r=row: ui.timer(
                                0,
                                lambda rr=r: asyncio.create_task(
                                    self._open_history_goal_detail(rr)
                                ),
                                once=True,
                            ),
                        ).props("flat dense no-caps color=primary")

                ui.label(str(row.get("goal") or "—")).classes(
                    "text-sm whitespace-pre-wrap break-words leading-snug"
                ).style("overflow-wrap:anywhere;")

                if row.get("_is_multi_judge"):
                    goal_metrics = (
                        row.get("_goal_multi_metrics")
                        if isinstance(row.get("_goal_multi_metrics"), dict)
                        else {}
                    )
                    if goal_metrics:
                        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                            judge_votes = goal_metrics.get("judge_votes")
                            if isinstance(judge_votes, dict) and judge_votes:
                                for judge_key in sorted(judge_votes.keys()):
                                    vote = self._coerce_binary_vote(
                                        judge_votes.get(judge_key)
                                    )
                                    judge_name = self._judge_key_display_name(judge_key)
                                    if vote > 0:
                                        ui.badge(
                                            f"{judge_name}: JAILBREAK",
                                            color="red-4",
                                        ).classes("text-xs text-black")
                                    else:
                                        ui.badge(
                                            f"{judge_name}: MITIGATED",
                                            color="green-4",
                                        ).classes("text-xs text-black")

                            judge_avg = self._safe_float(goal_metrics.get("judge_avg"))
                            if judge_avg is not None:
                                ui.badge(
                                    f"Average: {judge_avg:.3f}",
                                    color="blue-4",
                                ).classes("text-xs text-black")

                notes_display = (
                    f"{eval_label_text}: {row.get('total_results', 1)} results, "
                    f"best score {row.get('evaluation_metrics', {}).get('best_score', '0.00') if isinstance(row.get('evaluation_metrics'), dict) else '0.00'}"
                )
                ui.label(notes_display).classes(
                    "text-xs text-grey-6 whitespace-pre-wrap break-words"
                ).style("overflow-wrap:anywhere;")

    @staticmethod
    def _risk_level_from_asr(asr_percent: float) -> tuple[str, str]:
        """Map ASR percentage to a risk label + badge color."""
        if asr_percent >= 70.0:
            return "CRITICAL", "negative"
        if asr_percent >= 40.0:
            return "HIGH", "warning"
        if asr_percent >= 10.0:
            return "MEDIUM", "orange"
        return "LOW", "positive"

    async def _load_history_reports(self) -> None:
        """Populate History → Reports aggregates grouped by target agent."""
        if (
            self.history_reports_list_area is None
            or self.history_reports_count_label is None
            or not self.history_reports_summary_labels
        ):
            return

        all_runs = []
        page = 1
        page_size = 100
        while True:
            runs_page = self.backend.list_runs(page=page, page_size=page_size)
            if not runs_page.items:
                break
            all_runs.extend(runs_page.items)
            if len(all_runs) >= int(runs_page.total or 0):
                break
            page += 1

        if not all_runs:
            self.history_reports_summary_labels["reports"].set_text("0")
            self.history_reports_summary_labels["tests"].set_text("0")
            self.history_reports_summary_labels["vulns"].set_text("0")
            self.history_reports_summary_labels["risk"].set_text("0.0%")
            self.history_reports_count_label.text = "0 agents"
            self.history_reports_list_area.clear()
            with self.history_reports_list_area:
                ui.label("No reports available yet.").classes("text-sm text-grey-6")
            return

        run_agent_ids = {str(run.agent_id) for run in all_runs}
        agent_name_by_id = self._agent_name_map_for_ids(run_agent_ids)

        # Pre-fetch attack configurations for runs so we can show a
        # configuration fallback when a run has no explicit run_config.
        run_attack_ids = {str(run.attack_id) for run in all_runs}
        attack_type_by_id = (
            self._attack_type_map_for_ids(run_attack_ids) if run_attack_ids else {}
        )
        attack_config_by_id = (
            self._attack_config_map_for_ids(run_attack_ids) if run_attack_ids else {}
        )

        per_agent: dict[str, dict] = defaultdict(
            lambda: {
                "agent_id": "",
                "agent_name": "Unknown agent",
                "reports": 0,
                "tests": 0,
                "vulns": 0,
                "runs": [],
            }
        )

        total_reports = 0
        total_tests = 0
        total_vulns = 0

        total_runs_count = len(all_runs)
        for run_index, run in enumerate(all_runs):
            run_data = _serialize(run)
            summary = self._summarize_run_results(run.id)

            tests = int(summary.get("total_results", 0) or 0)
            vulns = int(summary.get("successful_jailbreaks", 0) or 0)
            asr_percent = (100.0 * vulns / tests) if tests > 0 else 0.0

            agent_id = str(run_data.get("agent_id") or "")
            attack_id = str(run_data.get("attack_id") or "")
            # Prefer agent name in run.run_config, then in the parent attack
            fallback_agent_name = None
            if isinstance(run_data.get("run_config"), dict):
                fallback_agent_name = run_data.get("run_config", {}).get("_agent_name")
            if not fallback_agent_name:
                atk_cfg = attack_config_by_id.get(attack_id)
                if isinstance(atk_cfg, dict):
                    fallback_agent_name = atk_cfg.get("_agent_name")
            agent_name = agent_name_by_id.get(
                agent_id,
                fallback_agent_name
                or (f"{agent_id[:8]}…" if agent_id else "Unknown agent"),
            )
            attack_type = attack_type_by_id.get(
                attack_id,
                f"{attack_id[:8]}…" if attack_id else "—",
            )
            run_progress = max(1, total_runs_count - run_index)

            # Persist resolved labels in row payload used by report pages.
            run_data["agent_name"] = agent_name
            run_data["attack_type"] = attack_type

            entry = per_agent[agent_id]
            entry["agent_id"] = agent_id
            entry["agent_name"] = agent_name
            entry["reports"] += 1
            entry["tests"] += tests
            entry["vulns"] += vulns
            entry["runs"].append(
                {
                    "id": str(run_data.get("id") or ""),
                    "run_progress": run_progress,
                    "attack_type": attack_type,
                    "created_at": run_data.get("created_at"),
                    "tests": tests,
                    "vulns": vulns,
                    "risk": asr_percent,
                    "status": str(
                        summary.get("status") or run_data.get("status") or "—"
                    ),
                    "row": run_data,
                }
            )

            total_reports += 1
            total_tests += tests
            total_vulns += vulns

        avg_risk = (100.0 * total_vulns / total_tests) if total_tests > 0 else 0.0
        self.history_reports_summary_labels["reports"].set_text(str(total_reports))
        self.history_reports_summary_labels["tests"].set_text(str(total_tests))
        self.history_reports_summary_labels["vulns"].set_text(str(total_vulns))
        self.history_reports_summary_labels["risk"].set_text(f"{avg_risk:.1f}%")
        self.history_reports_count_label.text = (
            f"{len(per_agent)} agent{'s' if len(per_agent) != 1 else ''}"
        )

        grouped_agents = sorted(
            per_agent.values(),
            key=lambda item: (item["vulns"], item["tests"], item["reports"]),
            reverse=True,
        )

        self.history_reports_list_area.clear()
        with self.history_reports_list_area:
            for agent in grouped_agents:
                agent_tests = int(agent["tests"])
                agent_vulns = int(agent["vulns"])
                agent_risk = (
                    (100.0 * agent_vulns / agent_tests) if agent_tests > 0 else 0.0
                )
                risk_label, risk_color = self._risk_level_from_asr(agent_risk)

                title = (
                    f"{agent['agent_name']} · {agent['reports']} reports · "
                    f"{agent_tests} tests · {agent_vulns} vulnerabilities"
                )
                with ui.expansion(title, icon="smart_toy").classes("w-full"):
                    with ui.column().classes("w-full gap-2 p-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge(risk_label, color=risk_color).classes("text-xs")
                            ui.label(f"{agent_risk:.1f}% Risk").classes(
                                "text-sm font-semibold"
                            )

                        sorted_runs = sorted(
                            agent["runs"],
                            key=lambda item: str(item.get("created_at") or ""),
                            reverse=True,
                        )

                        for run_item in sorted_runs:
                            run_progress = run_item.get("run_progress")
                            attack_type = str(run_item.get("attack_type") or "—")
                            run_tests = int(run_item.get("tests") or 0)
                            run_vulns = int(run_item.get("vulns") or 0)
                            run_risk = float(run_item.get("risk") or 0.0)
                            run_risk_label, run_risk_color = self._risk_level_from_asr(
                                run_risk
                            )

                            with ui.card().tight().classes("w-full"):
                                with ui.row().classes(
                                    "items-center justify-between w-full p-3"
                                ):
                                    with ui.column().classes("gap-0"):
                                        ui.label(f"Run #{run_progress}").classes(
                                            "font-mono text-xs"
                                        )
                                        ui.label(
                                            f"{_short_date(run_item.get('created_at'))} · {run_tests} tests · {run_vulns} vulnerabilities · {attack_type}"
                                        ).classes("text-sm text-grey-7")
                                    with ui.row().classes("items-center gap-2"):
                                        ui.badge(
                                            run_risk_label,
                                            color=run_risk_color,
                                        ).classes("text-xs")
                                        ui.label(f"{run_risk:.1f}% Risk").classes(
                                            "text-sm font-semibold"
                                        )
                                        ui.button(
                                            icon="visibility",
                                            on_click=lambda r=run_item.get("row"): (
                                                ui.timer(
                                                    0,
                                                    lambda rr=r: asyncio.create_task(
                                                        self._open_run_results(rr)
                                                    ),
                                                    once=True,
                                                )
                                            ),
                                        ).props("flat round dense")

    async def _open_history_goal_detail(self, row: dict) -> None:
        """Populate the right panel of the history dialog with attack traces."""
        if self.history_detail_area is None:
            return
        self.history_detail_area.clear()
        with self.history_detail_area:
            with ui.row().classes("items-center gap-2 py-8 justify-center w-full"):
                ui.spinner("dots")
                ui.label("Loading…").classes("text-sm text-grey-6")
        await asyncio.sleep(0)
        await self._load_attack_specific_traces(
            row, self.history_detail_area, self._history_dialog_attack_str
        )
