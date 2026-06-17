# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Data loading for dashboard, agents, attacks and runs.

Provides ``DashboardDataMixin`` for ``DashboardPage``. It is the bridge between
the storage backend and the widgets built by the layout mixin: it fetches data
and populates the tables/cards for each view.

Responsibilities:
    - ``refresh_view`` dispatches to the loader for the active view.
    - ``_load_dashboard`` / ``_load_agents`` / ``_load_attacks`` / ``_load_runs``
      pull records from ``self.backend`` and render them.
    - Runs filtering and pagination (search box, filter dropdowns,
      ``_fetch_all_runs``, ``_load_more_runs``).
    - The attack detail dialog and attack deletion.

It reads page-size constants from ``_constants`` and reuses aggregation helpers
from ``DashboardAnalysisDataMixin``.
"""

from __future__ import annotations

import json
import math
from uuid import UUID

from nicegui import ui


from ._constants import (
    _DASHBOARD_RUN_SCAN_LIMIT,
)
from ._helpers import (
    _format_latency,
    _rel_time,
    _result_bucket,
    _serialize,
    _short_date,
)


class DashboardDataMixin:
    """Data loading for dashboard, agents, attacks and runs."""

    def _build_attack_dialog(self) -> None:
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-4xl h-[80vh] flex flex-col gap-4"):
                with ui.row().classes("items-center justify-between w-full shrink-0"):
                    self.attack_dialog_title = ui.label("Attack Detail").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                self.attack_config_area = ui.column().classes(
                    "w-full gap-4 flex-1 overflow-auto"
                )

        self.attack_dialog = dialog

    async def _open_attack_detail(self, attack: dict) -> None:
        """Open the attack detail dialog with config and associated runs."""
        short_id = str(attack.get("id", ""))[:8]
        self.attack_dialog_title.text = (
            f"Attack {short_id}… · {attack.get('type', '—')}"
        )
        self.attack_config_area.clear()

        with self.attack_config_area:
            # ── Info cards ────────────────────────────────────────────────
            with ui.row().classes("w-full flex-wrap gap-4"):
                for lbl, val, icon_name in [
                    ("ID", attack.get("id", "—"), "fingerprint"),
                    ("Type", attack.get("type", "—"), "flash_on"),
                    ("Agent", str(attack.get("agent_id", "—"))[:12] + "…", "smart_toy"),
                    ("Created", attack.get("_rel", "—"), "schedule"),
                ]:
                    with ui.card().classes("flex-1 min-w-40"):
                        with ui.row().classes("items-center gap-2 mb-1"):
                            ui.icon(icon_name, size="xs").classes("text-grey-6")
                            ui.label(lbl).classes(
                                "text-xs text-grey-6 uppercase font-semibold"
                            )
                        ui.label(str(val)).classes(
                            "text-sm font-mono select-all break-all"
                        )

            # ── Configuration JSON ────────────────────────────────────────
            config = attack.get("configuration", {})
            if config:
                with ui.column().classes("w-full gap-1"):
                    ui.label("CONFIGURATION").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                    )
                    ui.code(
                        json.dumps(config, indent=2, default=str),
                        language="json",
                    ).classes("w-full text-xs overflow-auto")

            # ── Associated runs ───────────────────────────────────────────
            ui.label("RUNS").classes(
                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
            )
            runs_container = ui.column().classes("w-full gap-0")
            with runs_container:
                with ui.row().classes("items-center gap-2 py-4 justify-center"):
                    ui.spinner("dots")
                    ui.label("Loading runs…").classes("text-sm text-grey-6")

        self.attack_dialog.open()

        # Load runs for this attack asynchronously
        try:
            attack_id = UUID(str(attack["id"]))
            runs_p = self.backend.list_runs(attack_id=attack_id, page=1, page_size=100)
            runs_container.clear()

            if not runs_p.items:
                with runs_container:
                    ui.label("No runs for this attack.").classes(
                        "text-sm text-grey-6 text-center py-6"
                    )
            else:
                with runs_container:
                    for run in runs_p.items:
                        d = _serialize(run)
                        summary = self._summarize_run_results(run.id)
                        d["total_results"] = int(summary["total_results"])
                        d["successful_jailbreaks"] = int(
                            summary["successful_jailbreaks"]
                        )
                        d["failed_attacks"] = int(summary["failed_attacks"])
                        d["mitigations"] = int(summary["mitigations"])
                        d["status"] = str(summary["status"])
                        status = d.get("status", "")
                        status_color = (
                            "positive"
                            if status == "COMPLETED"
                            else "info"
                            if status == "RUNNING"
                            else "negative"
                            if status == "FAILED"
                            else "warning"
                        )
                        with (
                            ui.card()
                            .classes("w-full cursor-pointer hover:shadow-md")
                            .on(
                                "click",
                                lambda _e, r=d: (
                                    self.attack_dialog.close(),
                                    ui.timer(
                                        0,
                                        lambda: self._open_run_history_results(r),
                                        once=True,
                                    ),
                                ),
                            )
                        ):
                            with ui.row().classes(
                                "items-center justify-between w-full"
                            ):
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(str(d["id"])[:8] + "…").classes(
                                        "font-mono text-xs font-medium"
                                    )
                                    ui.badge(status, color=status_color).classes(
                                        "text-xs"
                                    )
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(f"{d['total_results']} results").classes(
                                        "text-xs text-grey-6"
                                    )
                                    if d["successful_jailbreaks"] > 0:
                                        ui.badge(
                                            f"⚠ {d['successful_jailbreaks']}",
                                            color="negative",
                                        ).classes("text-xs")
                                    ui.label(_rel_time(d.get("created_at"))).classes(
                                        "text-xs text-grey-6"
                                    )
        except Exception as exc:
            runs_container.clear()
            with runs_container:
                with ui.row().classes("gap-2 items-center py-4"):
                    ui.icon("error_outline", color="negative")
                    ui.label(f"Error loading runs: {exc}").classes(
                        "text-sm text-negative"
                    )

    # ── Dark mode ─────────────────────────────────────────────────────────────

    async def _delete_selected_attacks(self) -> None:
        ids = list(self._selected_attack_ids)
        if not ids:
            return
        try:
            for aid in ids:
                self.backend.delete_attack(UUID(aid))
            ui.notify(f"Deleted {len(ids)} attack(s)", type="positive")
        except Exception as exc:
            ui.notify(f"Delete failed: {exc}", type="negative")
        self._selected_attack_ids.clear()
        if self.attacks_table is not None:
            self.attacks_table.selected.clear()
        if self._attacks_delete_btn is not None:
            self._attacks_delete_btn.classes(add="hidden")
        await self._load_attacks()

    async def refresh_view(self) -> None:
        _v = self.current_view["value"]
        self.loading_spinner.set_visibility(True)
        try:
            if _v == "dashboard":
                await self._load_dashboard()
            elif _v == "agents":
                await self._load_agents()
            elif _v == "runs":
                await self._load_runs()
        except Exception as exc:
            ui.notify(f"Failed to load data: {exc}", type="negative")
        finally:
            self.loading_spinner.set_visibility(False)

    # ── Result detail (right drawer) ──────────────────────────────────────────

    async def _load_dashboard(self) -> None:
        runs_p = self.backend.list_runs(page=1, page_size=_DASHBOARD_RUN_SCAN_LIMIT)
        global_buckets = self.backend.count_result_buckets()
        targets_count = self._count_targets_with_runs()

        latest_run = runs_p.items[0] if runs_p.items else None
        latest_target_name = "—"
        if latest_run is not None:
            latest_target_id = str(latest_run.agent_id)
            latest_target_name = self._agent_name_map_for_ids({latest_target_id}).get(
                latest_target_id,
                latest_run.run_config.get("_agent_name")
                or (f"{latest_target_id[:8]}…" if latest_target_id else "—"),
            )

        # ── Buckets scoped to latest tested target only ───────────────
        buckets = (
            self._count_result_buckets_for_agent(latest_run.agent_id)
            if latest_run is not None
            else {
                "total": 0,
                "jailbreaks": 0,
                "mitigated": 0,
                "failed": 0,
                "pending": 0,
            }
        )
        total_results = buckets["total"]
        jailbreaks = buckets["jailbreaks"]
        mitigated = buckets["mitigated"]
        failed = buckets["failed"]
        pending = buckets["pending"]

        risk_pct = (
            round(100 * jailbreaks / max(total_results, 1)) if total_results else 0
        )
        risk_color = (
            "#ef4444"
            if risk_pct >= 70
            else "#f97316"
            if risk_pct >= 40
            else "#eab308"
            if risk_pct >= 10
            else "#22c55e"
        )
        risk_level = (
            "Critical"
            if risk_pct >= 70
            else "High"
            if risk_pct >= 40
            else "Medium"
            if risk_pct >= 10
            else "Low"
            if total_results
            else "No data"
        )

        self.stat_labels["total_agents"].set_text(str(targets_count))
        self.stat_labels["total_runs"].set_text(str(runs_p.total))
        self.stat_labels["successful_jailbreaks"].set_text(
            str(global_buckets.get("jailbreaks", 0))
        )
        if self.latest_target_stats_label is not None:
            self.latest_target_stats_label.text = "Latest Target Statistics"
        if self.latest_target_agent_label is not None:
            self.latest_target_agent_label.text = (
                latest_target_name if latest_run is not None else "N/A"
            )

        # Risk donut
        no_data = total_results == 0
        self.risk_chart.options.clear()
        self.risk_chart.options.update(
            {
                "series": [
                    {
                        "type": "pie",
                        "radius": ["58%", "80%"],
                        "data": (
                            [
                                {
                                    "value": 1,
                                    "name": "No data",
                                    "itemStyle": {"color": "#94a3b8"},
                                }
                            ]
                            if no_data
                            else [
                                {
                                    "value": jailbreaks,
                                    "name": "Jailbreaks",
                                    "itemStyle": {"color": "#ef4444"},
                                },
                                {
                                    "value": mitigated,
                                    "name": "Mitigated",
                                    "itemStyle": {"color": "#22c55e"},
                                },
                                {
                                    "value": failed,
                                    "name": "Errors",
                                    "itemStyle": {"color": "#f97316"},
                                },
                                {
                                    "value": pending,
                                    "name": "Pending",
                                    "itemStyle": {"color": "#94a3b8"},
                                },
                            ]
                        ),
                        "label": {"show": False},
                        "emphasis": {"scale": False},
                    }
                ],
                "graphic": (
                    []
                    if no_data
                    else [
                        {
                            "type": "group",
                            "left": "center",
                            "top": "center",
                            "children": [
                                {
                                    "type": "text",
                                    "style": {
                                        "text": f"{risk_pct}%",
                                        "textAlign": "center",
                                        "fontSize": 22,
                                        "fontWeight": "bold",
                                        "fill": risk_color,
                                    },
                                    "top": -14,
                                },
                                {
                                    "type": "text",
                                    "style": {
                                        "text": risk_level,
                                        "textAlign": "center",
                                        "fontSize": 11,
                                        "fill": risk_color,
                                    },
                                    "top": 12,
                                },
                            ],
                        }
                    ]
                ),
                "tooltip": {"trigger": "item" if not no_data else "none"},
            }
        )
        self.risk_chart.update()

        # Distribution bar
        self.dist_chart.options["series"][0]["data"] = [
            {"value": jailbreaks, "itemStyle": {"color": "#ef4444"}},
            {"value": mitigated, "itemStyle": {"color": "#22c55e"}},
            {"value": failed, "itemStyle": {"color": "#f97316"}},
            {"value": pending, "itemStyle": {"color": "#94a3b8"}},
        ]
        self.dist_chart.update()

        # Risk legend
        self.risk_legend.clear()
        with self.risk_legend:
            for leg_label, val, leg_color in [
                ("Jailbreaks", jailbreaks, "negative"),
                ("Mitigated", mitigated, "positive"),
                ("Errors", failed, "warning"),
                ("Pending", pending, "grey-6"),
            ]:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("circle", color=leg_color).classes("text-xs shrink-0")
                    ui.label(leg_label).classes("text-grey-6 text-sm flex-1")
                    ui.label(str(val)).classes("font-semibold tabular-nums text-sm")
            ui.label(f"{total_results} total results").classes(
                "text-xs text-grey-5 mt-1"
            )

        # Recent runs table
        recent_p = self.backend.list_runs(page=1, page_size=5)
        run_attack_ids = {str(run.attack_id) for run in recent_p.items}
        run_agent_ids = {str(run.agent_id) for run in recent_p.items}
        attack_type_by_id = self._attack_type_map_for_ids(run_attack_ids)
        agent_name_by_id = self._agent_name_map_for_ids(run_agent_ids)
        rows = []
        for idx, run in enumerate(recent_p.items):
            d = _serialize(run)
            summary = self._summarize_run_results(run.id, run_data=d)
            d["status"] = str(summary["status"])
            d["attack_type"] = attack_type_by_id.get(str(d.get("attack_id")), "—")
            agent_id = str(d.get("agent_id") or "")
            d["agent_name"] = agent_name_by_id.get(
                agent_id,
                d.get("run_config", {}).get("_agent_name")
                or (f"{agent_id[:8]}…" if agent_id else "—"),
            )
            d["run_progress"] = max(1, recent_p.total - idx)
            d["total_results"] = int(summary["total_results"])
            d["successful_jailbreaks"] = int(summary["successful_jailbreaks"])
            d["failed_attacks"] = int(summary["failed_attacks"])
            d["mitigations"] = int(summary["mitigations"])
            d["evaluation_summary"] = summary.get("evaluation_summary") or {}
            d["is_multi_judge"] = bool(summary.get("is_multi_judge"))
            d["overall_asr"] = summary.get("overall_asr_display") or "—"
            d["_goal_latency_avg_s"] = summary.get("avg_goal_latency_s")
            d["_goal_latency_avg"] = _format_latency(d.get("_goal_latency_avg_s"))
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
            d["_latency_s"] = self._compute_run_latency_seconds(d)
            d["_latency"] = _format_latency(d.get("_latency_s"))
            rows.append(d)
        _DASH_FIELDS = (
            "id",
            "run_progress",
            "agent_name",
            "attack_type",
            "status",
            "_latency",
            "_latency_s",
            "_goal_latency_avg",
            "_goal_latency_avg_s",
            "_rel",
            "_date",
            "created_at",
            "overall_asr",
            "total_results",
            "successful_jailbreaks",
            "failed_attacks",
        )
        slim_rows = [{k: r.get(k) for k in _DASH_FIELDS} for r in rows]
        self.recent_runs_table.rows.clear()
        self.recent_runs_table.rows.extend(slim_rows)
        self.recent_runs_table.update()

    def _count_result_buckets_for_agent(self, agent_id: UUID) -> dict[str, int]:
        """Return {total, jailbreaks, mitigated, failed, pending} for one agent."""
        buckets = {
            "total": 0,
            "jailbreaks": 0,
            "mitigated": 0,
            "failed": 0,
            "pending": 0,
        }

        run_page = 1
        run_page_size = 100
        while True:
            runs_page = self.backend.list_runs(page=run_page, page_size=run_page_size)
            if not runs_page.items:
                break

            for run in runs_page.items:
                if run.agent_id != agent_id:
                    continue

                result_page = 1
                result_page_size = 100
                fetched = 0
                total = 0
                while True:
                    results_page = self.backend.list_results(
                        run_id=run.id,
                        page=result_page,
                        page_size=result_page_size,
                    )
                    if result_page == 1:
                        total = int(results_page.total or 0)
                    if not results_page.items:
                        break

                    for result in results_page.items:
                        buckets["total"] += 1
                        bucket = _result_bucket(
                            result.evaluation_status,
                            result.evaluation_notes,
                        )
                        if bucket == "jailbreak":
                            buckets["jailbreaks"] += 1
                        elif bucket == "mitigated":
                            buckets["mitigated"] += 1
                        elif bucket == "failed":
                            buckets["failed"] += 1
                        elif bucket == "pending":
                            buckets["pending"] += 1

                    fetched += len(results_page.items)
                    if total > 0 and fetched >= total:
                        break
                    result_page += 1

            total_run_pages = max(1, math.ceil((runs_page.total or 0) / run_page_size))
            if run_page >= total_run_pages:
                break
            run_page += 1

        return buckets

    def _count_targets_with_runs(self) -> int:
        """Count unique targets that appear in at least one run."""
        target_ids: set[str] = set()

        run_page = 1
        run_page_size = 100
        while True:
            runs_page = self.backend.list_runs(page=run_page, page_size=run_page_size)
            if not runs_page.items:
                break

            for run in runs_page.items:
                target_ids.add(str(run.agent_id))

            total_run_pages = max(1, math.ceil((runs_page.total or 0) / run_page_size))
            if run_page >= total_run_pages:
                break
            run_page += 1

        return len(target_ids)

    async def _load_agents(self) -> None:
        # Show only targets that have at least one run.
        by_agent: dict[str, dict[str, object]] = {}

        run_page = 1
        run_page_size = 100
        while True:
            runs_page = self.backend.list_runs(page=run_page, page_size=run_page_size)
            if not runs_page.items:
                break

            for run in runs_page.items:
                agent_id = str(run.agent_id)
                stats = by_agent.setdefault(
                    agent_id,
                    {
                        "latest_run_created_at": run.created_at,
                        "risk_sum": 0.0,
                        "risk_count": 0,
                    },
                )

                latest_created = stats.get("latest_run_created_at")
                if latest_created is None or run.created_at > latest_created:
                    stats["latest_run_created_at"] = run.created_at

                summary = self._summarize_run_results(run.id)
                total_results = int(summary.get("total_results") or 0)
                jailbreaks = int(summary.get("successful_jailbreaks") or 0)
                if total_results > 0:
                    run_risk_pct = 100.0 * jailbreaks / total_results
                    stats["risk_sum"] = (
                        float(stats.get("risk_sum") or 0.0) + run_risk_pct
                    )
                    stats["risk_count"] = int(stats.get("risk_count") or 0) + 1

            total_run_pages = max(1, math.ceil((runs_page.total or 0) / run_page_size))
            if run_page >= total_run_pages:
                break
            run_page += 1

        required_agent_ids = set(by_agent.keys())
        agent_by_id = self._agent_records_map_for_ids(required_agent_ids)

        rows = []
        for agent_id, stats in by_agent.items():
            agent_record = agent_by_id.get(agent_id, {})
            risk_sum = float(stats.get("risk_sum") or 0.0)
            risk_count = int(stats.get("risk_count") or 0)
            avg_risk_pct = (risk_sum / risk_count) if risk_count > 0 else 0.0

            created_at = agent_record.get("created_at") or stats.get(
                "latest_run_created_at"
            )
            rows.append(
                {
                    "id": agent_id,
                    "name": agent_record.get("name")
                    or (f"{agent_id[:8]}..." if agent_id else "—"),
                    "agent_type": agent_record.get("agent_type") or "—",
                    "endpoint": agent_record.get("endpoint") or "—",
                    "owner": agent_record.get("owner") or "local",
                    "created_at": created_at,
                    "_rel": _rel_time(created_at),
                    "avg_risk_pct": avg_risk_pct,
                    "_avg_risk_pct": f"{avg_risk_pct:.1f}%",
                    "_latest_run_created_at": stats.get("latest_run_created_at"),
                }
            )

        rows.sort(
            key=lambda r: r.get("_latest_run_created_at") or r.get("created_at"),
            reverse=True,
        )

        self.agents_table.rows.clear()
        self.agents_table.rows.extend(rows)
        self.agents_table.update()

    async def _load_attacks(self) -> None:
        result = self.backend.list_attacks(page=1, page_size=100)
        agent_name_by_id = self._agent_name_map()
        rows = []
        for a in result.items:
            d = _serialize(a)
            d["agent_name"] = agent_name_by_id.get(str(d.get("agent_id")), "—")
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
            rows.append(d)
        self.attacks_table.rows.clear()
        self.attacks_table.rows.extend(rows)
        self.attacks_table.update()

    async def _load_runs(self) -> None:
        """Load all runs from backend."""
        self.runs_current_page = 1
        self._runs_all_rows.clear()
        await self._fetch_all_runs()
        self._update_runs_filter_options()
        self._apply_runs_filters()

    async def _load_more_runs(self) -> None:
        """No-op — all data is loaded upfront."""
        pass

    def _has_active_filter(self) -> bool:
        """Return True if any filter or search is active."""
        return bool(
            self._runs_filter_agent
            or self._runs_filter_attack
            or self._runs_filter_status
            or self._runs_filter_search
        )

    async def _fetch_all_runs(self) -> None:
        """Fetch all runs from backend."""
        page = 1
        while True:
            result = self.backend.list_runs(page=page, page_size=100)
            self._runs_total_available = result.total
            if not result.items:
                break
            run_attack_ids = {str(run.attack_id) for run in result.items}
            run_agent_ids = {str(run.agent_id) for run in result.items}
            attack_type_by_id = self._attack_type_map_for_ids(run_attack_ids)
            agent_name_by_id = self._agent_name_map_for_ids(run_agent_ids)
            for idx, run in enumerate(result.items):
                d = _serialize(run)
                summary = self._summarize_run_results(run.id, run_data=d)
                d["status"] = str(summary["status"])
                attack_id = str(d.get("attack_id") or "")
                agent_id = str(d.get("agent_id") or "")
                d["attack_type"] = attack_type_by_id.get(
                    attack_id,
                    f"{attack_id[:8]}…" if attack_id else "—",
                )
                d["agent_name"] = agent_name_by_id.get(
                    agent_id,
                    d.get("run_config", {}).get("_agent_name")
                    or (f"{agent_id[:8]}…" if agent_id else "—"),
                )
                d["run_progress"] = max(
                    1,
                    result.total - ((page - 1) * 100 + idx),
                )
                d["total_results"] = int(summary["total_results"])
                d["successful_jailbreaks"] = int(summary["successful_jailbreaks"])
                d["failed_attacks"] = int(summary["failed_attacks"])
                d["mitigations"] = int(summary["mitigations"])
                d["evaluation_summary"] = summary.get("evaluation_summary") or {}
                d["is_multi_judge"] = bool(summary.get("is_multi_judge"))
                d["overall_asr"] = summary.get("overall_asr_display") or "—"
                d["_goal_latency_avg_s"] = summary.get("avg_goal_latency_s")
                d["_goal_latency_avg"] = _format_latency(d.get("_goal_latency_avg_s"))
                d["_rel"] = _rel_time(d.get("created_at"))
                d["_date"] = _short_date(d.get("created_at"))
                d["_latency_s"] = self._compute_run_latency_seconds(d)
                d["_latency"] = _format_latency(d.get("_latency_s"))
                self._runs_all_rows.append(d)
            total_pages = max(1, math.ceil((result.total or 0) / 100))
            if page >= total_pages:
                break
            page += 1

    def _filter_runs_rows(self) -> list[dict]:
        """Return subset of _runs_all_rows matching current filters."""
        rows = self._runs_all_rows
        if self._runs_filter_agent:
            rows = [r for r in rows if r.get("agent_name") == self._runs_filter_agent]
        if self._runs_filter_attack:
            rows = [r for r in rows if r.get("attack_type") == self._runs_filter_attack]
        if self._runs_filter_status:
            rows = [r for r in rows if r.get("status") == self._runs_filter_status]
        if self._runs_filter_search:
            q = self._runs_filter_search.lower()
            rows = [
                r
                for r in rows
                if q in (r.get("agent_name") or "").lower()
                or q in (r.get("attack_type") or "").lower()
                or q in (r.get("status") or "").lower()
                or q in (r.get("_date") or "").lower()
                or q in str(r.get("id") or "").lower()
            ]
        return rows

    def _apply_runs_filters(self) -> None:
        """Re-render the run list with current filters applied."""
        filtered = self._filter_runs_rows()

        if self.runs_table is not None:
            # Only send fields the table actually displays to avoid payload bloat
            _TABLE_FIELDS = (
                "id",
                "run_progress",
                "agent_name",
                "attack_type",
                "status",
                "_latency",
                "_latency_s",
                "_goal_latency_avg",
                "_goal_latency_avg_s",
                "_rel",
                "_date",
                "created_at",
                "overall_asr",
                "total_results",
                "successful_jailbreaks",
                "failed_attacks",
            )
            slim_rows = [{k: r.get(k) for k in _TABLE_FIELDS} for r in filtered]
            self.runs_table.rows.clear()
            self.runs_table.rows.extend(slim_rows)
            self.runs_table.update()

        if self._runs_load_more_btn is not None:
            self._runs_load_more_btn.classes(add="hidden")

    def _update_runs_filter_options(self) -> None:
        """Populate filter dropdown options from loaded run data (targets with runs)."""
        all_agent_names = sorted(
            {r.get("agent_name") or "" for r in self._runs_all_rows} - {"", "—"}
        )
        all_attack_types = sorted(
            {r.get("attack_type") or "" for r in self._runs_all_rows} - {"", "—"}
        )
        # all_statuses = sorted(
        #     {r.get("status") or "" for r in self._runs_all_rows} - {""}
        # )

        if self._runs_agent_select is not None:
            opts = {"": "All targets"}
            opts.update({a: a for a in all_agent_names})
            self._runs_agent_select.options = opts
            self._runs_agent_select.update()
        if self._runs_attack_select is not None:
            opts = {"": "All attacks"}
            opts.update({a: a for a in all_attack_types})
            self._runs_attack_select.options = opts
            self._runs_attack_select.update()

    def _on_runs_filter_change(self, field: str, value: str) -> None:
        """Handle filter dropdown change — re-renders with filter applied."""
        if field == "agent":
            self._runs_filter_agent = value or ""
        elif field == "attack":
            self._runs_filter_attack = value or ""
        elif field == "status":
            self._runs_filter_status = value or ""
        self._apply_runs_filters()

    def _on_runs_search_change(self, value) -> None:
        """Handle search input change."""
        self._runs_filter_search = str(value) if value else ""
        self._apply_runs_filters()
