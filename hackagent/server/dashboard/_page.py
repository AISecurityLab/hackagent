# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DashboardPage — all NiceGUI UI layout and data-loading logic."""

from __future__ import annotations

import contextlib
import json
from uuid import UUID

from nicegui import app as _fastapi_app
from nicegui import ui

from ._components import EVAL_COLOR_JS, EVAL_LABEL_JS, make_run_table
from ._helpers import (
    _eval_color,
    _eval_label,
    _rel_time,
    _serialize,
    _step_color,
)

_VIEW_LABELS = {
    "dashboard": "Dashboard",
    "agents": "Agents",
    "attacks": "Attacks",
    "runs": "History",
}


class DashboardPage:
    """Owns all NiceGUI widgets for a single dashboard page request.

    A new instance is created inside the ``@ui.page("/")`` handler for every
    browser connection, so each user gets independent widget state.
    """

    def __init__(self, backend) -> None:
        self.backend = backend

        # Dark mode
        self.dark: ui.dark_mode | None = None
        self.dark_btn: ui.button | None = None

        # Navigation state
        self.current_view: dict[str, str] = {"value": "dashboard"}
        self.nav_buttons: dict[str, ui.button] = {}
        self.all_panels: dict[str, ui.column] = {}
        self.page_title: ui.label | None = None
        self.loading_spinner: ui.spinner | None = None

        # Right drawer — result detail
        self.right_drawer: ui.right_drawer | None = None
        self.result_area: ui.scroll_area | None = None
        self.result_detail_title: ui.label | None = None

        # Dashboard panel widgets
        self.stat_labels: dict[str, ui.label] = {}
        self.risk_chart: ui.echart | None = None
        self.dist_chart: ui.echart | None = None
        self.risk_legend: ui.column | None = None
        self.recent_runs_table: ui.table | None = None

        # Agents / Attacks / Runs panel widgets
        self.agents_table: ui.table | None = None
        self.attacks_table: ui.table | None = None
        self.runs_table: ui.table | None = None
        self.runs_count_label: ui.label | None = None

        # Run results dialog
        self.run_dialog: ui.dialog | None = None
        self.run_dialog_title: ui.label | None = None
        self.results_table: ui.table | None = None

    # ── Public entry point ────────────────────────────────────────────────────

    async def build(self) -> None:  # noqa: C901
        """Render the full page. Called from the ``@ui.page("/")`` handler."""
        self.dark = ui.dark_mode()
        if _fastapi_app.storage.browser.get("hackagent_dark"):
            self.dark.enable()

        self._build_right_drawer()
        sidebar = self._build_sidebar()
        self._build_header(sidebar)
        self._build_panels()
        self._build_run_dialog()

        self._highlight_nav("dashboard")
        await self._load_dashboard()

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_right_drawer(self) -> None:
        with ui.right_drawer(fixed=True, bordered=True, elevated=True).props(
            "width=520 overlay behavior=desktop"
        ) as drawer:
            drawer.hide()
            with ui.column().classes("w-full h-full gap-0"):
                with ui.row().classes(
                    "items-center justify-between w-full shrink-0 px-5 py-3 border-b"
                ):
                    self.result_detail_title = ui.label("Result Detail").classes(
                        "font-semibold text-base"
                    )
                    ui.button(icon="close", on_click=drawer.hide).props(
                        "flat round dense"
                    )
                self.result_area = ui.scroll_area().classes("flex-1 w-full")
        self.right_drawer = drawer

    def _build_sidebar(self) -> ui.left_drawer:
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
            for view_id, label, icon_name in nav_items:
                btn = (
                    ui.button(
                        label,
                        icon=icon_name,
                        on_click=lambda v=view_id: self.navigate(v),
                    )
                    .props("flat align=left no-caps")
                    .classes("w-full justify-start px-3 rounded-lg")
                )
                self.nav_buttons[view_id] = btn

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
                    is_remote = self.backend.get_api_key() is not None
                    mode_dot.classes(
                        add="text-info" if is_remote else "text-positive",
                        remove="text-positive text-info",
                    )
                    mode_lbl.text = "remote mode" if is_remote else "local mode"

            ui.timer(0.1, _load_mode, once=True)
        return sidebar

    def _build_header(self, sidebar: ui.left_drawer) -> None:
        with ui.header(elevated=True).classes(
            "items-center justify-between px-4 py-2 bg-primary"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="menu", on_click=sidebar.toggle).props(
                    "flat round dense color=white"
                )
                self.page_title = ui.label("Dashboard").classes(
                    "text-white font-semibold text-lg"
                )
            with ui.row().classes("items-center gap-1"):
                self.loading_spinner = ui.spinner("dots", size="1.2em", color="white")
                self.loading_spinner.set_visibility(False)
                self.dark_btn = ui.button(
                    icon="dark_mode" if not self.dark.value else "light_mode",
                    on_click=self._toggle_dark,
                ).props("flat round dense color=white")
                ui.button(
                    icon="refresh",
                    on_click=lambda: ui.timer(0, self.refresh_view, once=True),
                ).props("flat round dense color=white")

    def _build_panels(self) -> None:
        with ui.column().classes("w-full p-5 gap-6"):
            dashboard_panel = ui.column().classes("w-full gap-6")
            agents_panel = ui.column().classes("w-full gap-4")
            attacks_panel = ui.column().classes("w-full gap-4")
            runs_panel = ui.column().classes("w-full gap-4")

            self.all_panels = {
                "dashboard": dashboard_panel,
                "agents": agents_panel,
                "attacks": attacks_panel,
                "runs": runs_panel,
            }
            for panel in self.all_panels.values():
                panel.set_visibility(False)
            dashboard_panel.set_visibility(True)

            self._build_dashboard_panel(dashboard_panel)
            self._build_agents_panel(agents_panel)
            self._build_attacks_panel(attacks_panel)
            self._build_runs_panel(runs_panel)

    def _build_dashboard_panel(self, panel: ui.column) -> None:
        with panel:
            # Stat cards
            with ui.row().classes("w-full flex-wrap gap-4"):
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
                        self.stat_labels[s_key] = ui.label("—").classes(
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
                        self.risk_chart = ui.echart(
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
                        self.risk_legend = ui.column().classes("gap-2 flex-1")

                with ui.card().classes("flex-1 min-w-72"):
                    ui.label("Result Distribution").classes("font-semibold text-sm")
                    ui.label("Evaluation outcomes across all runs").classes(
                        "text-xs text-grey-6 mb-4"
                    )
                    self.dist_chart = ui.echart(
                        {
                            "xAxis": {
                                "type": "category",
                                "data": ["Jailbreaks", "Passed", "Errors", "Pending"],
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
                        "View all →", on_click=lambda: self.navigate("runs")
                    ).props("flat dense").classes("text-xs text-grey-6")
                self.recent_runs_table = make_run_table(
                    on_row_click=lambda run: ui.timer(
                        0, lambda r=run: self._open_run_results(r), once=True
                    )
                )

    def _build_agents_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes("w-full"):
                self.agents_table = ui.table(
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
                self.agents_table.add_slot(
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
                self.agents_table.add_slot(
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
                self.agents_table.add_slot(
                    "body-cell-created_at",
                    r"""
                    <q-td :props="props">
                      <span class="text-xs text-grey-6">{{ props.row._rel }}</span>
                    </q-td>
                    """,
                )

    def _build_attacks_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes("w-full"):
                self.attacks_table = ui.table(
                    columns=[
                        {"name": "id", "label": "ID", "field": "id", "align": "left"},
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
                self.attacks_table.add_slot(
                    "body-cell-id",
                    r"<q-td :props='props'>"
                    r"<span class='font-mono text-xs'>{{ props.row.id.slice(0,8) }}…</span>"
                    r"</q-td>",
                )
                self.attacks_table.add_slot(
                    "body-cell-type",
                    r"<q-td :props='props'>"
                    r"<q-badge color='orange' :label='props.row.type' />"
                    r"</q-td>",
                )
                self.attacks_table.add_slot(
                    "body-cell-agent_id",
                    r"<q-td :props='props'>"
                    r"<span class='font-mono text-xs'>{{ props.row.agent_id.slice(0,8) }}…</span>"
                    r"</q-td>",
                )
                self.attacks_table.add_slot(
                    "body-cell-created_at",
                    r"<q-td :props='props'>"
                    r"<span class='text-xs text-grey-6'>{{ props.row._rel }}</span>"
                    r"</q-td>",
                )

    def _build_runs_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center justify-between mb-1 px-2"):
                    self.runs_count_label = ui.label("").classes("text-sm text-grey-6")
                self.runs_table = make_run_table(
                    on_row_click=lambda run: ui.timer(
                        0, lambda r=run: self._open_run_results(r), once=True
                    ),
                    pagination={"rowsPerPage": 25},
                )

    def _build_run_dialog(self) -> None:
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-5xl h-[80vh] flex flex-col gap-4"):
                with ui.row().classes("items-center justify-between w-full shrink-0"):
                    self.run_dialog_title = ui.label("Run Results").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                self.results_table = ui.table(
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

                self.results_table.add_slot(
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
                self.results_table.add_slot(
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
                self.results_table.add_slot(
                    "body-cell-eval",
                    f"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                      <q-badge :color="{EVAL_COLOR_JS}"
                               :label="{EVAL_LABEL_JS}" />
                    </q-td>
                    """,
                )
                self.results_table.add_slot(
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
                self.results_table.on(
                    "rowClick",
                    lambda e: ui.timer(
                        0,
                        lambda args=e.args: self.show_result_detail(args),
                        once=True,
                    ),
                )
        self.run_dialog = dialog

    def _extract_run_asr_display(self, run, run_results) -> str:
        """Return ASR string for a run, preferring synced evaluation_summary."""
        run_cfg = getattr(run, "run_config", None)
        if isinstance(run_cfg, dict):
            summary = run_cfg.get("evaluation_summary")
            if isinstance(summary, dict):
                try:
                    return (
                        f"{float(summary.get('overall_success_rate', 0.0)) * 100:.1f}%"
                    )
                except (TypeError, ValueError):
                    pass

        total = len(run_results)
        if total <= 0:
            return "—"

        jailbreaks = sum(
            1
            for r in run_results
            if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
        )
        return f"{(jailbreaks / total) * 100:.1f}%"

    # ── Dark mode ─────────────────────────────────────────────────────────────

    def _toggle_dark(self) -> None:
        self.dark.toggle()
        _fastapi_app.storage.browser["hackagent_dark"] = self.dark.value
        self.dark_btn.props(f"icon={'light_mode' if self.dark.value else 'dark_mode'}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _highlight_nav(self, view: str) -> None:
        for v, btn in self.nav_buttons.items():
            if v == view:
                btn.props(remove="flat").props(add="unelevated color=primary")
            else:
                btn.props(remove="unelevated color=primary", add="flat")

    def navigate(self, view: str) -> None:
        self.current_view["value"] = view
        for v, panel in self.all_panels.items():
            panel.set_visibility(v == view)
        self.page_title.text = _VIEW_LABELS.get(view, "Dashboard")
        self._highlight_nav(view)
        ui.timer(0, self.refresh_view, once=True)

    async def refresh_view(self) -> None:
        _v = self.current_view["value"]
        self.loading_spinner.set_visibility(True)
        try:
            if _v == "dashboard":
                await self._load_dashboard()
            elif _v == "agents":
                await self._load_agents()
            elif _v == "attacks":
                await self._load_attacks()
            elif _v == "runs":
                await self._load_runs()
        except Exception as exc:
            ui.notify(f"Failed to load data: {exc}", type="negative")
        finally:
            self.loading_spinner.set_visibility(False)

    # ── Result detail (right drawer) ──────────────────────────────────────────

    async def show_result_detail(self, result: dict) -> None:
        """Populate the right drawer with result + traces and open it."""
        self.result_area.clear()
        eval_status = result.get("evaluation_status", "")
        s = eval_status.upper()

        with self.result_area:
            with ui.column().classes("w-full gap-4 p-5"):
                ui.label(result.get("id", "")).classes(
                    "font-mono text-xs text-grey-6 select-all"
                )
                self.result_detail_title.text = (
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
                    ui.label(result.get("goal", "—")).classes("text-sm leading-relaxed")

                with ui.row().classes("items-center justify-between"):
                    ui.badge(
                        _eval_label(eval_status),
                        color=_eval_color(eval_status),
                    ).classes("text-xs px-2 py-0.5")
                    ui.label(f"Goal #{(result.get('goal_index', 0) or 0) + 1}").classes(
                        "text-xs text-grey-6"
                    )

                # Metrics
                metrics = result.get("evaluation_metrics")
                if metrics and isinstance(metrics, dict) and metrics:
                    with ui.column().classes("gap-1"):
                        ui.label("METRICS").classes(
                            "text-[10px] font-semibold tracking-widest "
                            "text-grey-5 uppercase"
                        )
                        ui.code(json.dumps(metrics, indent=2), language="json").classes(
                            "w-full text-xs max-h-48"
                        )

                ui.separator()

                with ui.row().classes("items-center gap-2"):
                    ui.label("TRACE TIMELINE").classes(
                        "text-[10px] font-semibold tracking-widest "
                        "text-grey-5 uppercase"
                    )
                    trace_count_badge = ui.badge("…", color="grey-6").classes("text-xs")

                with ui.column().classes("w-full gap-0") as trace_container:
                    with ui.row().classes("items-center gap-2 py-4 justify-center"):
                        ui.spinner("dots")
                        ui.label("Loading traces…").classes("text-sm text-grey-6")

        self.right_drawer.show()

        # Load traces async
        try:
            traces_raw = self.backend.list_traces(result_id=UUID(result["id"]))
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
                            with ui.column().classes("items-center shrink-0 w-8 gap-0"):
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
                                    ui.label(_rel_time(td.get("created_at"))).classes(
                                        "text-xs text-grey-6"
                                    )
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

    # ── Data loaders ──────────────────────────────────────────────────────────

    async def _load_dashboard(self) -> None:
        agents_p = self.backend.list_agents(page=1, page_size=1)
        attacks_p = self.backend.list_attacks(page=1, page_size=1)
        runs_p = self.backend.list_runs(page=1, page_size=200)
        total_results = jailbreaks = passed = errors = not_eval = 0
        for run in runs_p.items:
            rp = self.backend.list_results(run_id=run.id, page=1, page_size=500)
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

        self.stat_labels["total_agents"].set_text(str(agents_p.total))
        self.stat_labels["total_attacks"].set_text(str(attacks_p.total))
        self.stat_labels["total_runs"].set_text(str(runs_p.total))
        self.stat_labels["successful_jailbreaks"].set_text(str(jailbreaks))

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
        self.risk_chart.update()

        # Distribution bar
        self.dist_chart.options["series"][0]["data"] = [
            {"value": jailbreaks, "itemStyle": {"color": "#ef4444"}},
            {"value": passed, "itemStyle": {"color": "#22c55e"}},
            {"value": errors, "itemStyle": {"color": "#f97316"}},
            {"value": not_eval, "itemStyle": {"color": "#94a3b8"}},
        ]
        self.dist_chart.update()

        # Risk legend
        self.risk_legend.clear()
        with self.risk_legend:
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
        recent_p = self.backend.list_runs(page=1, page_size=5)
        rows = []
        for run in recent_p.items:
            d = _serialize(run)
            rp = self.backend.list_results(run_id=run.id, page=1, page_size=500)
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
            )
            d["overall_asr"] = self._extract_run_asr_display(run, list(rp.items))
            d["_rel"] = _rel_time(d.get("created_at"))
            rows.append(d)
        self.recent_runs_table.rows.clear()
        self.recent_runs_table.rows.extend(rows)
        self.recent_runs_table.update()

    async def _load_agents(self) -> None:
        result = self.backend.list_agents(page=1, page_size=100)
        rows = []
        for a in result.items:
            d = _serialize(a)
            d["_rel"] = _rel_time(d.get("created_at"))
            rows.append(d)
        self.agents_table.rows.clear()
        self.agents_table.rows.extend(rows)
        self.agents_table.update()

    async def _load_attacks(self) -> None:
        result = self.backend.list_attacks(page=1, page_size=100)
        rows = []
        for a in result.items:
            d = _serialize(a)
            d["_rel"] = _rel_time(d.get("created_at"))
            rows.append(d)
        self.attacks_table.rows.clear()
        self.attacks_table.rows.extend(rows)
        self.attacks_table.update()

    async def _load_runs(self) -> None:
        result = self.backend.list_runs(page=1, page_size=50)
        rows = []
        for run in result.items:
            d = _serialize(run)
            rp = self.backend.list_results(run_id=run.id, page=1, page_size=500)
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
            )
            d["overall_asr"] = self._extract_run_asr_display(run, list(rp.items))
            d["_rel"] = _rel_time(d.get("created_at"))
            rows.append(d)
        self.runs_table.rows.clear()
        self.runs_table.rows.extend(rows)
        self.runs_table.update()
        self.runs_count_label.text = (
            f"{result.total} run{'s' if result.total != 1 else ''} total"
        )

    async def _open_run_results(self, run: dict) -> None:
        self.run_dialog_title.text = f"Results — Run {run['id'][:8]}…"
        self.results_table.rows.clear()
        self.results_table.update()
        self.run_dialog.open()
        try:
            rp = self.backend.list_results(
                run_id=UUID(run["id"]), page=1, page_size=200
            )
            for r in rp.items:
                d = _serialize(r)
                d["_rel"] = _rel_time(d.get("created_at"))
                self.results_table.rows.append(d)
            self.results_table.update()
        except Exception as exc:
            ui.notify(f"Error loading results: {exc}", type="negative")
