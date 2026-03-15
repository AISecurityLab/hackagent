# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
HackAgent Dashboard — NiceGUI application.

Exposes a FastAPI REST API over the HackAgent storage backend and serves the
dashboard UI at ``/`` using NiceGUI (Quasar/Vue).  Dark/light mode works
correctly via Quasar's built-in theming.  The trace side panel uses a native
Quasar right-drawer with smooth animation, replacing the old Alpine.js
slide-over.

Public API:
    create_app(backend=None, db_path=None) -> _DashboardApp
    _DashboardApp.run(host, port, show)
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from nicegui import app as _fastapi_app  # NiceGUI's internal FastAPI instance
from nicegui import ui

_BRAND = "#dc2626"  # red-600


# ── Helpers ───────────────────────────────────────────────────────────────────


def _serialize(record) -> dict:
    return record.model_dump(mode="json")


def _rel_time(iso: str | None) -> str:
    if not iso:
        return "—"
    with contextlib.suppress(Exception):
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = (datetime.now(timezone.utc) - dt).total_seconds()
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff // 60)}m ago"
        if diff < 86400:
            return f"{int(diff // 3600)}h ago"
        if diff < 604_800:
            return f"{int(diff // 86400)}d ago"
        return dt.strftime("%b %d %Y")
    return iso or "—"


def _eval_label(status: str | None) -> str:
    s = (status or "").upper()
    if "SUCCESSFUL_JAILBREAK" in s:
        return "Jailbreak"
    if "FAILED_JAILBREAK" in s:
        return "Mitigated"
    if "PASSED_CRITERIA" in s:
        return "Passed"
    if "FAILED_CRITERIA" in s:
        return "Failed"
    if "ERROR_AGENT" in s:
        return "Agent Error"
    if "ERROR" in s:
        return "Error"
    if "NOT_EVALUATED" in s:
        return "Pending"
    return status or "N/A"


def _eval_color(status: str | None) -> str:
    s = (status or "").upper()
    if "SUCCESSFUL_JAILBREAK" in s:
        return "negative"
    if "FAILED_JAILBREAK" in s or "PASSED_CRITERIA" in s:
        return "positive"
    if "ERROR" in s:
        return "warning"
    return "grey-6"


def _step_color(step_type: str | None) -> str:
    s = (step_type or "").upper()
    if "TOOL_RESPONSE" in s:
        return "indigo"
    if "TOOL_CALL" in s:
        return "deep-purple"
    if "AGENT_THOUGHT" in s:
        return "blue"
    if "AGENT_RESPONSE" in s:
        return "green"
    if "MCP" in s:
        return "teal"
    if "A2A" in s:
        return "cyan"
    return "grey"


# ── App wrapper ───────────────────────────────────────────────────────────────


class _DashboardApp:
    """Return value of ``create_app()`` — wraps ``ui.run()``."""

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 7860,
        show: bool = True,
        **_kwargs,  # absorb legacy Flask kwargs (debug=, use_reloader=)
    ) -> None:
        ui.run(
            host=host,
            port=port,
            title="HackAgent Dashboard",
            show=show,
            reload=False,
            storage_secret="hackagent-local-v1",
            favicon="🛡️",
        )


# ── App factory ───────────────────────────────────────────────────────────────


def create_app(
    backend=None,
    db_path: Optional[str] = None,
) -> _DashboardApp:
    """Register REST API routes and the NiceGUI UI page.

    Args:
        backend: Any ``StorageBackend``-compatible instance.
        db_path: SQLite path override (only used when *backend* is None).

    Returns:
        A ``_DashboardApp`` whose ``.run()`` starts the NiceGUI server.
    """
    if backend is None:
        from hackagent.server.storage.local import LocalBackend

        backend = LocalBackend(db_path=db_path)

    # ── REST API (FastAPI) ────────────────────────────────────────────────────

    @_fastapi_app.get("/api/status")
    async def api_status():
        ctx = backend.get_context()
        return {
            "status": "ok",
            "mode": "local" if backend.get_api_key() is None else "remote",
            "org_id": str(ctx.org_id),
            "user_id": ctx.user_id,
            "db_path": str(backend._db_path) if hasattr(backend, "_db_path") else None,
        }

    @_fastapi_app.get("/api/stats")
    async def api_stats():
        agents_p = backend.list_agents(page=1, page_size=1)
        attacks_p = backend.list_attacks(page=1, page_size=1)
        runs_p = backend.list_runs(page=1, page_size=200)
        total_results = jailbreaks = passed = errors = not_evaluated = 0
        for run in runs_p.items:
            rp = backend.list_results(run_id=run.id, page=1, page_size=500)
            total_results += rp.total
            for r in rp.items:
                s = r.evaluation_status.upper()
                if "SUCCESSFUL_JAILBREAK" in s:
                    jailbreaks += 1
                elif "PASSED" in s:
                    passed += 1
                elif "ERROR" in s:
                    errors += 1
                elif "NOT_EVALUATED" in s:
                    not_evaluated += 1
        risk_pct = (
            round(100 * jailbreaks / max(total_results, 1)) if total_results else 0
        )
        return {
            "total_agents": agents_p.total,
            "total_attacks": attacks_p.total,
            "total_runs": runs_p.total,
            "total_results": total_results,
            "successful_jailbreaks": jailbreaks,
            "passed": passed,
            "errors": errors,
            "not_evaluated": not_evaluated,
            "risk_percentage": risk_pct,
        }

    @_fastapi_app.get("/api/agents")
    async def api_agents():
        result = backend.list_agents(page=1, page_size=100)
        return {"items": [_serialize(a) for a in result.items], "total": result.total}

    @_fastapi_app.get("/api/attacks")
    async def api_attacks():
        result = backend.list_attacks(page=1, page_size=100)
        return {"items": [_serialize(a) for a in result.items], "total": result.total}

    @_fastapi_app.get("/api/runs")
    async def api_runs():
        result = backend.list_runs(page=1, page_size=50)
        items = []
        for run in result.items:
            d = _serialize(run)
            rp = backend.list_results(run_id=run.id, page=1, page_size=500)
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
            )
            items.append(d)
        return {"items": items, "total": result.total}

    # ── NiceGUI UI ────────────────────────────────────────────────────────────

    @ui.page("/")
    async def index():  # noqa: C901
        ui.colors(primary=_BRAND)

        # ── Dark mode (persisted in browser storage) ──────────────────────────
        dark = ui.dark_mode()
        if _fastapi_app.storage.browser.get("hackagent_dark"):
            dark.enable()

        def toggle_dark() -> None:
            dark.toggle()
            _fastapi_app.storage.browser["hackagent_dark"] = dark.value
            dark_btn.props(f"icon={'light_mode' if dark.value else 'dark_mode'}")

        # ── Per-page mutable state ────────────────────────────────────────────
        current_view: dict[str, str] = {"value": "dashboard"}

        # ── RIGHT DRAWER — Result + Trace detail ──────────────────────────────
        with ui.right_drawer(fixed=True, bordered=True, elevated=True).props(
            "width=520 overlay behavior=desktop"
        ) as right_drawer:
            right_drawer.hide()

            with ui.column().classes("w-full h-full gap-0"):
                with ui.row().classes(
                    "items-center justify-between w-full shrink-0 px-5 py-3 border-b"
                ):
                    result_detail_title = ui.label("Result Detail").classes(
                        "font-semibold text-base"
                    )
                    ui.button(icon="close", on_click=right_drawer.hide).props(
                        "flat round dense"
                    )
                result_area = ui.scroll_area().classes("flex-1 w-full")

        async def show_result_detail(result: dict) -> None:
            """Populate the right drawer with result + traces and open it."""
            result_area.clear()
            eval_status = result.get("evaluation_status", "")
            s = eval_status.upper()

            with result_area:
                with ui.column().classes("w-full gap-4 p-5"):
                    ui.label(result.get("id", "")).classes(
                        "font-mono text-xs text-grey-6 select-all"
                    )
                    result_detail_title.text = (
                        f"Result · #{(result.get('goal_index', 0) or 0) + 1}"
                    )

                    # Evaluation banner
                    if "SUCCESSFUL_JAILBREAK" in s:
                        with (
                            ui.card()
                            .tight()
                            .classes(
                                "w-full border border-red-300 dark:border-red-700 "
                                "bg-red-50 dark:bg-red-900/30"
                            )
                        ):
                            with ui.row().classes("gap-3 items-start p-4"):
                                ui.icon("lock_open", color="negative").classes(
                                    "text-2xl mt-0.5"
                                )
                                with ui.column().classes("gap-0.5"):
                                    ui.label("Jailbreak Successful").classes(
                                        "font-semibold text-negative text-sm"
                                    )
                                    if result.get("evaluation_notes"):
                                        ui.label(result["evaluation_notes"]).classes(
                                            "text-xs text-grey-6"
                                        )
                    elif "FAILED_JAILBREAK" in s or "PASSED_CRITERIA" in s:
                        with (
                            ui.card()
                            .tight()
                            .classes(
                                "w-full border border-green-300 dark:border-green-700 "
                                "bg-green-50 dark:bg-green-900/30"
                            )
                        ):
                            with ui.row().classes("gap-3 items-start p-4"):
                                ui.icon("security", color="positive").classes(
                                    "text-2xl mt-0.5"
                                )
                                with ui.column().classes("gap-0.5"):
                                    ui.label("Model Resisted").classes(
                                        "font-semibold text-positive text-sm"
                                    )
                                    if result.get("evaluation_notes"):
                                        ui.label(result["evaluation_notes"]).classes(
                                            "text-xs text-grey-6"
                                        )
                    elif "ERROR" in s:
                        with (
                            ui.card()
                            .tight()
                            .classes(
                                "w-full border border-orange-300 dark:border-orange-700 "
                                "bg-orange-50 dark:bg-orange-900/30"
                            )
                        ):
                            with ui.row().classes("gap-3 items-start p-4"):
                                ui.icon("warning_amber", color="warning").classes(
                                    "text-2xl mt-0.5"
                                )
                                with ui.column().classes("gap-0.5"):
                                    ui.label("Evaluation Error").classes(
                                        "font-semibold text-warning text-sm"
                                    )
                                    if result.get("evaluation_notes"):
                                        ui.label(result["evaluation_notes"]).classes(
                                            "text-xs text-grey-6"
                                        )

                    # Goal
                    with ui.column().classes("gap-1"):
                        ui.label("GOAL").classes(
                            "text-[10px] font-semibold tracking-widest "
                            "text-grey-5 uppercase"
                        )
                        ui.label(result.get("goal", "—")).classes(
                            "text-sm leading-relaxed"
                        )

                    with ui.row().classes("items-center justify-between"):
                        ui.badge(
                            _eval_label(eval_status),
                            color=_eval_color(eval_status),
                        ).classes("text-xs px-2 py-0.5")
                        ui.label(
                            f"Goal #{(result.get('goal_index', 0) or 0) + 1}"
                        ).classes("text-xs text-grey-6")

                    # Metrics
                    metrics = result.get("evaluation_metrics")
                    if metrics and isinstance(metrics, dict) and metrics:
                        with ui.column().classes("gap-1"):
                            ui.label("METRICS").classes(
                                "text-[10px] font-semibold tracking-widest "
                                "text-grey-5 uppercase"
                            )
                            ui.code(
                                json.dumps(metrics, indent=2), language="json"
                            ).classes("w-full text-xs max-h-48")

                    ui.separator()

                    with ui.row().classes("items-center gap-2"):
                        ui.label("TRACE TIMELINE").classes(
                            "text-[10px] font-semibold tracking-widest "
                            "text-grey-5 uppercase"
                        )
                        trace_count_badge = ui.badge("…", color="grey-6").classes(
                            "text-xs"
                        )

                    with ui.column().classes("w-full gap-0") as trace_container:
                        with ui.row().classes("items-center gap-2 py-4 justify-center"):
                            ui.spinner("dots")
                            ui.label("Loading traces…").classes("text-sm text-grey-6")

            right_drawer.show()

            # Load traces async
            try:
                traces_raw = backend.list_traces(result_id=UUID(result["id"]))
                trace_container.clear()

                if not traces_raw:
                    with trace_container:
                        ui.label("No traces recorded for this result.").classes(
                            "text-sm text-grey-6 text-center py-6"
                        )
                    trace_count_badge.set_text("0")
                    trace_count_badge.props("color=grey-6")
                else:
                    trace_count_badge.set_text(str(len(traces_raw)))
                    trace_count_badge.props("color=primary")
                    with trace_container:
                        for i, trace in enumerate(traces_raw):
                            td = _serialize(trace)
                            color = _step_color(td.get("step_type"))
                            step_label = (
                                (td.get("step_type") or "").replace("_", " ").title()
                            )
                            is_last = i == len(traces_raw) - 1

                            with ui.row().classes("gap-0 w-full"):
                                # Timeline rail
                                with ui.column().classes(
                                    "items-center shrink-0 w-8 gap-0"
                                ):
                                    ui.badge(
                                        str(td.get("sequence", i + 1)),
                                        color=color,
                                    ).classes(
                                        "w-6 h-6 rounded-full text-[10px] "
                                        "font-bold flex items-center "
                                        "justify-center shrink-0"
                                    )
                                    if not is_last:
                                        ui.element("div").classes(
                                            "w-px flex-1 min-h-4 bg-grey-3 "
                                            "dark:bg-grey-8 my-1"
                                        )
                                # Step body
                                with ui.column().classes("flex-1 min-w-0 pb-4 gap-1.5"):
                                    with ui.row().classes(
                                        "items-center justify-between w-full"
                                    ):
                                        ui.label(step_label).classes(
                                            f"text-xs font-semibold text-{color}"
                                        )
                                        ui.label(
                                            _rel_time(td.get("created_at"))
                                        ).classes("text-xs text-grey-6")
                                    content = td.get("content")
                                    if content is not None:
                                        raw = (
                                            json.dumps(content, indent=2)
                                            if isinstance(content, (dict, list))
                                            else str(content)
                                        )
                                        ui.code(raw, language="json").classes(
                                            "w-full text-xs max-h-52 overflow-auto"
                                        )
            except Exception as exc:
                trace_container.clear()
                with trace_container:
                    with ui.row().classes("gap-2 items-center py-4"):
                        ui.icon("error_outline", color="negative")
                        ui.label(f"Error loading traces: {exc}").classes(
                            "text-sm text-negative"
                        )

        # ── Reusable run table factory ────────────────────────────────────────

        def _make_run_table(on_row_click, pagination=None) -> ui.table:
            tbl = ui.table(
                columns=[
                    {
                        "name": "id",
                        "label": "Run",
                        "field": "id",
                        "align": "left",
                    },
                    {
                        "name": "status",
                        "label": "Status",
                        "field": "status",
                        "align": "left",
                    },
                    {
                        "name": "results",
                        "label": "Results",
                        "field": "total_results",
                        "align": "left",
                    },
                    {
                        "name": "created_at",
                        "label": "Created",
                        "field": "created_at",
                        "align": "left",
                    },
                ],
                rows=[],
                row_key="id",
                pagination=pagination or {"rowsPerPage": 5},
            ).classes("w-full")
            tbl.add_slot(
                "body-cell-id",
                r"""
                <q-td :props="props" class="cursor-pointer"
                      @click="$emit('rowClick', props.row)">
                  <div class="font-mono text-xs font-medium">
                    {{ props.row.id.slice(0,8) }}…
                  </div>
                  <div class="text-xs text-grey-6 truncate max-w-xs">
                    {{ props.row.run_notes || '—' }}
                  </div>
                </q-td>
                """,
            )
            tbl.add_slot(
                "body-cell-status",
                r"""
                <q-td :props="props">
                  <q-badge
                    :color="props.row.status === 'COMPLETED' ? 'positive'
                          : props.row.status === 'RUNNING'   ? 'info'
                          : props.row.status === 'FAILED'    ? 'negative'
                          : 'warning'"
                    :label="props.row.status" />
                  <q-spinner v-if="props.row.status === 'RUNNING'"
                             color="info" size="xs" class="ml-2" />
                </q-td>
                """,
            )
            tbl.add_slot(
                "body-cell-results",
                r"""
                <q-td :props="props">
                  <span class="tabular-nums font-medium">
                    {{ props.row.total_results ?? 0 }}
                  </span>
                  <q-badge v-if="(props.row.successful_jailbreaks ?? 0) > 0"
                           color="negative" class="ml-2">
                    ⚠ {{ props.row.successful_jailbreaks }}
                  </q-badge>
                </q-td>
                """,
            )
            tbl.add_slot(
                "body-cell-created_at",
                r"""
                <q-td :props="props">
                  <span class="text-xs text-grey-6">{{ props.row._rel }}</span>
                </q-td>
                """,
            )
            tbl.on("rowClick", lambda e, cb=on_row_click: cb(e.args))
            return tbl

        # ── LEFT SIDEBAR ──────────────────────────────────────────────────────
        with ui.left_drawer(top_corner=True, bottom_corner=True).props(
            "mini mini-to-overlay width=220 mini-width=60 bordered"
        ) as sidebar:
            with ui.row().classes("items-center gap-3 px-3 py-4 shrink-0"):
                with ui.element("div").classes(
                    "w-7 h-7 bg-red-600 rounded flex items-center "
                    "justify-center shrink-0"
                ):
                    ui.icon("security", color="white").classes("text-base")
                ui.label("HackAgent").classes("font-semibold text-base")

            ui.separator().classes("mb-1")

            nav_items = [
                ("dashboard", "Dashboard", "dashboard"),
                ("agents", "Agents", "smart_toy"),
                ("attacks", "Attacks", "flash_on"),
                ("runs", "History", "assignment"),
            ]
            nav_buttons: dict[str, ui.button] = {}
            for view_id, label, icon_name in nav_items:
                btn = (
                    ui.button(
                        label,
                        icon=icon_name,
                        on_click=lambda v=view_id: navigate(v),
                    )
                    .props("flat align=left no-caps")
                    .classes("w-full justify-start px-3 rounded-lg")
                )
                nav_buttons[view_id] = btn

            ui.separator().classes("my-1")

            with ui.row().classes("items-center gap-3 px-3 py-2"):
                ui.icon("menu_book", size="xs").classes("text-grey-6 shrink-0")
                ui.link("Docs", "https://docs.hackagent.dev", new_tab=True).classes(
                    "text-sm text-grey-6 no-underline"
                )

            ui.space()
            ui.separator()

            with ui.row().classes("px-3 py-3 gap-2 items-center"):
                mode_dot = ui.icon("circle", size="xs").classes("text-positive text-xs")
                mode_lbl = ui.label("local mode").classes("text-xs text-grey-6")

            async def _load_mode() -> None:
                with contextlib.suppress(Exception):
                    is_remote = backend.get_api_key() is not None
                    mode_dot.classes(
                        add="text-info" if is_remote else "text-positive",
                        remove="text-positive text-info",
                    )
                    mode_lbl.text = "remote mode" if is_remote else "local mode"

            ui.timer(0.1, _load_mode, once=True)

        # ── HEADER ────────────────────────────────────────────────────────────
        with ui.header(elevated=True).classes(
            "items-center justify-between px-4 py-2 bg-primary"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="menu", on_click=sidebar.toggle).props(
                    "flat round dense color=white"
                )
                page_title = ui.label("Dashboard").classes(
                    "text-white font-semibold text-lg"
                )

            with ui.row().classes("items-center gap-1"):
                loading_spinner = ui.spinner("dots", size="1.2em", color="white")
                loading_spinner.set_visibility(False)
                dark_btn = ui.button(
                    icon="dark_mode" if not dark.value else "light_mode",
                    on_click=toggle_dark,
                ).props("flat round dense color=white")
                ui.button(
                    icon="refresh",
                    on_click=lambda: ui.timer(0, refresh_view, once=True),
                ).props("flat round dense color=white")

        # ── MAIN PANELS ───────────────────────────────────────────────────────
        with ui.column().classes("w-full p-5 gap-6"):
            dashboard_panel = ui.column().classes("w-full gap-6")
            agents_panel = ui.column().classes("w-full gap-4")
            attacks_panel = ui.column().classes("w-full gap-4")
            runs_panel = ui.column().classes("w-full gap-4")
            all_panels = {
                "dashboard": dashboard_panel,
                "agents": agents_panel,
                "attacks": attacks_panel,
                "runs": runs_panel,
            }
            for panel in all_panels.values():
                panel.set_visibility(False)
            dashboard_panel.set_visibility(True)

            # ── DASHBOARD ─────────────────────────────────────────────────────
            with dashboard_panel:
                # Stat cards
                with ui.row().classes("w-full flex-wrap gap-4"):
                    stat_labels: dict[str, ui.label] = {}
                    for s_label, s_key, s_icon, s_color in [
                        ("Agents", "total_agents", "smart_toy", "blue"),
                        ("Attacks", "total_attacks", "flash_on", "orange"),
                        ("Runs", "total_runs", "assignment", "green"),
                        ("Jailbreaks", "successful_jailbreaks", "lock_open", "red"),
                    ]:
                        with ui.card().classes("flex-1 min-w-36"):
                            with ui.row().classes("items-center justify-between mb-2"):
                                ui.label(s_label).classes("text-sm text-grey-6")
                                ui.icon(s_icon, color=s_color).classes("text-xl")
                            stat_labels[s_key] = ui.label("—").classes(
                                "text-3xl font-bold"
                            )

                # Charts
                with ui.row().classes("w-full flex-wrap gap-4 items-start"):
                    with ui.card().classes("flex-1 min-w-72"):
                        ui.label("Risk Overview").classes("font-semibold text-sm")
                        ui.label("Jailbreak rate across all evaluated results").classes(
                            "text-xs text-grey-6 mb-4"
                        )
                        with ui.row().classes("items-center gap-6 flex-wrap"):
                            risk_chart = ui.echart(
                                {
                                    "series": [
                                        {
                                            "type": "pie",
                                            "radius": ["58%", "80%"],
                                            "data": [
                                                {
                                                    "value": 1,
                                                    "name": "No data",
                                                    "itemStyle": {"color": "#94a3b8"},
                                                }
                                            ],
                                            "label": {"show": False},
                                        }
                                    ],
                                    "graphic": [],
                                    "tooltip": {"show": False},
                                }
                            ).classes("w-36 h-36 shrink-0")
                            risk_legend = ui.column().classes("gap-2 flex-1")

                    with ui.card().classes("flex-1 min-w-72"):
                        ui.label("Result Distribution").classes("font-semibold text-sm")
                        ui.label("Evaluation outcomes across all runs").classes(
                            "text-xs text-grey-6 mb-4"
                        )
                        dist_chart = ui.echart(
                            {
                                "xAxis": {
                                    "type": "category",
                                    "data": [
                                        "Jailbreaks",
                                        "Passed",
                                        "Errors",
                                        "Pending",
                                    ],
                                    "axisLine": {"show": False},
                                    "axisTick": {"show": False},
                                },
                                "yAxis": {
                                    "type": "value",
                                    "minInterval": 1,
                                    "splitLine": {"lineStyle": {"type": "dashed"}},
                                },
                                "series": [
                                    {
                                        "type": "bar",
                                        "data": [0, 0, 0, 0],
                                        "itemStyle": {"borderRadius": [4, 4, 0, 0]},
                                        "barMaxWidth": 60,
                                    }
                                ],
                                "grid": {
                                    "left": "3%",
                                    "right": "3%",
                                    "top": "8%",
                                    "bottom": "3%",
                                    "containLabel": True,
                                },
                                "tooltip": {"trigger": "axis"},
                            }
                        ).classes("w-full h-44")

                # Recent runs
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center justify-between mb-3"):
                        ui.label("Recent Runs").classes("font-semibold text-sm")
                        ui.button(
                            "View all →", on_click=lambda: navigate("runs")
                        ).props("flat dense").classes("text-xs text-grey-6")

                    recent_runs_table = _make_run_table(
                        on_row_click=lambda run: ui.timer(
                            0, lambda r=run: _open_run_results(r), once=True
                        )
                    )

            # ── AGENTS ────────────────────────────────────────────────────────
            with agents_panel:
                with ui.card().classes("w-full"):
                    agents_table = ui.table(
                        columns=[
                            {
                                "name": "name",
                                "label": "Agent",
                                "field": "name",
                                "align": "left",
                                "sortable": True,
                            },
                            {
                                "name": "agent_type",
                                "label": "Type",
                                "field": "agent_type",
                                "align": "left",
                            },
                            {
                                "name": "endpoint",
                                "label": "Endpoint",
                                "field": "endpoint",
                                "align": "left",
                            },
                            {
                                "name": "owner",
                                "label": "Owner",
                                "field": "owner",
                                "align": "left",
                            },
                            {
                                "name": "created_at",
                                "label": "Created",
                                "field": "created_at",
                                "align": "left",
                            },
                        ],
                        rows=[],
                        row_key="id",
                        pagination={"rowsPerPage": 25},
                    ).classes("w-full")
                    agents_table.add_slot(
                        "body-cell-name",
                        r"""
                        <q-td :props="props">
                          <div class="font-medium text-sm">{{ props.row.name }}</div>
                          <div class="font-mono text-xs text-grey-6">
                            {{ props.row.id.slice(0,8) }}…
                          </div>
                        </q-td>
                        """,
                    )
                    agents_table.add_slot(
                        "body-cell-agent_type",
                        r"""
                        <q-td :props="props">
                          <q-badge
                            :color="{'LITELLM':'purple','OPENAI_SDK':'green',
                                     'GOOGLE_ADK':'blue','OLLAMA':'orange'}
                                    [props.row.agent_type] || 'grey-6'"
                            :label="props.row.agent_type" />
                        </q-td>
                        """,
                    )
                    agents_table.add_slot(
                        "body-cell-created_at",
                        r"""
                        <q-td :props="props">
                          <span class="text-xs text-grey-6">{{ props.row._rel }}</span>
                        </q-td>
                        """,
                    )

            # ── ATTACKS ───────────────────────────────────────────────────────
            with attacks_panel:
                with ui.card().classes("w-full"):
                    attacks_table = ui.table(
                        columns=[
                            {
                                "name": "id",
                                "label": "ID",
                                "field": "id",
                                "align": "left",
                            },
                            {
                                "name": "type",
                                "label": "Type",
                                "field": "type",
                                "align": "left",
                            },
                            {
                                "name": "agent_id",
                                "label": "Agent",
                                "field": "agent_id",
                                "align": "left",
                            },
                            {
                                "name": "created_at",
                                "label": "Created",
                                "field": "created_at",
                                "align": "left",
                            },
                        ],
                        rows=[],
                        row_key="id",
                        pagination={"rowsPerPage": 25},
                    ).classes("w-full")
                    attacks_table.add_slot(
                        "body-cell-id",
                        r"<q-td :props='props'>"
                        r"<span class='font-mono text-xs'>{{ props.row.id.slice(0,8) }}…</span>"
                        r"</q-td>",
                    )
                    attacks_table.add_slot(
                        "body-cell-type",
                        r"<q-td :props='props'>"
                        r"<q-badge color='orange' :label='props.row.type' />"
                        r"</q-td>",
                    )
                    attacks_table.add_slot(
                        "body-cell-agent_id",
                        r"<q-td :props='props'>"
                        r"<span class='font-mono text-xs'>{{ props.row.agent_id.slice(0,8) }}…</span>"
                        r"</q-td>",
                    )
                    attacks_table.add_slot(
                        "body-cell-created_at",
                        r"<q-td :props='props'>"
                        r"<span class='text-xs text-grey-6'>{{ props.row._rel }}</span>"
                        r"</q-td>",
                    )

            # ── RUNS / HISTORY ────────────────────────────────────────────────
            with runs_panel:
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center justify-between mb-1 px-2"):
                        runs_count_label = ui.label("").classes("text-sm text-grey-6")

                    runs_table = _make_run_table(
                        on_row_click=lambda run: ui.timer(
                            0, lambda r=run: _open_run_results(r), once=True
                        ),
                        pagination={"rowsPerPage": 25},
                    )

        # ── RUN RESULTS DIALOG ────────────────────────────────────────────────
        with ui.dialog() as run_dialog:
            with ui.card().classes("w-full max-w-5xl h-[80vh] flex flex-col gap-4"):
                with ui.row().classes("items-center justify-between w-full shrink-0"):
                    run_dialog_title = ui.label("Run Results").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=run_dialog.close).props(
                        "flat round"
                    )

                results_table = ui.table(
                    columns=[
                        {
                            "name": "num",
                            "label": "#",
                            "field": "goal_index",
                            "align": "center",
                            "style": "width:50px",
                        },
                        {
                            "name": "goal",
                            "label": "Goal",
                            "field": "goal",
                            "align": "left",
                        },
                        {
                            "name": "eval",
                            "label": "Evaluation",
                            "field": "evaluation_status",
                            "align": "left",
                        },
                        {
                            "name": "notes",
                            "label": "Notes",
                            "field": "evaluation_notes",
                            "align": "left",
                        },
                    ],
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                ).classes("w-full flex-1")

                _EVAL_COLOR_JS = (
                    "props.row.evaluation_status?.toUpperCase().includes('SUCCESSFUL_JAILBREAK') ? 'negative'"
                    " : (props.row.evaluation_status?.toUpperCase().includes('PASSED') ||"
                    "    props.row.evaluation_status?.toUpperCase().includes('FAILED_JAILBREAK')) ? 'positive'"
                    " : props.row.evaluation_status?.toUpperCase().includes('ERROR') ? 'warning'"
                    " : 'grey-6'"
                )
                _EVAL_LABEL_JS = (
                    "props.row.evaluation_status?.toUpperCase().includes('SUCCESSFUL_JAILBREAK') ? 'Jailbreak'"
                    " : props.row.evaluation_status?.toUpperCase().includes('PASSED_CRITERIA') ? 'Passed'"
                    " : props.row.evaluation_status?.toUpperCase().includes('FAILED_JAILBREAK') ? 'Mitigated'"
                    " : props.row.evaluation_status?.toUpperCase().includes('FAILED_CRITERIA') ? 'Failed'"
                    " : props.row.evaluation_status?.toUpperCase().includes('ERROR') ? 'Error'"
                    " : 'Pending'"
                )
                results_table.add_slot(
                    "body-cell-num",
                    r"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                      <span class="tabular-nums text-grey-6 text-xs">
                        {{ (props.row.goal_index ?? 0) + 1 }}
                      </span>
                    </q-td>
                    """,
                )
                results_table.add_slot(
                    "body-cell-goal",
                    r"""
                    <q-td :props="props" class="cursor-pointer max-w-md"
                          @click="$emit('rowClick', props.row)">
                      <span class="text-xs truncate block max-w-md"
                            :title="props.row.goal">
                        {{ props.row.goal }}
                      </span>
                    </q-td>
                    """,
                )
                results_table.add_slot(
                    "body-cell-eval",
                    f"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                      <q-badge :color="{_EVAL_COLOR_JS}"
                               :label="{_EVAL_LABEL_JS}" />
                    </q-td>
                    """,
                )
                results_table.add_slot(
                    "body-cell-notes",
                    r"""
                    <q-td :props="props" class="cursor-pointer max-w-xs"
                          @click="$emit('rowClick', props.row)">
                      <span class="text-xs text-grey-6 truncate block max-w-xs">
                        {{ props.row.evaluation_notes || '—' }}
                      </span>
                    </q-td>
                    """,
                )
                results_table.on(
                    "rowClick",
                    lambda e: ui.timer(
                        0, lambda args=e.args: show_result_detail(args), once=True
                    ),
                )

        # ── Navigation ────────────────────────────────────────────────────────

        _view_labels = {
            "dashboard": "Dashboard",
            "agents": "Agents",
            "attacks": "Attacks",
            "runs": "History",
        }

        def _highlight_nav(view: str) -> None:
            for v, btn in nav_buttons.items():
                if v == view:
                    btn.props(remove="flat").props(add="unelevated color=primary")
                else:
                    btn.props(
                        remove="unelevated color=primary",
                        add="flat",
                    )

        def navigate(view: str) -> None:
            current_view["value"] = view
            for v, panel in all_panels.items():
                panel.set_visibility(v == view)
            page_title.text = _view_labels.get(view, "Dashboard")
            _highlight_nav(view)
            ui.timer(0, lambda: refresh_view(), once=True)

        async def refresh_view() -> None:
            _v = current_view["value"]
            loading_spinner.set_visibility(True)
            try:
                if _v == "dashboard":
                    await _load_dashboard()
                elif _v == "agents":
                    await _load_agents()
                elif _v == "attacks":
                    await _load_attacks()
                elif _v == "runs":
                    await _load_runs()
            except Exception as exc:
                ui.notify(f"Failed to load data: {exc}", type="negative")
            finally:
                loading_spinner.set_visibility(False)

        # ── Data loaders ──────────────────────────────────────────────────────

        async def _load_dashboard() -> None:
            agents_p = backend.list_agents(page=1, page_size=1)
            attacks_p = backend.list_attacks(page=1, page_size=1)
            runs_p = backend.list_runs(page=1, page_size=200)
            total_results = jailbreaks = passed = errors = not_eval = 0
            for run in runs_p.items:
                rp = backend.list_results(run_id=run.id, page=1, page_size=500)
                total_results += rp.total
                for r in rp.items:
                    sv = r.evaluation_status.upper()
                    if "SUCCESSFUL_JAILBREAK" in sv:
                        jailbreaks += 1
                    elif "PASSED" in sv:
                        passed += 1
                    elif "ERROR" in sv:
                        errors += 1
                    elif "NOT_EVALUATED" in sv:
                        not_eval += 1

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

            stat_labels["total_agents"].set_text(str(agents_p.total))
            stat_labels["total_attacks"].set_text(str(attacks_p.total))
            stat_labels["total_runs"].set_text(str(runs_p.total))
            stat_labels["successful_jailbreaks"].set_text(str(jailbreaks))

            # Risk donut
            no_data = total_results == 0
            risk_chart.options.clear()
            risk_chart.options.update(
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
                                        "value": passed,
                                        "name": "Passed",
                                        "itemStyle": {"color": "#22c55e"},
                                    },
                                    {
                                        "value": errors,
                                        "name": "Errors",
                                        "itemStyle": {"color": "#f97316"},
                                    },
                                    {
                                        "value": not_eval,
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
            risk_chart.update()

            # Distribution bar
            dist_chart.options["series"][0]["data"] = [
                {"value": jailbreaks, "itemStyle": {"color": "#ef4444"}},
                {"value": passed, "itemStyle": {"color": "#22c55e"}},
                {"value": errors, "itemStyle": {"color": "#f97316"}},
                {"value": not_eval, "itemStyle": {"color": "#94a3b8"}},
            ]
            dist_chart.update()

            # Risk legend
            risk_legend.clear()
            with risk_legend:
                for leg_label, val, leg_color in [
                    ("Jailbreaks", jailbreaks, "negative"),
                    ("Passed / Safe", passed, "positive"),
                    ("Errors", errors, "warning"),
                    ("Pending", not_eval, "grey-6"),
                ]:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("circle", color=leg_color).classes("text-xs shrink-0")
                        ui.label(leg_label).classes("text-grey-6 text-sm flex-1")
                        ui.label(str(val)).classes("font-semibold tabular-nums text-sm")
                ui.label(f"{total_results} total results").classes(
                    "text-xs text-grey-5 mt-1"
                )

            # Recent runs table
            recent_p = backend.list_runs(page=1, page_size=5)
            rows = []
            for run in recent_p.items:
                d = _serialize(run)
                rp = backend.list_results(run_id=run.id, page=1, page_size=500)
                d["total_results"] = rp.total
                d["successful_jailbreaks"] = sum(
                    1
                    for r in rp.items
                    if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
                )
                d["_rel"] = _rel_time(d.get("created_at"))
                rows.append(d)
            recent_runs_table.rows.clear()
            recent_runs_table.rows.extend(rows)
            recent_runs_table.update()

        async def _load_agents() -> None:
            result = backend.list_agents(page=1, page_size=100)
            rows = []
            for a in result.items:
                d = _serialize(a)
                d["_rel"] = _rel_time(d.get("created_at"))
                rows.append(d)
            agents_table.rows.clear()
            agents_table.rows.extend(rows)
            agents_table.update()

        async def _load_attacks() -> None:
            result = backend.list_attacks(page=1, page_size=100)
            rows = []
            for a in result.items:
                d = _serialize(a)
                d["_rel"] = _rel_time(d.get("created_at"))
                rows.append(d)
            attacks_table.rows.clear()
            attacks_table.rows.extend(rows)
            attacks_table.update()

        async def _load_runs() -> None:
            result = backend.list_runs(page=1, page_size=50)
            rows = []
            for run in result.items:
                d = _serialize(run)
                rp = backend.list_results(run_id=run.id, page=1, page_size=500)
                d["total_results"] = rp.total
                d["successful_jailbreaks"] = sum(
                    1
                    for r in rp.items
                    if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
                )
                d["_rel"] = _rel_time(d.get("created_at"))
                rows.append(d)
            runs_table.rows.clear()
            runs_table.rows.extend(rows)
            runs_table.update()
            runs_count_label.text = (
                f"{result.total} run{'s' if result.total != 1 else ''} total"
            )

        async def _open_run_results(run: dict) -> None:
            run_dialog_title.text = f"Results — Run {run['id'][:8]}…"
            results_table.rows.clear()
            results_table.update()
            run_dialog.open()
            try:
                rp = backend.list_results(run_id=UUID(run["id"]), page=1, page_size=200)
                for r in rp.items:
                    d = _serialize(r)
                    d["_rel"] = _rel_time(d.get("created_at"))
                    results_table.rows.append(d)
                results_table.update()
            except Exception as exc:
                ui.notify(f"Error loading results: {exc}", type="negative")

        # ── Initial render ────────────────────────────────────────────────────
        _highlight_nav("dashboard")
        await _load_dashboard()

    return _DashboardApp()
