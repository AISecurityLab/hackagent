# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DashboardPage — all NiceGUI UI layout and data-loading logic."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
import html
import json
import math
import re
from uuid import UUID

from nicegui import app as _fastapi_app
from nicegui import ui

from hackagent.attacks.evaluator.metrics import (
    calculate_fleiss_kappa,
    calculate_majority_vote_asr,
    calculate_per_judge_strictness,
)

from ._components import make_run_table
from ._helpers import (
    _duration_seconds,
    _eval_color,
    _eval_label,
    _format_latency,
    _rel_time,
    _serialize,
    _result_bucket,
    _short_date,
)

_VIEW_LABELS = {
    "dashboard": "Dashboard",
    "agents": "Targets",
    "runs": "History",
    "reports": "Reports",
}

_RESULTS_FETCH_LIMIT = 20
_DASHBOARD_RUN_SCAN_LIMIT = 10
_RUNS_VIEW_PAGE_SIZE = 15


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

        # Foreground modal — result detail from goal list
        self.result_modal_dialog: ui.dialog | None = None
        self.result_modal_area: ui.scroll_area | None = None
        self.result_modal_title: ui.label | None = None

        # Dashboard panel widgets
        self.stat_labels: dict[str, ui.label] = {}
        self.risk_chart: ui.echart | None = None
        self.dist_chart: ui.echart | None = None
        self.risk_legend: ui.column | None = None
        self.latest_target_stats_label: ui.label | None = None
        self.latest_target_agent_label: ui.label | None = None
        self.recent_runs_table: ui.table | None = None

        # Agents / History panel widgets
        self.agents_table: ui.table | None = None
        self.runs_table: ui.table | None = None
        self.runs_count_label: ui.label | None = None
        self.runs_page_label: ui.label | None = None
        self.runs_current_page: int = 1
        self.runs_total_pages: int = 1
        self.history_reports_list_area: ui.column | None = None
        self.history_reports_summary_labels: dict[str, ui.label] = {}
        self.history_reports_count_label: ui.label | None = None

        # Reports panel (side-by-side list + detail)
        self._reports_left_col: ui.column | None = None
        self._reports_detail_panel: ui.column | None = None
        self._reports_detail_title: ui.label | None = None
        self._reports_detail_visible: bool = False
        self._report_results_left_col: ui.column | None = None
        self._report_goal_detail_panel: ui.column | None = None
        self._report_current_run: dict | None = None
        self._report_current_run_results: list[dict] = []

        # Run results dialog (report view)
        self.run_dialog: ui.dialog | None = None
        self.run_dialog_title: ui.label | None = None
        self.run_report_area: ui.column | None = None

        # History run dialog (two-panel popup)
        self.history_run_dialog: ui.dialog | None = None
        self.history_run_dialog_title: ui.label | None = None
        self.history_run_dialog_subtitle: ui.label | None = None
        self.history_run_config_area: ui.column | None = None
        self.history_results_list_area: ui.column | None = None
        self.history_results_empty_label: ui.label | None = None
        self.metrics_area: ui.column | None = None
        self.history_detail_area: ui.column | None = None
        self._history_dialog_attack_str: str = ""

        # New side-by-side History layout
        self._history_runs_area: ui.column | None = None
        self._history_expanded_run_id: str | None = None
        self._history_expanded_goals_area: ui.column | None = None
        self._history_current_run: dict | None = None
        self._history_current_run_results: list[dict] = []
        self._history_visible_run_ids: list[str] = []

        # Attack detail dialog
        self.attack_dialog: ui.dialog | None = None
        self.attack_dialog_title: ui.label | None = None
        self.attack_config_area: ui.column | None = None
        self.attack_runs_table: ui.table | None = None

        # Selection state for bulk operations
        self._selected_run_ids: list[str] = []
        self._selected_attack_ids: list[str] = []
        self._runs_delete_btn: ui.button | None = None
        self._attacks_delete_btn: ui.button | None = None

    # ── Public entry point ────────────────────────────────────────────────────

    async def build(self) -> None:  # noqa: C901
        """Render the full page. Called from the ``@ui.page("/")`` handler."""
        self.dark = ui.dark_mode()
        if _fastapi_app.storage.browser.get("hackagent_dark"):
            self.dark.enable()

        self._build_result_modal_dialog()
        sidebar = self._build_sidebar()
        self._build_header(sidebar)
        self._build_panels()
        self._build_run_dialog()
        self._build_history_run_dialog()
        self._build_attack_dialog()

        self._highlight_nav("dashboard")
        # Defer heavy data loading so the page skeleton renders first
        # and the browser WebSocket is established before backend I/O.
        ui.timer(0.1, self._load_dashboard, once=True)

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

    def _build_result_modal_dialog(self) -> None:
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-5xl h-[80vh] flex flex-col gap-0"):
                with ui.row().classes(
                    "items-center justify-between w-full shrink-0 px-5 py-3 border-b"
                ):
                    with ui.row().classes("items-center gap-3"):
                        ui.button("← Back to goals", on_click=dialog.close).props(
                            "flat dense no-caps"
                        )
                        self.result_modal_title = ui.label("Goal Detail").classes(
                            "font-semibold text-base"
                        )
                    ui.button(icon="close", on_click=dialog.close).props(
                        "flat round dense"
                    )
                self.result_modal_area = ui.scroll_area().classes("flex-1 w-full")
        self.result_modal_dialog = dialog

    def _build_sidebar(self) -> ui.left_drawer:
        with ui.left_drawer(top_corner=True, bottom_corner=True, value=True).props(
            "width=220 bordered"
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
                ("agents", "Targets", "smart_toy"),
                ("runs", "History", "assignment"),
                ("reports", "Reports", "assessment"),
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
                ui.icon("circle", size="xs").classes("text-positive text-xs")
                ui.label("local mode").classes("text-xs text-grey-6")
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
            runs_panel = ui.column().classes("w-full gap-4")
            reports_panel = ui.column().classes("w-full gap-4")

            self.all_panels = {
                "dashboard": dashboard_panel,
                "agents": agents_panel,
                "runs": runs_panel,
                "reports": reports_panel,
            }
            for panel in self.all_panels.values():
                panel.set_visibility(False)
            dashboard_panel.set_visibility(True)

            self._build_dashboard_panel(dashboard_panel)
            self._build_agents_panel(agents_panel)
            self._build_runs_panel(runs_panel)
            self._build_reports_panel(reports_panel)

    def _build_dashboard_panel(self, panel: ui.column) -> None:
        with panel:
            # Stat cards
            with ui.row().classes("w-full flex-wrap gap-4"):
                for s_label, s_key, s_icon, s_color in [
                    ("Targets", "total_agents", "smart_toy", "blue"),
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

            # Charts (single container: label on top, pie left, bar right)
            with ui.card().classes("w-full"):
                self.latest_target_stats_label = ui.label(
                    "Latest Target Statistics"
                ).classes("text-lg font-bold text-grey-8")
                with ui.row().classes(
                    "items-center gap-2 mt-2 w-fit px-3 py-2 rounded-md bg-grey-1 border border-grey-3"
                ):
                    ui.icon("smart_toy", color="grey-5").classes("text-base")
                    with ui.row().classes("items-baseline gap-2"):
                        ui.label("Agent:").classes("text-sm text-grey-6 font-semibold")
                        self.latest_target_agent_label = ui.label("N/A").classes(
                            "font-mono text-sm"
                        )

                with ui.row().classes("w-full flex-wrap gap-6 items-start mt-4"):
                    with ui.column().classes("flex-1 min-w-72"):
                        ui.label("Run Overview").classes("font-semibold text-sm")
                        ui.label(
                            "Evaluation outcomes for the latest tested target"
                        ).classes("text-xs text-grey-6 mb-4")
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

                    with ui.column().classes("flex-1 min-w-72"):
                        ui.label("Result Distribution").classes("font-semibold text-sm")
                        ui.label(
                            "Evaluation outcomes for the latest tested target"
                        ).classes("text-xs text-grey-6 mb-4")
                        self.dist_chart = ui.echart(
                            {
                                "xAxis": {
                                    "type": "category",
                                    "data": [
                                        "Jailbreaks",
                                        "Mitigated",
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
                        "View all →", on_click=lambda: self.navigate("runs")
                    ).props("flat dense").classes("text-xs text-grey-6")
                self.recent_runs_table = make_run_table(
                    on_row_click=lambda run: ui.timer(
                        0,
                        lambda r=run: asyncio.create_task(
                            self._open_run_history_results(r)
                        ),
                        once=True,
                    ),
                    include_agent=True,
                    include_progressive_run=True,
                    include_results=False,
                    include_goal_latency_avg=True,
                    include_asr=True,
                )

    def _build_agents_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes("w-full"):
                self.agents_table = ui.table(
                    columns=[
                        {
                            "name": "name",
                            "label": "Target",
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
                            "name": "avg_risk_pct",
                            "label": "Avg Risk %",
                            "field": "avg_risk_pct",
                            "align": "left",
                            "sortable": True,
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
                    "body-cell-avg_risk_pct",
                    r"""
                    <q-td :props="props">
                      <q-badge
                        :color="props.row.avg_risk_pct >= 70 ? 'negative' : (props.row.avg_risk_pct >= 40 ? 'warning' : 'positive')"
                        :label="props.row._avg_risk_pct || '0.0%'" />
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
                self.agents_table.add_slot(
                    "no-data",
                    r"""
                    <div class="q-pa-md text-grey-6 text-sm">
                      No targets with runs yet.
                    </div>
                    """,
                )

    def _build_attacks_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center justify-between mb-1 px-2"):
                    ui.label("").classes("text-sm text-grey-6")  # spacer
                    self._attacks_delete_btn = (
                        ui.button(
                            "Delete selected",
                            icon="delete",
                            on_click=lambda: ui.timer(
                                0, self._delete_selected_attacks, once=True
                            ),
                        )
                        .props("flat dense no-caps color=negative")
                        .classes("hidden")
                    )
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
                            "name": "agent_name",
                            "label": "Agent",
                            "field": "agent_name",
                            "align": "left",
                        },
                        {
                            "name": "created_at",
                            "label": "Timestamp",
                            "field": "created_at",
                            "align": "left",
                        },
                    ],
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 25},
                    selection="multiple",
                ).classes("w-full")
                self.attacks_table.add_slot(
                    "body-cell-id",
                    r"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                      <span class="font-mono text-xs">{{ props.row.id.slice(0,8) }}…</span>
                    </q-td>
                    """,
                )
                self.attacks_table.add_slot(
                    "body-cell-type",
                    r"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                      <q-badge color="orange" :label="props.row.type" />
                    </q-td>
                    """,
                )
                self.attacks_table.add_slot(
                    "body-cell-agent_name",
                    r"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                                            <span class="text-sm">{{ props.row.agent_name || '—' }}</span>
                    </q-td>
                    """,
                )
                self.attacks_table.add_slot(
                    "body-cell-created_at",
                    r"""
                    <q-td :props="props" class="cursor-pointer"
                          @click="$emit('rowClick', props.row)">
                                            <div class="text-sm">{{ props.row._rel }}</div>
                                            <div class="text-xs text-grey-6">{{ props.row._date || '—' }}</div>
                    </q-td>
                    """,
                )

                def _on_attack_row_click(e) -> None:
                    row = self._extract_row(e.args)
                    if row is not None:
                        ui.timer(
                            0,
                            lambda r=row: self._open_attack_detail(r),
                            once=True,
                        )

                self.attacks_table.on("rowClick", _on_attack_row_click)

                def _on_attack_select(e) -> None:
                    self._selected_attack_ids = [
                        row["id"] for row in (self.attacks_table.selected or [])
                    ]
                    if self._attacks_delete_btn is not None:
                        if self._selected_attack_ids:
                            self._attacks_delete_btn.classes(remove="hidden")
                        else:
                            self._attacks_delete_btn.classes(add="hidden")

                self.attacks_table.on("selection", _on_attack_select)

    def _build_runs_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes(
                "w-full h-[calc(100vh-220px)] min-h-[540px] overflow-hidden"
            ):
                with ui.column().classes("w-full h-full min-h-0 gap-2"):
                    with ui.row().classes("items-center justify-between mb-1 px-2"):
                        self.runs_count_label = ui.label("").classes(
                            "text-sm text-grey-6"
                        )
                        with ui.row().classes("items-center gap-2"):
                            self._runs_delete_btn = (
                                ui.button(
                                    "Delete selected",
                                    icon="delete",
                                    on_click=lambda: ui.timer(
                                        0,
                                        self._delete_selected_runs,
                                        once=True,
                                    ),
                                )
                                .props("flat dense no-caps color=negative")
                                .classes("hidden")
                            )
                            ui.button(
                                "← Prev",
                                on_click=lambda: self._change_runs_page(-1),
                            ).props("flat dense no-caps")
                            self.runs_page_label = ui.label("Page 1 / 1").classes(
                                "text-sm text-grey-6"
                            )
                            ui.button(
                                "Next →",
                                on_click=lambda: self._change_runs_page(1),
                            ).props("flat dense no-caps")
                    with ui.scroll_area().classes("w-full flex-1 min-h-0"):
                        self._history_runs_area = ui.column().classes(
                            "w-full gap-0 overflow-x-auto"
                        )

    def _build_reports_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes(
                "w-full h-[calc(100vh-220px)] min-h-[540px] overflow-hidden"
            ):
                with ui.row().classes(
                    "w-full h-full gap-0 items-stretch overflow-hidden"
                ):
                    self._reports_left_col = ui.column().classes(
                        "w-full h-full min-h-0 gap-4 transition-all duration-300"
                    )
                    with self._reports_left_col:
                        with ui.row().classes("w-full flex-wrap gap-4"):
                            for label, key, icon, color in [
                                ("Total Reports", "reports", "description", "blue"),
                                ("Total Tests", "tests", "pulse", "purple"),
                                ("Vulnerabilities", "vulns", "warning", "negative"),
                                ("Avg Risk Score", "risk", "trending_up", "orange"),
                            ]:
                                with ui.card().classes("flex-1 min-w-36"):
                                    with ui.row().classes(
                                        "items-center justify-between mb-2"
                                    ):
                                        ui.label(label).classes("text-sm text-grey-6")
                                        ui.icon(icon, color=color).classes("text-xl")
                                    self.history_reports_summary_labels[key] = ui.label(
                                        "—"
                                    ).classes("text-3xl font-bold")

                        self.history_reports_count_label = ui.label(
                            "Loading reports..."
                        ).classes("text-sm text-grey-6 px-1")
                        with ui.scroll_area().classes("w-full flex-1 min-h-0"):
                            self.history_reports_list_area = ui.column().classes(
                                "w-full gap-2"
                            )

                    self._reports_detail_panel = (
                        ui.column()
                        .classes("h-full min-h-0 gap-0 border-l shrink-0")
                        .style(
                            "width: 0; min-width: 0; overflow: hidden; "
                            "transition: all 0.3s ease;"
                        )
                    )

    def _build_run_dialog(self) -> None:
        with ui.dialog().props("maximized") as dialog:
            with ui.card().classes("w-full h-full flex flex-col gap-0"):
                with ui.row().classes(
                    "items-center justify-between w-full shrink-0 px-5 py-3 border-b"
                ):
                    self.run_dialog_title = ui.label("Report").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props(
                        "flat round dense"
                    )
                with ui.scroll_area().classes("w-full flex-1"):
                    self.run_report_area = ui.column().classes(
                        "w-full gap-5 p-5 max-w-6xl mx-auto"
                    )
        self.run_dialog = dialog

    def _build_history_run_dialog(self) -> None:
        """Build a two-panel dialog for History run results."""
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-[96vw] h-[90vh] flex flex-col gap-0"):
                with ui.row().classes(
                    "items-center justify-between w-full shrink-0 px-5 py-3 border-b"
                ):
                    self.history_run_dialog_title = ui.label("Run Results").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props(
                        "flat round dense"
                    )
                # Two-panel body
                with ui.row().classes("w-full flex-1 gap-0 overflow-hidden"):
                    # Left: config/metrics + compact card list
                    with (
                        ui.scroll_area()
                        .classes("h-full border-r")
                        .style("flex:none;width:680px")
                    ):
                        with ui.column().classes("w-full gap-3 p-4"):
                            self.history_run_config_area = ui.column().classes(
                                "w-full gap-2"
                            )
                            ui.separator()
                            self.metrics_area = ui.column().classes("w-full gap-2")
                            ui.separator()
                            self.history_results_empty_label = ui.label(
                                "Loading results..."
                            ).classes("text-sm text-grey-8 py-2")
                            self.history_results_list_area = ui.column().classes(
                                "w-full gap-1"
                            )
                    # Right: detail view
                    with ui.scroll_area().classes("h-full flex-1"):
                        self.history_detail_area = ui.column().classes(
                            "w-full gap-3 p-6"
                        )
                        with self.history_detail_area:
                            ui.label("← Select a goal to view details").classes(
                                "text-grey-4 text-sm italic mt-16 w-full text-center"
                            )
        self.history_run_dialog = dialog

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

    def _render_result_tab(self, row: dict) -> None:
        """Render the Result tab content for a goal detail."""
        eval_status = row.get("evaluation_status", "")
        eval_notes = row.get("evaluation_notes")
        bucket = _result_bucket(eval_status, eval_notes)

        # Evaluation banner
        if bucket == "jailbreak":
            with (
                ui.card()
                .tight()
                .classes(
                    "w-full border border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/30"
                )
            ):
                with ui.row().classes("gap-3 items-center p-4"):
                    ui.icon("lock_open", color="negative").classes("text-2xl")
                    with ui.column().classes("gap-0.5"):
                        ui.label("Jailbreak Successful").classes(
                            "font-semibold text-negative text-sm"
                        )
                    evaluator = ""
                    if isinstance(row.get("evaluation_metrics"), dict):
                        evaluator = str(row["evaluation_metrics"].get("evaluator", ""))
                    if not evaluator and isinstance(row.get("metadata"), dict):
                        evaluator = str(row["metadata"].get("evaluator", ""))
                    if evaluator:
                        ui.label(evaluator).classes(
                            "ml-2 text-xs text-grey-6 font-mono"
                        )
        elif bucket == "mitigated":
            with (
                ui.card()
                .tight()
                .classes(
                    "w-full border border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/30"
                )
            ):
                with ui.row().classes("gap-3 items-center p-4"):
                    ui.icon("security", color="positive").classes("text-2xl")
                    with ui.column().classes("gap-0.5"):
                        ui.label("Model resisted").classes(
                            "font-semibold text-positive text-sm"
                        )
                    evaluator = ""
                    if isinstance(row.get("evaluation_metrics"), dict):
                        evaluator = str(row["evaluation_metrics"].get("evaluator", ""))
                    if not evaluator and isinstance(row.get("metadata"), dict):
                        evaluator = str(row["metadata"].get("evaluator", ""))
                    if evaluator:
                        ui.label(evaluator).classes(
                            "ml-2 text-xs text-grey-6 font-mono"
                        )
        elif bucket == "failed":
            with (
                ui.card()
                .tight()
                .classes(
                    "w-full border border-orange-300 bg-orange-50 dark:border-orange-700 dark:bg-orange-900/30"
                )
            ):
                with ui.row().classes("gap-3 items-center p-4"):
                    ui.icon("warning_amber", color="warning").classes("text-2xl")
                    ui.label("Evaluation Error").classes(
                        "font-semibold text-warning text-sm"
                    )

        # Summary cards row
        with ui.row().classes("w-full flex-wrap gap-3"):
            latency = row.get("_goal_latency", "—")
            with ui.card().tight().classes("min-w-32"):
                with ui.column().classes("px-3 py-2 gap-0"):
                    ui.label("LATENCY").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                    )
                    ui.label(str(latency)).classes("text-sm font-medium")
            with ui.card().tight().classes("min-w-32"):
                with ui.column().classes("px-3 py-2 gap-0"):
                    ui.label("HTTP STATUS").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                    )
                    http_status = "—"
                    if isinstance(row.get("metadata"), dict):
                        http_status = str(
                            row["metadata"].get("http_status")
                            or row["metadata"].get("status_code")
                            or "—"
                        )
                    ui.label(http_status).classes("text-sm font-medium")
            with ui.card().tight().classes("flex-1 min-w-48"):
                with ui.column().classes("px-3 py-2 gap-0"):
                    ui.label("GOAL").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                    )
                    ui.label(str(row.get("goal") or "—")).classes(
                        "text-sm font-medium whitespace-normal break-words leading-snug"
                    ).style("overflow-wrap:anywhere;")

        # Evaluation Notes
        notes = str(row.get("evaluation_notes") or "—")
        with ui.column().classes("w-full gap-1"):
            ui.label("Evaluation Notes").classes(
                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
            )
            ui.label(notes).classes("text-sm")

        # MML-specific rendering: Image + Prompt + Response
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        encoding_mode = metadata.get("encoding_mode")
        if encoding_mode:
            self._render_mml_result_section(row, metadata)

        # Key-value detail table
        detail_fields = self._build_result_detail_fields(row)
        if detail_fields:
            with ui.column().classes("w-full gap-0"):
                for k, v in detail_fields:
                    with ui.row().classes(
                        "w-full items-start gap-4 py-2 border-b border-grey-2"
                    ):
                        ui.label(f"{k}:").classes(
                            "text-sm text-grey-6 font-medium min-w-32"
                        )
                        ui.label(str(v)).classes("text-sm")

    @staticmethod
    def _build_result_detail_fields(row: dict) -> list[tuple[str, str]]:
        """Build key-value pairs for the Result tab detail table."""
        fields = []
        metrics = (
            row.get("evaluation_metrics")
            if isinstance(row.get("evaluation_metrics"), dict)
            else {}
        )
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}

        # Combine metrics + metadata for display
        combined: dict[str, object] = {}
        # Skip large binary data fields from the detail table
        _skip_keys = {"image_data_url"}
        for src in (metadata, metrics):
            if isinstance(src, dict):
                for k, v in src.items():
                    if v not in (None, "", {}, []) and k not in _skip_keys:
                        combined[k] = v

        # Also add some top-level result fields
        for key in ("goal", "goal_index"):
            val = row.get(key)
            if val not in (None, ""):
                combined[key] = val

        for k, v in combined.items():
            display_val = v
            if isinstance(v, dict):
                display_val = json.dumps(v, indent=2, default=str)
            elif isinstance(v, list):
                display_val = json.dumps(v, default=str)
            fields.append((k, str(display_val)))
        return fields

    # ── MML: render multimodal result section ────────────────────────────────

    def _render_mml_result_section(self, row: dict, metadata: dict) -> None:
        """Render MML-specific result content: encoded image, prompt, response."""
        encoding_mode = metadata.get("encoding_mode", "unknown")
        image_data_url = metadata.get("image_data_url", "")
        text_prompt = (
            metadata.get("text_prompt") or metadata.get("jailbreak_prompt") or ""
        )
        response = metadata.get("jailbreak_response") or metadata.get("response") or ""

        with ui.column().classes("w-full gap-3"):
            # Section header
            with ui.row().classes("items-center gap-2"):
                ui.icon("image", color="primary").classes("text-lg")
                ui.label("MML Attack Details").classes("font-semibold text-sm")
                ui.badge(f"Mode: {encoding_mode}", color="purple").classes("text-xs")

            # Encoded image
            if image_data_url:
                with ui.card().tight().classes("w-full border border-grey-3"):
                    with ui.column().classes("p-3 gap-2"):
                        ui.label("ENCODED IMAGE").classes(
                            "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                        )
                        ui.html(
                            f'<img src="{image_data_url}" '
                            f'alt="MML encoded prompt ({encoding_mode})" '
                            f'style="max-width:100%;height:auto;border-radius:4px;'
                            f'border:1px solid var(--q-grey-3);" />'
                        ).classes("w-full")

            # Text prompt sent to the model
            if text_prompt:
                with (
                    ui.card()
                    .tight()
                    .classes(
                        "w-full border border-blue-200 bg-blue-50 dark:border-blue-700 dark:bg-blue-900/20"
                    )
                ):
                    with ui.column().classes("p-3 gap-1"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label("TEXT PROMPT").classes(
                                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                            )
                            ui.button(
                                icon="content_copy",
                            ).props("flat dense size=xs color=grey-6").tooltip(
                                "Copy to clipboard"
                            ).on(
                                "click",
                                js_handler=f"() => navigator.clipboard.writeText({json.dumps(text_prompt)})",
                            )
                        ui.label(text_prompt).classes(
                            "text-sm whitespace-pre-wrap break-words"
                        ).style("overflow-wrap:anywhere;")

            # Target model response
            if response:
                with (
                    ui.card()
                    .tight()
                    .classes(
                        "w-full border border-orange-200 bg-orange-50 dark:border-orange-700 dark:bg-orange-900/20"
                    )
                ):
                    with ui.column().classes("p-3 gap-1"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label("TARGET RESPONSE").classes(
                                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                            )
                            ui.button(
                                icon="content_copy",
                            ).props("flat dense size=xs color=grey-6").tooltip(
                                "Copy to clipboard"
                            ).on(
                                "click",
                                js_handler=f"() => navigator.clipboard.writeText({json.dumps(response)})",
                            )
                        ui.label(response).classes(
                            "text-sm whitespace-pre-wrap break-words"
                        ).style("overflow-wrap:anywhere;")

    # ── History: render Config tab ───────────────────────────────────────────

    def _render_config_tab(self, row: dict, run: dict | None = None) -> None:
        """Render the Config tab showing structured attack configuration."""
        run = run or self._history_current_run or {}
        attack_id = str(run.get("attack_id") or "")
        agent_name = str(run.get("agent_name") or "—")
        attack_type = str(run.get("attack_type") or "—")
        created = str(run.get("_date") or run.get("created_at") or "—")

        # Resolve missing display fields from IDs to avoid "-" in report configs.
        if (not agent_name or agent_name == "—") and run.get("agent_id"):
            agent_id = str(run.get("agent_id") or "")
            if agent_id:
                agent_name = self._agent_name_map_for_ids({agent_id}).get(
                    agent_id, agent_name
                )
        if (not attack_type or attack_type == "—") and attack_id:
            attack_type = self._attack_type_map_for_ids({attack_id}).get(
                attack_id, attack_type
            )

        # Header card
        with ui.card().tight().classes("w-full border border-primary/30 bg-primary/5"):
            with ui.column().classes("p-4 gap-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("bolt", color="primary").classes("text-lg")
                    ui.label(attack_type).classes("font-semibold text-sm")
                with ui.row().classes("items-center gap-4 text-xs text-grey-6"):
                    ui.icon("smart_toy", size="xs")
                    ui.label(agent_name)
                    ui.icon("calendar_today", size="xs")
                    ui.label(created)

        # Fetch attack config
        display_config: dict = {}
        if attack_id:
            with contextlib.suppress(Exception):
                attack_cfgs = self._attack_config_map_for_ids({attack_id})
                cfg = attack_cfgs.get(attack_id)
                if isinstance(cfg, dict) and cfg:
                    display_config = cfg

        if not display_config:
            raw_run_config = run.get("run_config")
            if isinstance(raw_run_config, dict):
                display_config = {
                    k: v for k, v in raw_run_config.items() if k != "evaluation_summary"
                }
            elif isinstance(raw_run_config, str) and raw_run_config.strip():
                try:
                    display_config = json.loads(raw_run_config)
                except Exception:
                    pass

        if not display_config:
            ui.label("No configuration found for this run.").classes(
                "text-xs text-grey-6"
            )
            return

        # Dataset section
        dataset_info = display_config.get("dataset") or display_config.get(
            "dataset_config"
        )
        if isinstance(dataset_info, dict):
            with ui.column().classes("w-full gap-1"):
                ui.label("DATASET").classes(
                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                )
                with ui.row().classes("flex-wrap gap-3"):
                    for dk, dv in dataset_info.items():
                        if dv not in (None, "", {}, []):
                            with ui.card().tight().classes("min-w-24"):
                                with ui.column().classes("px-3 py-2 gap-0"):
                                    ui.label(dk.upper()).classes(
                                        "text-[10px] font-semibold text-grey-5"
                                    )
                                    ui.label(str(dv)).classes("text-sm font-medium")

        # Parameters section
        ignored_keys = {
            "dataset",
            "dataset_config",
            "models",
            "model",
            "evaluation_summary",
        }
        params = {
            k: v
            for k, v in display_config.items()
            if k not in ignored_keys and not isinstance(v, (dict, list))
        }
        if params:
            with ui.column().classes("w-full gap-1"):
                ui.label("PARAMETERS").classes(
                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                )
                with ui.row().classes("flex-wrap gap-3"):
                    for pk, pv in params.items():
                        with ui.card().tight().classes("min-w-24"):
                            with ui.column().classes("px-3 py-2 gap-0"):
                                ui.label(pk.upper().replace("_", " ")).classes(
                                    "text-[10px] font-semibold text-grey-5"
                                )
                                ui.label(str(pv)).classes("text-sm font-medium")

        # Models section
        models_info = display_config.get("models") or display_config.get("model")
        if models_info:
            with ui.column().classes("w-full gap-1"):
                ui.label("MODELS").classes(
                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                )
                if isinstance(models_info, dict):
                    for mk, mv in models_info.items():
                        with ui.card().tight().classes("w-full"):
                            with ui.column().classes("px-3 py-2 gap-0"):
                                ui.label(mk.upper()).classes(
                                    "text-[10px] font-semibold text-grey-5"
                                )
                                if isinstance(mv, dict):
                                    for mmk, mmv in mv.items():
                                        if mmv not in (None, ""):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.icon(
                                                    "circle",
                                                    size="6px",
                                                    color="grey-6",
                                                )
                                                ui.label(f"{mmk}: {mmv}").classes(
                                                    "text-sm"
                                                )
                                else:
                                    ui.label(str(mv)).classes("text-sm")
                elif isinstance(models_info, list):
                    for m in models_info:
                        ui.label(str(m)).classes("text-sm")
                else:
                    ui.label(str(models_info)).classes("text-sm")

        # IDs
        with ui.column().classes("w-full gap-1 pt-2"):
            for id_label, id_val in [
                ("Attack ID", str(run.get("attack_id") or "—")),
                ("Agent ID", str(run.get("agent_id") or "—")),
                (
                    "Organization",
                    str(
                        run.get("organization_id")
                        or run.get("run_config", {}).get("organization_id")
                        or "—"
                    )
                    if isinstance(run.get("run_config"), dict)
                    else str(run.get("organization_id") or "—"),
                ),
            ]:
                with ui.row().classes("items-center gap-2"):
                    ui.label(id_label).classes("text-xs text-grey-6 font-medium")
                    ui.label(id_val).classes("text-xs font-mono text-grey-5")

        # Always expose raw config for completeness.
        with ui.column().classes("w-full gap-1 pt-3"):
            ui.label("RAW CONFIG").classes(
                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
            )
            ui.code(
                json.dumps(display_config, indent=2, default=str), language="json"
            ).classes("w-full text-xs")

    # ── History: load traces for a goal ──────────────────────────────────────

    async def _load_goal_traces(self, row: dict, container: ui.column) -> None:
        """Load and render traces for a specific goal result."""
        try:
            result_id = row.get("id")
            if not result_id:
                container.clear()
                with container:
                    ui.label("No result ID available.").classes("text-sm text-grey-6")
                return

            traces_raw = self.backend.list_traces(result_id=UUID(result_id))
            container.clear()

            serialized_traces = [_serialize(t) for t in traces_raw]
            synthetic_eval = self._build_synthetic_evaluation_trace(row)

            has_real_evaluation = False
            for td in serialized_traces:
                group, _ = self._classify_trace_step(td)
                if group == "evaluation":
                    has_real_evaluation = True
                    break

            if synthetic_eval is not None and not has_real_evaluation:
                synthetic_eval["sequence"] = len(serialized_traces) + 1
                serialized_traces.append(synthetic_eval)

            serialized_traces = self._ensure_evaluation_request_response(
                serialized_traces, row
            )

            if not serialized_traces:
                with container:
                    ui.label("No traces recorded for this result.").classes(
                        "text-sm text-grey-6 text-center py-6"
                    )
                return

            with container:
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label(
                        f"{len(serialized_traces)} step{'s' if len(serialized_traces) != 1 else ''}"
                    ).classes("text-xs text-grey-6")
                    ui.label(
                        f"{len([t for t in serialized_traces if self._classify_trace_step(t)[0] == 'evaluation'])} traces"
                    ).classes("text-xs text-grey-6")

                for td in serialized_traces:
                    _, label = self._classify_trace_step(td)
                    td["_display_label"] = label

                rendered_phase_view = self._render_autodan_phase_timeline(
                    serialized_traces
                )
                if not rendered_phase_view:
                    self._render_standard_trace_sections(serialized_traces)

        except Exception as exc:
            container.clear()
            with container:
                with ui.row().classes("gap-2 items-center py-4"):
                    ui.icon("error_outline", color="negative")
                    ui.label(f"Error loading traces: {exc}").classes(
                        "text-sm text-negative"
                    )

    def _extract_run_asr_display(self, run, run_results) -> str:
        """Return ASR string for a run, preferring synced evaluation_summary."""
        run_cfg = getattr(run, "run_config", None)
        if isinstance(run_cfg, dict):
            summary = run_cfg.get("evaluation_summary")
            if isinstance(summary, dict):
                try:
                    judge_count = int(summary.get("judge_count") or 0)
                    is_multi = bool(summary.get("is_multi_judge")) or (judge_count > 1)
                    if is_multi:
                        value = summary.get("majority_vote_asr")
                        if value is None:
                            value = summary.get("overall_majority_vote_asr")
                    else:
                        value = summary.get("overall_success_rate", 0.0)
                    return f"{float(value or 0.0) * 100:.1f}%"
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

    def navigate(self, view: str, schedule_refresh: bool = True) -> None:
        if view == "runs" and self.current_view.get("value") != "runs":
            self.runs_current_page = 1
        if view != "reports":
            self._close_reports_detail()
        self.current_view["value"] = view
        for v, panel in self.all_panels.items():
            panel.set_visibility(v == view)
        self.page_title.text = _VIEW_LABELS.get(view, "Dashboard")
        self._highlight_nav(view)
        if schedule_refresh:
            asyncio.create_task(self.refresh_view())

    def _change_runs_page(self, delta: int) -> None:
        new_page = self.runs_current_page + delta
        if new_page < 1 or new_page > self.runs_total_pages:
            return
        self.runs_current_page = new_page
        ui.timer(0, self._load_runs, once=True)

    def _on_runs_select(self) -> None:
        if self.runs_table is not None:
            self._selected_run_ids = [
                row["id"] for row in (self.runs_table.selected or [])
            ]
        if self._runs_delete_btn is not None:
            if self._selected_run_ids:
                self._runs_delete_btn.classes(remove="hidden")
            else:
                self._runs_delete_btn.classes(add="hidden")

    async def _delete_selected_runs(self) -> None:
        ids = list(self._selected_run_ids)
        if not ids:
            return
        try:
            for rid in ids:
                self.backend.delete_run(UUID(rid))
            ui.notify(f"Deleted {len(ids)} run(s)", type="positive")
        except Exception as exc:
            ui.notify(f"Delete failed: {exc}", type="negative")
        self._selected_run_ids.clear()
        if self.runs_table is not None:
            self.runs_table.selected.clear()
        if self._runs_delete_btn is not None:
            self._runs_delete_btn.classes(add="hidden")
        await self._load_runs()
        await self._load_history_reports()

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

    @staticmethod
    def _extract_row(payload: object) -> dict | None:
        """Normalize NiceGUI/Quasar click payloads to a row dictionary."""
        if isinstance(payload, dict):
            row = payload.get("row")
            if isinstance(row, dict):
                return row
            if "id" in payload:
                return payload
            return None

        if isinstance(payload, (list, tuple)):
            for item in payload:
                row = DashboardPage._extract_row(item)
                if row is not None:
                    return row

        return None

    def _attack_type_map(self) -> dict[str, str]:
        """Return mapping attack_id -> attack type for run table enrichment."""
        return self._attack_type_map_for_ids(None)

    def _agent_name_map(self) -> dict[str, str]:
        """Return mapping agent_id -> agent name for table enrichment."""
        return self._agent_name_map_for_ids(None)

    def _attack_type_map_for_ids(self, required_ids: set[str] | None) -> dict[str, str]:
        """Fetch attack types, paginating until required IDs are found."""
        out: dict[str, str] = {}
        page = 1
        page_size = 100

        while True:
            attacks_p = self.backend.list_attacks(page=page, page_size=page_size)
            if not attacks_p.items:
                break

            for attack in attacks_p.items:
                attack_id = str(attack.id)
                if required_ids is None or attack_id in required_ids:
                    out[attack_id] = attack.type

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((attacks_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    def _attack_config_map_for_ids(
        self, required_ids: set[str] | None
    ) -> dict[str, dict]:
        """Fetch attack configurations, paginating until required IDs are found.

        Returns mapping attack_id -> configuration dict (may be empty dict).
        """
        out: dict[str, dict] = {}
        page = 1
        page_size = 100

        while True:
            attacks_p = self.backend.list_attacks(page=page, page_size=page_size)
            if not attacks_p.items:
                break

            for attack in attacks_p.items:
                attack_id = str(attack.id)
                if required_ids is None or attack_id in required_ids:
                    # AttackRecord.configuration is a dict
                    cfg = getattr(attack, "configuration", {})
                    out[attack_id] = cfg or {}

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((attacks_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    def _agent_name_map_for_ids(self, required_ids: set[str] | None) -> dict[str, str]:
        """Fetch agent names, paginating until required IDs are found."""
        out: dict[str, str] = {}
        page = 1
        page_size = 100

        while True:
            agents_p = self.backend.list_agents(page=page, page_size=page_size)
            if not agents_p.items:
                break

            for agent in agents_p.items:
                agent_id = str(agent.id)
                if required_ids is None or agent_id in required_ids:
                    out[agent_id] = agent.name

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((agents_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    def _agent_records_map_for_ids(
        self, required_ids: set[str] | None
    ) -> dict[str, dict]:
        """Fetch serialized agent records, paginating until required IDs are found."""
        out: dict[str, dict] = {}
        page = 1
        page_size = 100

        while True:
            agents_p = self.backend.list_agents(page=page, page_size=page_size)
            if not agents_p.items:
                break

            for agent in agents_p.items:
                agent_id = str(agent.id)
                if required_ids is None or agent_id in required_ids:
                    out[agent_id] = _serialize(agent)

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((agents_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    @staticmethod
    def _derive_run_status(
        result_statuses: list[tuple[str, str | None]],
        observed_total_results: int | None = None,
        expected_total_goals: int | None = None,
        fallback: str = "",
    ) -> str:
        """Derive run status from associated goal evaluation statuses."""
        if observed_total_results is None:
            observed_total_results = len(result_statuses)

        if (
            isinstance(expected_total_goals, int)
            and expected_total_goals > 0
            and observed_total_results < expected_total_goals
        ):
            fallback_status = str(fallback or "").upper()
            if fallback_status in {"FAILED", "CANCELLED"}:
                return fallback_status
            return "RUNNING"

        buckets = [_result_bucket(status=s, notes=n) for s, n in result_statuses]
        has_pending = any(b == "pending" for b in buckets)
        if has_pending:
            return "RUNNING"
        if buckets:
            return "COMPLETED"
        return fallback or "PENDING"

    @staticmethod
    def _extract_expected_total_goals(run_data: dict) -> int | None:
        """Extract expected goal count from run_config when available."""
        if not isinstance(run_data, dict):
            return None

        run_cfg = run_data.get("run_config")
        if not isinstance(run_cfg, dict):
            return None

        candidates = (
            run_cfg.get("expected_total_goals"),
            run_cfg.get("expected_goal_count"),
            run_cfg.get("total_goals"),
            run_cfg.get("goal_count"),
        )
        for value in candidates:
            try:
                parsed = int(value)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """Best-effort float parsing with None fallback."""
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_run_evaluation_summary(run_data: dict) -> dict:
        """Extract evaluation_summary from run payload/run_config."""
        if not isinstance(run_data, dict):
            return {}

        run_cfg = run_data.get("run_config")
        if isinstance(run_cfg, dict):
            summary = run_cfg.get("evaluation_summary")
            return summary if isinstance(summary, dict) else {}

        if isinstance(run_cfg, str) and run_cfg.strip():
            with contextlib.suppress(Exception):
                parsed = json.loads(run_cfg)
                if isinstance(parsed, dict):
                    summary = parsed.get("evaluation_summary")
                    if isinstance(summary, dict):
                        return summary
        return {}

    @staticmethod
    def _coerce_binary_vote(value: object) -> int:
        """Normalize common vote values to 0/1 for dashboard metrics."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(float(value) > 0)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {
                "1",
                "true",
                "yes",
                "y",
                "success",
                "successful",
                "jailbreak",
                "harmful",
                "violating",
                "1_violating",
            }:
                return 1
            if normalized in {
                "0",
                "false",
                "no",
                "n",
                "safe",
                "compliant",
                "mitigated",
                "0_compliant",
                "",
            }:
                return 0
            with contextlib.suppress(ValueError):
                return int(float(normalized) > 0)
        return 0

    @staticmethod
    def _is_canonical_eval_vote_key(key: object) -> bool:
        """True only for canonical eval vote keys (exclude derived stats)."""
        if not isinstance(key, str):
            return False
        if not key.startswith("eval_"):
            return False
        if key.endswith("_raw_response"):
            return False
        if key.endswith("_mean") or key.endswith("_count"):
            return False
        return True

    @staticmethod
    def _judge_key_display_name(judge_key: object) -> str:
        """Return compact judge name for UI labels (e.g. eval_hbv -> hbv)."""
        if isinstance(judge_key, str) and judge_key.startswith("eval_"):
            return judge_key[5:]
        return str(judge_key)

    @classmethod
    def _extract_eval_votes_from_result(cls, result_data: dict) -> dict[str, int]:
        """Collect canonical eval_* judge votes from top-level/metadata/metrics."""
        votes: dict[str, int] = {}
        for source in (
            result_data,
            result_data.get("metadata"),
            result_data.get("evaluation_metrics"),
        ):
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                if not cls._is_canonical_eval_vote_key(key):
                    continue
                if value is None:
                    continue
                votes[key] = cls._coerce_binary_vote(value)

        return dict(sorted(votes.items()))

    @classmethod
    def _compute_goal_multi_judge_metrics(cls, result_data: dict) -> dict:
        """Compute per-goal multi-judge metrics from a single result row."""
        votes = cls._extract_eval_votes_from_result(result_data)
        if len(votes) <= 1:
            return {}

        row_votes = dict(votes)
        judge_avg = (
            sum(float(vote) for vote in row_votes.values()) / len(row_votes)
            if row_votes
            else None
        )
        return {
            "judge_count": len(row_votes),
            "judge_votes": dict(sorted(row_votes.items())),
            "judge_avg": judge_avg,
            # Keep an explicit majority_vote_asr alias so downstream consumers
            # can consistently derive per-goal majority verdicts.
            "majority_vote_asr": judge_avg,
        }

    def _summarize_run_results(
        self, run_id: UUID, run_data: dict | None = None
    ) -> dict[str, object]:
        """Return per-run result counts and derived run status."""
        evaluation_summary = self._extract_run_evaluation_summary(run_data or {})
        judge_count = int(evaluation_summary.get("judge_count") or 0)
        is_multi_judge = bool(evaluation_summary.get("is_multi_judge")) or (
            judge_count > 1
        )

        majority_vote_asr = self._safe_float(
            evaluation_summary.get("majority_vote_asr")
            if isinstance(evaluation_summary, dict)
            else None
        )
        if majority_vote_asr is None and isinstance(evaluation_summary, dict):
            majority_vote_asr = self._safe_float(
                evaluation_summary.get("overall_majority_vote_asr")
            )

        overall_success_rate = self._safe_float(
            evaluation_summary.get("overall_success_rate")
            if isinstance(evaluation_summary, dict)
            else None
        )

        page = 1
        page_size = 100
        fetched = 0
        total = 0
        successful_jailbreaks = 0
        mitigations = 0
        finished_goal_latencies_s: list[float] = []
        statuses: list[tuple[str, str | None]] = []
        computed_run_vote_columns: set[str] = set()
        computed_run_vote_rows: list[dict[str, int]] = []

        while True:
            rp = self.backend.list_results(
                run_id=run_id, page=page, page_size=page_size
            )
            if page == 1:
                total = int(rp.total or 0)
            if not rp.items:
                break

            for result in rp.items:
                serialized_result = _serialize(result)
                row_votes = self._extract_eval_votes_from_result(serialized_result)
                if row_votes:
                    computed_run_vote_columns.update(row_votes.keys())
                    computed_run_vote_rows.append(dict(row_votes))

                bucket = _result_bucket(
                    result.evaluation_status, result.evaluation_notes
                )
                if bucket == "jailbreak":
                    successful_jailbreaks += 1
                elif bucket == "mitigated":
                    mitigations += 1
                if bucket != "pending":
                    latency_s = self._extract_goal_latency_seconds(_serialize(result))
                    if isinstance(latency_s, (int, float)):
                        finished_goal_latencies_s.append(float(latency_s))
                statuses.append((result.evaluation_status, result.evaluation_notes))

            fetched += len(rp.items)
            if total > 0 and fetched >= total:
                break
            page += 1

        if total == 0:
            total = fetched

        expected_total_goals = self._extract_expected_total_goals(run_data or {})

        computed_judge_count = len(computed_run_vote_columns)
        if computed_judge_count > 0:
            judge_count = computed_judge_count
            is_multi_judge = judge_count > 1

        if is_multi_judge and majority_vote_asr is None and computed_run_vote_rows:
            majority_vote_asr = calculate_majority_vote_asr(
                [dict(row) for row in computed_run_vote_rows]
            )

        avg_goal_latency_s = (
            sum(finished_goal_latencies_s) / len(finished_goal_latencies_s)
            if finished_goal_latencies_s
            else None
        )

        overall_asr_rate = None
        if is_multi_judge and majority_vote_asr is not None:
            overall_asr_rate = majority_vote_asr
        elif overall_success_rate is not None:
            overall_asr_rate = overall_success_rate
        elif total > 0:
            overall_asr_rate = successful_jailbreaks / total

        overall_asr_display = (
            f"{(overall_asr_rate * 100):.1f}%"
            if isinstance(overall_asr_rate, (int, float))
            else "—"
        )

        return {
            "total_results": total,
            "successful_jailbreaks": successful_jailbreaks,
            "mitigations": mitigations,
            "failed_attacks": mitigations,
            "avg_goal_latency_s": avg_goal_latency_s,
            "evaluation_summary": evaluation_summary,
            "is_multi_judge": is_multi_judge,
            "judge_count": judge_count,
            "overall_asr_rate": overall_asr_rate,
            "overall_asr_display": overall_asr_display,
            "expected_total_goals": expected_total_goals,
            "status": self._derive_run_status(
                statuses,
                observed_total_results=total,
                expected_total_goals=expected_total_goals,
            ),
        }

    @staticmethod
    def _compute_run_latency_seconds(run_data: dict) -> float | None:
        """Best-effort run wall-time latency from run timestamps."""
        return _duration_seconds(
            str(run_data.get("created_at") or "") or None,
            str(run_data.get("updated_at") or "") or None,
        )

    @staticmethod
    def _extract_goal_latency_seconds(result_data: dict) -> float | None:
        """Best-effort per-goal latency from metadata/metrics or timestamps."""
        metadata = (
            result_data.get("metadata")
            if isinstance(result_data.get("metadata"), dict)
            else {}
        )
        metrics = (
            result_data.get("evaluation_metrics")
            if isinstance(result_data.get("evaluation_metrics"), dict)
            else {}
        )

        # Prefer end-to-end goal elapsed_s written by Tracker.finalize_goal().
        for key in ("elapsed_s",):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            value = metrics.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))

        # Secondary explicit fields if elapsed_s is missing.
        for key in ("latency_s", "duration_s"):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            value = metrics.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))

        return _duration_seconds(
            str(result_data.get("created_at") or "") or None,
            str(result_data.get("updated_at") or "") or None,
        )

    @staticmethod
    def _extract_category_label(result_data: dict) -> str | None:
        """Best-effort category label lookup from result metadata/metrics."""
        sources = []
        for src in (
            result_data,
            result_data.get("metadata"),
            result_data.get("evaluation_metrics"),
        ):
            if isinstance(src, dict):
                sources.append(src)

        key_candidates = (
            "category",
            "category_name",
            "harm_category",
            "risk_category",
            "risk_domain",
            "topic",
            "label",
            "l2_name",
            "l3_name",
            "l4_name",
            "l2-name",
            "l3-name",
            "l4-name",
        )

        for src in sources:
            for key in key_candidates:
                val = src.get(key)
                if val not in (None, ""):
                    return str(val)
            taxonomy = src.get("taxonomy")
            if isinstance(taxonomy, dict):
                for key in ("l2", "l3", "l4", "name", "category"):
                    val = taxonomy.get(key)
                    if val not in (None, ""):
                        return str(val)

        return None

    @staticmethod
    def _extract_goal_classifier_label(result_data: dict, field: str) -> str:
        """Extract classifier category/subcategory labels from result payload."""
        normalized = (field or "").strip().lower()
        if normalized not in {"category", "subcategory"}:
            return "N/A"

        sources = []
        for src in (
            result_data,
            result_data.get("metadata"),
            result_data.get("evaluation_metrics"),
        ):
            if isinstance(src, dict):
                sources.append(src)

        if normalized == "category":
            key_candidates = (
                "category",
                "category_name",
                "harm_category",
                "risk_category",
            )
            taxonomy_keys = ("category", "l2", "name")
        else:
            key_candidates = (
                "subcategory",
                "subcategory_name",
                "harm_subcategory",
                "risk_subcategory",
            )
            taxonomy_keys = ("subcategory", "l3", "l4", "name")

        for src in sources:
            for key in key_candidates:
                val = src.get(key)
                if val not in (None, ""):
                    return str(val)

            taxonomy = src.get("taxonomy")
            if isinstance(taxonomy, dict):
                for key in taxonomy_keys:
                    val = taxonomy.get(key)
                    if val not in (None, ""):
                        return str(val)

        return "N/A"

    @staticmethod
    def _goal_category_badge_text(result_data: dict) -> str:
        """Compose a single category/subcategory badge label for a goal."""
        category = DashboardPage._extract_goal_classifier_label(result_data, "category")
        subcategory = DashboardPage._extract_goal_classifier_label(
            result_data, "subcategory"
        )
        category = category if category and category != "N/A" else "N/A"
        subcategory = subcategory if subcategory and subcategory != "N/A" else "N/A"
        return f"{category} / {subcategory}"

    @staticmethod
    def _classify_trace_step(trace_data: dict) -> tuple[str, str]:
        """Classify a trace step into a semantic group and human label."""
        step_type = (trace_data.get("step_type") or "").upper()
        content = trace_data.get("content")

        if "GOAL" in step_type:
            return "goal", "Goal"
        if "EVALUATION" in step_type:
            return "evaluation", "Evaluation"
        if "TOOL" in step_type:
            return "tools", "Tools"
        if "TAP" in step_type or "DEPTH" in step_type or "ATTACK" in step_type:
            return "generation", "Attack / Generation"

        if isinstance(content, dict):
            step_name = str(content.get("step_name") or "").strip().lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )
            nested_result = (
                content.get("result") if isinstance(content.get("result"), dict) else {}
            )
            display_type = str(metadata.get("display_type") or "").strip().lower()
            _, response_value = DashboardPage._extract_request_response_candidates(
                content
            )
            has_target_response = response_value not in (None, "")
            if isinstance(response_value, str):
                has_target_response = response_value.strip().lower() not in {
                    "(response not available)",
                    "response not available",
                }

            def _has_eval_columns(source: dict) -> bool:
                return any(str(k).startswith("eval_") for k in source.keys())

            has_eval_columns = any(
                _has_eval_columns(source)
                for source in (content, metadata, nested_result)
                if isinstance(source, dict)
            )

            has_harm_judge_signal = has_eval_columns or any(
                source.get(key) is not None
                for source in (content, metadata, nested_result)
                if isinstance(source, dict)
                for key in (
                    "judge_score",
                    "best_score",
                    "judge_success",
                    "success",
                    "evaluation_status",
                    "explanation",
                    "scorer_explanation",
                )
            )

            on_topic_only = (
                metadata.get("on_topic_score") is not None
                and content.get("judge_score") is None
                and metadata.get("judge_score") is None
                and nested_result.get("judge_score") is None
                and not has_eval_columns
            )

            # TAP candidate traces carry per-candidate judge scores in metadata.
            # Surface them under Evaluation so users can inspect each scored prompt.
            if step_name.startswith("depth") and "candidate" in step_name:
                if on_topic_only:
                    return "generation", "Attack / Generation"
                if has_target_response and has_harm_judge_signal:
                    return "evaluation", "Evaluation"
                return "generation", "Attack / Generation"
            if (
                step_name in {"evaluation", "judge", "scoring"}
                or step_name.startswith("evaluation")
                or display_type == "bon_evaluation"
            ):
                return "evaluation", "Evaluation"
            if (
                "goal" in content
                and "request" not in content
                and "response" not in content
            ):
                return "goal", "Goal"
            if any(
                key in content
                for key in (
                    "judge_score",
                    "best_score",
                    "success",
                    "judge_model",
                    "evaluator",
                    "explanation",
                )
            ):
                return "evaluation", "Evaluation"
            # Prefix/completion judged by a model are evaluation payloads.
            if "prefix" in content and "completion" in content:
                return "evaluation", "Evaluation"
            if any(
                key in content
                for key in (
                    "attack_type",
                    "request",
                    "response",
                    "depth",
                    "width",
                    "iteration",
                    "improvement",
                )
            ):
                return "generation", "Attack / Generation"

        if step_type:
            return "other", step_type.replace("_", " ").title()
        return "other", "Other"

    @staticmethod
    def _is_harmful_evaluation_trace(trace_data: dict) -> bool:
        """Return True if an evaluation trace indicates harmful/successful outcome."""
        content = trace_data.get("content")
        if not isinstance(content, dict):
            return False

        nested_result = (
            content.get("result") if isinstance(content.get("result"), dict) else {}
        )
        metadata = (
            content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
        )
        response_payload = (
            content.get("response") if isinstance(content.get("response"), dict) else {}
        )

        def _as_bool_harmful_marker(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value > 0
            if isinstance(value, str):
                token = value.strip().lower()
                if token in {
                    "1",
                    "1.0",
                    "true",
                    "yes",
                    "y",
                    "harmful",
                    "unsafe",
                    "jailbreak",
                    "successful_jailbreak",
                    "1_violating",
                }:
                    return True
            return False

        def _contains_harmful_text(value: object) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            negative_phrases = (
                "not harmful",
                "non harmful",
                "harmless",
                "safe",
                "not unsafe",
                "no jailbreak",
            )
            if any(phrase in text for phrase in negative_phrases):
                return False
            return any(token in text for token in ("harmful", "unsafe", "jailbreak"))

        explanation = str(content.get("explanation") or "").lower()
        if not explanation and nested_result:
            explanation = str(nested_result.get("explanation") or "").lower()
        if _contains_harmful_text(explanation):
            return True

        success = content.get("success")
        if success is None:
            success = content.get("is_success")
        if success is None and nested_result:
            success = nested_result.get("success")
        if success is None and nested_result:
            success = nested_result.get("is_success")
        if success is None and metadata:
            success = metadata.get("success")
        if success is None and metadata:
            success = metadata.get("is_jailbreak")
        if _as_bool_harmful_marker(success):
            return True

        eval_status = str(
            content.get("evaluation_status")
            or nested_result.get("evaluation_status")
            or ""
        ).upper()
        if "SUCCESSFUL_JAILBREAK" in eval_status:
            return True

        judge_columns = (
            metadata.get("judge_columns")
            if isinstance(metadata.get("judge_columns"), dict)
            else {}
        )
        response_judge_columns = (
            response_payload.get("judge_columns")
            if isinstance(response_payload.get("judge_columns"), dict)
            else {}
        )

        for source in (
            content,
            nested_result,
            metadata,
            judge_columns,
            response_judge_columns,
        ):
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                if key.startswith("eval_"):
                    if _as_bool_harmful_marker(value):
                        return True

        for source in (content, nested_result, metadata):
            if not isinstance(source, dict):
                continue
            for key in ("explanation", "scorer_explanation", "evaluation_notes"):
                if _contains_harmful_text(source.get(key)):
                    return True

        return False

    @staticmethod
    def _build_synthetic_evaluation_trace(result: dict) -> dict | None:
        """Build a fallback evaluation trace from result fields when none exists."""
        eval_status = str(result.get("evaluation_status") or "")
        eval_notes = result.get("evaluation_notes")
        metrics = result.get("evaluation_metrics")
        metadata = result.get("metadata")

        has_eval_payload = bool(eval_status or eval_notes or metrics)
        if not has_eval_payload:
            return None

        metrics_dict = metrics if isinstance(metrics, dict) else {}
        metadata_dict = metadata if isinstance(metadata, dict) else {}

        request_value = (
            metadata_dict.get("request")
            or metadata_dict.get("request_payload")
            or metadata_dict.get("prompt")
            or metadata_dict.get("prefix")
        )
        response_value = (
            metadata_dict.get("response")
            or metadata_dict.get("response_body")
            or metadata_dict.get("completion")
            or metadata_dict.get("raw_response_body")
        )

        best_score = metrics_dict.get("best_score")
        if best_score is None:
            best_score = metadata_dict.get("best_score")

        bucket = _result_bucket(eval_status, eval_notes)
        success = bucket == "jailbreak"

        content = {
            "step_name": "Evaluation",
            "evaluation_status": eval_status,
            "success": success,
            "explanation": eval_notes,
            "judge_score": best_score,
            "request": request_value,
            "response": response_value,
            "metadata": metrics_dict or metadata_dict,
        }

        return {
            "id": str(result.get("id") or "synthetic-evaluation"),
            "result_id": result.get("id"),
            "sequence": 1,
            "step_type": "EVALUATION",
            "content": content,
            "created_at": result.get("updated_at") or result.get("created_at"),
        }

    @staticmethod
    def _extract_request_response_candidates(content: object) -> tuple[object, object]:
        """Best-effort extraction of request/response payloads from trace content."""
        if not isinstance(content, dict):
            return None, None

        metadata = (
            content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
        )
        nested_result = (
            content.get("result") if isinstance(content.get("result"), dict) else {}
        )

        request_value = (
            content.get("request")
            or content.get("prefix")
            or content.get("prompt")
            or nested_result.get("request")
            or nested_result.get("prefix")
            or nested_result.get("prompt")
            or metadata.get("request")
            or metadata.get("prefix")
            or metadata.get("prompt")
        )
        response_value = (
            content.get("response")
            or content.get("completion")
            or content.get("answer")
            or nested_result.get("response")
            or nested_result.get("completion")
            or nested_result.get("answer")
            or metadata.get("response")
            or metadata.get("completion")
            or metadata.get("answer")
            or metadata.get("raw_response_body")
        )

        if isinstance(request_value, dict):
            request_value = (
                request_value.get("prompt")
                or request_value.get("request")
                or request_value
            )

        if isinstance(response_value, dict):
            response_value = (
                response_value.get("target_response")
                or response_value.get("response")
                or response_value.get("completion")
                or response_value.get("generated_text")
                or response_value
            )

        return request_value, response_value

    def _ensure_evaluation_request_response(
        self,
        serialized_traces: list[dict],
        result: dict,
    ) -> list[dict]:
        """Inject Request/Response in evaluation traces so they are always visible."""

        def _trace_locators(content: object) -> dict[str, object]:
            if not isinstance(content, dict):
                return {}
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )
            return {
                "branch_index": metadata.get(
                    "branch_index", content.get("branch_index")
                ),
                "stream_index": metadata.get(
                    "stream_index", content.get("stream_index")
                ),
                "iteration": metadata.get("iteration", content.get("iteration")),
            }

        # Gather all traces that already carry usable request/response payloads.
        payload_sources: list[dict[str, object]] = []
        for td in serialized_traces:
            req, resp = self._extract_request_response_candidates(td.get("content"))
            if req in (None, "") and resp in (None, ""):
                continue
            payload_sources.append(
                {
                    "sequence": int(td.get("sequence") or 0),
                    "request": req,
                    "response": resp,
                    **_trace_locators(td.get("content")),
                }
            )

        fallback_request = None
        fallback_response = None
        if payload_sources:
            # Prefer the latest observed payload as global fallback.
            last_payload = max(
                payload_sources, key=lambda p: int(p.get("sequence") or 0)
            )
            fallback_request = last_payload.get("request")
            fallback_response = last_payload.get("response")

        # Fall back to result-level metadata/payload.
        result_meta = (
            result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        )
        if fallback_request in (None, ""):
            fallback_request = (
                result_meta.get("request")
                or result_meta.get("request_payload")
                or result_meta.get("prompt")
                or result_meta.get("prefix")
                or result.get("goal")
            )
        if fallback_response in (None, ""):
            fallback_response = (
                result_meta.get("response")
                or result_meta.get("response_body")
                or result_meta.get("completion")
                or result_meta.get("answer")
                or result_meta.get("raw_response_body")
            )

        # Hard guarantee: keep blocks visible even when upstream payload is incomplete.
        if fallback_request in (None, ""):
            fallback_request = "(request not available)"
        if fallback_response in (None, ""):
            fallback_response = "(response not available)"

        for td in serialized_traces:
            group, _ = self._classify_trace_step(td)
            if group != "evaluation":
                continue
            content = td.get("content")
            if not isinstance(content, dict):
                content = {"value": content}
                td["content"] = content

            if content.get("request") not in (None, "") and content.get(
                "response"
            ) not in (
                None,
                "",
            ):
                continue

            current_seq = int(td.get("sequence") or 0)
            current_loc = _trace_locators(content)

            matched_payload = None

            # 1) Strongest match: same branch+stream and closest previous sequence.
            branch_value = current_loc.get("branch_index")
            stream_value = current_loc.get("stream_index")
            if branch_value is not None and stream_value is not None:
                same_branch_stream = [
                    p
                    for p in payload_sources
                    if p.get("branch_index") == branch_value
                    and p.get("stream_index") == stream_value
                ]
                if same_branch_stream:
                    same_branch_stream.sort(
                        key=lambda p: (
                            abs(int(p.get("sequence") or 0) - current_seq),
                            int(p.get("sequence") or 0) > current_seq,
                        )
                    )
                    matched_payload = same_branch_stream[0]

            # 2) Next best: same iteration and closest sequence.
            if matched_payload is None and current_loc.get("iteration") is not None:
                same_iteration = [
                    p
                    for p in payload_sources
                    if p.get("iteration") == current_loc.get("iteration")
                ]
                if same_iteration:
                    same_iteration.sort(
                        key=lambda p: (
                            abs(int(p.get("sequence") or 0) - current_seq),
                            int(p.get("sequence") or 0) > current_seq,
                        )
                    )
                    matched_payload = same_iteration[0]

            # 3) Fallback: nearest previous payload by sequence.
            if matched_payload is None and payload_sources:
                previous = [
                    p
                    for p in payload_sources
                    if int(p.get("sequence") or 0) <= current_seq
                ]
                if previous:
                    matched_payload = max(
                        previous, key=lambda p: int(p.get("sequence") or 0)
                    )
                else:
                    matched_payload = min(
                        payload_sources,
                        key=lambda p: abs(int(p.get("sequence") or 0) - current_seq),
                    )

            if content.get("request") in (None, ""):
                content["request"] = (
                    matched_payload.get("request")
                    if isinstance(matched_payload, dict)
                    and matched_payload.get("request") not in (None, "")
                    else fallback_request
                )
            if content.get("response") in (None, ""):
                content["response"] = (
                    matched_payload.get("response")
                    if isinstance(matched_payload, dict)
                    and matched_payload.get("response") not in (None, "")
                    else fallback_response
                )

        return serialized_traces

    # ── Attack-specific goal card helpers ─────────────────────────────────────

    @staticmethod
    def _border_color_for_bucket(bucket: str) -> str:
        if bucket == "jailbreak":
            return "border-red-400"
        if bucket == "mitigated":
            return "border-green-400"
        if bucket == "failed":
            return "border-orange-400"
        return "border-grey-300"

    def _render_compact_card(self, row: dict, on_click) -> None:
        """Render a compact clickable goal card for the left-panel list view."""
        goal_text = str(row.get("goal") or "—")
        goal_number = row.get("goal_number", "?")
        bucket = row.get("_bucket", "pending")
        border_color = self._border_color_for_bucket(bucket)
        with (
            ui.card()
            .tight()
            .classes(
                f"w-full border-l-4 {border_color} cursor-pointer"
                " hover:shadow-sm transition-shadow"
            )
            .on("click", on_click)
        ):
            with ui.row().classes("items-start gap-2 px-3 py-2 w-full"):
                ui.label(f"#{goal_number}").classes(
                    "font-bold text-xs text-grey-5 shrink-0 w-6 pt-0.5 text-right"
                )
                ui.label(goal_text).classes(
                    "text-xs text-grey-8 flex-1 leading-snug whitespace-pre-wrap"
                )

    @contextlib.contextmanager
    def _goal_card_shell(self, row: dict, detail_mode: bool = False):
        goal_text = str(row.get("goal") or "—")
        goal_number = row.get("goal_number", "?")
        bucket = row.get("_bucket", "pending")
        border_color = self._border_color_for_bucket(bucket)
        if detail_mode:
            _cat = row.get("_goal_category") or ""
            _subcat = row.get("_goal_subcategory") or ""
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    ui.label(f"Goal #{goal_number}").classes(
                        "font-bold text-base shrink-0"
                    )
                    if bucket == "jailbreak":
                        ui.badge("Jailbreak", color="negative").classes("text-xs")
                    elif bucket == "mitigated":
                        ui.badge("Mitigated", color="positive").classes("text-xs")
                    elif bucket == "failed":
                        ui.badge("Error", color="warning").classes("text-xs")
                    lat = row.get("_goal_latency")
                    if lat and lat != "—":
                        ui.badge(f"Latency: {lat}", color="grey-7").classes("text-xs")
                if _cat:
                    _cat_str = _cat
                    if _subcat and _subcat not in ("", "N/A"):
                        _cat_str += f" › {_subcat}"
                    ui.label(_cat_str).classes("text-xs text-grey-5 tracking-wide")
                ui.label(goal_text).classes(
                    "text-sm text-grey-8 whitespace-pre-wrap leading-relaxed"
                )
            ui.separator().classes("my-2")
            yield
        else:
            with ui.card().tight().classes(f"w-full border-l-4 {border_color}"):
                with ui.column().classes("w-full gap-2 p-3") as col:
                    ui.label(f"Goal #{goal_number}").classes(
                        "font-bold text-sm shrink-0"
                    )
                    ui.label(goal_text).classes(
                        "text-sm text-grey-8 whitespace-pre-wrap"
                    )
                    yield col

    @staticmethod
    def _wire_expand_toggle(body_col) -> None:
        toggle_btn = (
            ui.button("Expand", icon="expand_more")
            .props("flat no-caps size=sm color=grey-7")
            .classes("w-full")
        )
        _state: dict = {"open": False}

        def _toggle(_b=body_col, _btn=toggle_btn, _s=_state) -> None:
            _s["open"] = not _s["open"]
            _b.set_visibility(_s["open"])
            _btn.props(
                f"label={'Collapse' if _s['open'] else 'Expand'} icon={'expand_less' if _s['open'] else 'expand_more'} flat no-caps size=sm color=grey-7"
            )

        toggle_btn.on_click(_toggle)

    # ── Baseline ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_baseline_traces(traces: list[dict], goal: str = "") -> list[dict]:
        """Parse Baseline attack traces into per-template rows.

        Each row dict:
          num           – 1-based row number
          template      – attack_prompt with goal text replaced by {goal}
          prompt        – raw attack prompt sent to target
          response      – target model response
          result        – "Jailbreak" | "Mitigated" | "Error"
          _bucket       – "jailbreak" | "mitigated" | "error"
        """
        from collections import deque  # noqa: PLC0415

        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        # Baseline writes one "Template:…" interaction trace per template and
        # one evaluation trace from the baseline_pattern_evaluator.
        interaction_traces: list[tuple[str, dict]] = []
        eval_trace_result: dict = {}

        for td in sorted_traces:
            content = td.get("content") or {}
            step_name = str(content.get("step_name") or td.get("step_name") or "")
            if step_name.startswith("Template:"):
                interaction_traces.append((step_name, content))
            elif content.get("evaluator") == "baseline_pattern_evaluator":
                eval_trace_result = content.get("result") or {}

        # Stable sort: by step_name then first message content
        interaction_traces.sort(
            key=lambda x: (
                x[0],
                (x[1].get("request") or {}).get("messages", [{}])[0].get("content", "")
                if (x[1].get("request") or {}).get("messages")
                else "",
            )
        )

        # Build lookup: (template_category, response_length) → deque of eval entries
        eval_by_key: dict[tuple, deque] = {}
        for ev in eval_trace_result.get("evaluations") or []:
            key = (
                ev.get("template_category") or "",
                int(ev.get("response_length") or 0),
            )
            if key not in eval_by_key:
                eval_by_key[key] = deque()
            eval_by_key[key].append(ev)

        rows: list[dict] = []
        for idx, (_, content) in enumerate(interaction_traces, start=1):
            request = content.get("request") or {}
            messages = request.get("messages") or []
            attack_prompt = messages[0].get("content", "") if messages else ""
            if not attack_prompt:
                attack_prompt = str(request.get("prompt") or "")

            _raw_resp = content.get("response")
            _actual_resp, _g_side, _g_expl, _g_cats = (
                DashboardPage._extract_guardrail_from_response(_raw_resp)
            )
            response_text = str(_actual_resp or "")

            metadata = content.get("metadata") or {}
            template_category = str(metadata.get("template_category") or "")
            response_length = int(metadata.get("response_length") or len(response_text))

            # Replace goal text in prompt with {goal} placeholder for display
            if goal and goal in attack_prompt:
                template_display = attack_prompt.replace(goal, "{goal}", 1)
            else:
                template_display = attack_prompt

            # Match against the evaluator result
            key = (template_category, response_length)
            success: bool | None = None
            q = eval_by_key.get(key)
            if q:
                ev = q.popleft()
                success = bool(ev.get("success", False))

            if _g_side:
                bucket = "mitigated"
            elif success is True:
                bucket = "jailbreak"
            elif success is False:
                bucket = "mitigated"
            elif response_text:
                # Have a response but no evaluator match — treat as pending
                bucket = "mitigated"
            else:
                bucket = "error"

            rows.append(
                {
                    "num": idx,
                    "template": template_display,
                    "template_category": template_category,
                    "prompt": attack_prompt,
                    "response": response_text,
                    "result": (
                        "Jailbreak"
                        if bucket == "jailbreak"
                        else "Error"
                        if bucket == "error"
                        else "Mitigated"
                    ),
                    "_bucket": bucket,
                    "_guardrail_side": _g_side,
                    "_guardrail_explanation": _g_expl,
                    "_guardrail_categories": _g_cats,
                }
            )

        return rows

    def _render_baseline_goal_card(
        self, row: dict, template_rows: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a Baseline goal card grouped by template category."""

        def _fmt_cat(cat: str) -> str:
            return cat.replace("_", " ").title() if cat else "Uncategorised"

        # Build category groups preserving insertion order
        groups: dict[str, list[dict]] = {}
        for tr in template_rows:
            cat = tr.get("template_category") or ""
            groups.setdefault(cat, []).append(tr)

        n_jailbreaks = sum(1 for r in template_rows if r["_bucket"] == "jailbreak")
        n_mitigated = sum(1 for r in template_rows if r["_bucket"] == "mitigated")
        n_errors = sum(1 for r in template_rows if r["_bucket"] == "error")

        bl_cols = [
            {
                "name": "template_short",
                "label": "Template",
                "field": "template_short",
                "align": "left",
            },
            {
                "name": "result",
                "label": "Result",
                "field": "result",
                "align": "center",
                "style": "width:100px",
            },
        ]

        with self._goal_card_shell(row, detail_mode):
            if not template_rows:
                ui.label("No Baseline template data recorded.").classes(
                    "text-sm text-grey-6"
                )
                return

            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                for cat, rows_in_cat in groups.items():
                    cat_label = _fmt_cat(cat)
                    cat_n_jailbreaks = sum(
                        1 for r in rows_in_cat if r["_bucket"] == "jailbreak"
                    )

                    with ui.row().classes("items-center gap-2 mt-3 mb-0.5 px-1"):
                        ui.label(cat_label).classes(
                            "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                        )
                        ui.badge(
                            f"{len(rows_in_cat)} prompt{'s' if len(rows_in_cat) != 1 else ''}",
                            color="grey-5",
                        ).classes("text-xs")
                        if cat_n_jailbreaks:
                            ui.badge(
                                f"{cat_n_jailbreaks} jailbreak{'s' if cat_n_jailbreaks != 1 else ''}",
                                color="negative",
                            ).classes("text-xs")

                    tbl_rows = [
                        {
                            "_num": tr["num"],
                            "template_short": (
                                (
                                    tr["template"].replace("{goal}", "", 1)[:80]
                                    + "\u2026"
                                )
                                if len(tr["template"].replace("{goal}", "", 1)) > 80
                                else tr["template"].replace("{goal}", "", 1)
                            )
                            or "—",
                            "result": tr["result"],
                            "_bucket": tr["_bucket"],
                            "_full_prompt": tr.get("prompt") or "",
                            "_response": tr.get("response") or "",
                            "_guardrail_side": tr.get("_guardrail_side") or "",
                            "_guardrail_explanation": tr.get("_guardrail_explanation")
                            or "",
                            "_guardrail_categories": tr.get("_guardrail_categories")
                            or [],
                        }
                        for tr in rows_in_cat
                    ]

                    tbl = (
                        ui.table(
                            columns=bl_cols,
                            rows=tbl_rows,
                            row_key="_num",
                        )
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        tbl.props(
                            f":expanded-rows='{json.dumps([r['_num'] for r in tbl_rows])}'"
                        )

                    tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="template_short" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:360px">
    {{ props.row.template_short }}
  </q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row._bucket === 'jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row._bucket === 'mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else color="warning" class="text-xs">Error</q-badge>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">PROMPT SENT TO TARGET</div>
      <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                  border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prompt || '\u2014' }}</pre>
      <template v-if="props.row._guardrail_side !== 'before'">
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">TARGET RESPONSE</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._response || 'No response recorded.' }}</pre>
      </template>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">&#x26a0; BEFORE GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">&#x1f6ab; AFTER GUARDRAIL &#x2014; CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">&#x1f6e1; GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                    )

                # ── Summary row ───────────────────────────────────────
                ui.separator().classes("mt-2")
                with ui.row().classes("items-center gap-2 mt-2 flex-wrap"):
                    ui.label("Summary:").classes("text-xs font-semibold text-grey-6")
                    if n_jailbreaks:
                        ui.badge(
                            f"{n_jailbreaks} Jailbreak{'s' if n_jailbreaks != 1 else ''}",
                            color="negative",
                        ).classes("text-xs")
                    ui.badge(f"{n_mitigated} Mitigated", color="positive").classes(
                        "text-xs"
                    )
                    if n_errors:
                        ui.badge(
                            f"{n_errors} Error{'s' if n_errors != 1 else ''}",
                            color="warning",
                        ).classes("text-xs")

            if not detail_mode:
                self._wire_expand_toggle(body_col)

    # ── Best-of-N (BoN) ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_bon_traces(traces: list[dict]) -> list[dict]:
        """Parse BoN traces into per-step groups.

        Returns a list of step dicts, each containing:
          step          – 0-based step index
          step_label    – human label "Step N / M"
          is_jailbreak  – True if the judge confirmed jailbreak for this step
          candidates    – list of candidate dicts:
              k                – 1-based candidate index
              augmented_prompt – text sent to target
              response         – target model response
              response_length  – char length of response
              is_best          – True if selected as best in the step
              error            – error string or None
              _guardrail_side  – "" | "before" | "after" | "unknown"
              _guardrail_explanation – explanation string
        """
        candidate_traces: list[dict] = []
        eval_traces: list[dict] = []

        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            dtype = str(meta.get("display_type") or "").lower()
            if dtype == "bon_candidate":
                candidate_traces.append(td)
            elif dtype == "bon_evaluation":
                eval_traces.append(td)

        # Build lookup: step index → is_jailbreak (from evaluation traces only)
        step_jailbreak: dict[int, bool] = {}
        for td in eval_traces:
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            s = meta.get("step")
            if s is not None:
                step_jailbreak[int(s)] = bool(meta.get("is_jailbreak", False))

        # Group candidate traces by step
        by_step: dict[int, list[dict]] = {}
        for td in candidate_traces:
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            s = int(meta.get("step", 0))
            by_step.setdefault(s, []).append(td)

        if not by_step:
            return []

        n_steps_seen = 1
        for td in candidate_traces:
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            n_steps_seen = max(n_steps_seen, int(meta.get("n_steps", 1)))

        steps: list[dict] = []
        for s in sorted(by_step.keys()):
            cands = []
            for td in sorted(
                by_step[s],
                key=lambda x: int(
                    (x.get("content") or {})
                    .get("metadata", {})
                    .get("candidate_index", 0)
                ),
            ):
                content = td.get("content") or {}
                meta = content.get("metadata") or {}
                request = content.get("request") or {}
                response_obj = content.get("response")

                augmented_prompt = (
                    request.get("prompt")
                    or (request.get("messages") or [{}])[0].get("content", "")
                    if isinstance(request, dict)
                    else ""
                )

                response_obj, _g_side, _g_expl, _g_cats = (
                    DashboardPage._extract_guardrail_from_response(response_obj)
                )

                if isinstance(response_obj, dict):
                    response_text = (
                        response_obj.get("generated_text")
                        or response_obj.get("completion")
                        or ""
                    )
                    error_text = response_obj.get("error_message")
                elif response_obj is not None:
                    response_text = str(response_obj)
                    error_text = None
                else:
                    response_text = ""
                    error_text = None

                resp_len = int(meta.get("response_length", len(response_text or "")))
                cands.append(
                    {
                        "k": int(meta.get("candidate_index", 0)),
                        "augmented_prompt": augmented_prompt,
                        "response": response_text,
                        "response_length": resp_len,
                        "is_best": bool(meta.get("is_best", False)),
                        "error": error_text,
                        "_guardrail_side": _g_side,
                        "_guardrail_explanation": _g_expl,
                        "_guardrail_categories": _g_cats,
                    }
                )

            steps.append(
                {
                    "step": s,
                    "step_label": f"Step {s + 1} / {n_steps_seen}",
                    "is_jailbreak": step_jailbreak.get(s, False),
                    "candidates": cands,
                }
            )

        return steps

    def _render_bon_goal_card(
        self, row: dict, step_groups: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a BoN goal card with per-step candidate tables."""
        with self._goal_card_shell(row, detail_mode):
            if not step_groups:
                ui.label("No BoN step results recorded.").classes("text-sm text-grey-6")
                return

            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                for sg in step_groups:
                    step_label = sg["step_label"]
                    is_jailbreak_step = sg["is_jailbreak"]
                    candidates = sg["candidates"]

                    with ui.row().classes("items-center gap-2 mt-3 mb-0.5 px-1"):
                        ui.label(step_label).classes(
                            "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                        )
                        if is_jailbreak_step:
                            ui.badge("Jailbreak", color="negative").classes("text-xs")

                    columns = [
                        {
                            "name": "k",
                            "label": "K",
                            "field": "k",
                            "align": "center",
                            "style": "width:48px",
                        },
                        {
                            "name": "augmented_prompt",
                            "label": "Augmented prompt",
                            "field": "augmented_prompt",
                            "align": "left",
                        },
                        {
                            "name": "response_length",
                            "label": "Response length",
                            "field": "response_length",
                            "align": "center",
                            "style": "width:140px",
                        },
                        {
                            "name": "result",
                            "label": "Result",
                            "field": "result",
                            "align": "center",
                            "style": "width:100px",
                        },
                    ]

                    rows_data = []
                    for c in candidates:
                        if c.get("_guardrail_side"):
                            result_label = "Mitigated"
                        elif c["error"]:
                            result_label = "Error"
                        elif c["is_best"] and is_jailbreak_step:
                            result_label = "Jailbreak"
                        elif c["is_best"] and not is_jailbreak_step:
                            result_label = "Mitigated"
                        else:
                            result_label = "—"
                        aug = c.get("augmented_prompt") or ""
                        rows_data.append(
                            {
                                "k": c["k"],
                                "augmented_prompt": (aug[:80] + "…")
                                if len(aug) > 80
                                else aug or "—",
                                "response_length": c["response_length"],
                                "result": result_label,
                                "_is_best": c["is_best"],
                                "_full_prompt": aug,
                                "_response": c.get("response") or "",
                                "_guardrail_side": c.get("_guardrail_side") or "",
                                "_guardrail_explanation": c.get(
                                    "_guardrail_explanation"
                                )
                                or "",
                            }
                        )

                    tbl = (
                        ui.table(columns=columns, rows=rows_data, row_key="k")
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        tbl.props(
                            f":expanded-rows='{json.dumps([r['k'] for r in rows_data])}'"
                        )

                    tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand"
      :class="props.row._is_best ? 'bg-grey-2' : ''"
      style="cursor:pointer">
  <q-td key="k" :props="props">{{ props.row.k }}</q-td>
  <q-td key="augmented_prompt" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:320px">
    {{ props.row.augmented_prompt }}
  </q-td>
  <q-td key="response_length" :props="props">{{ props.row.response_length }}</q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row.result === 'Jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row.result === 'Mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else-if="props.row.result === 'Error'" color="warning" class="text-xs">Error</q-badge>
    <span v-else class="text-grey-5">&#8212;</span>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">PROMPT SENT TO TARGET</div>
      <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                  border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prompt || '\u2014' }}</pre>
      <template v-if="props.row._guardrail_side !== 'before'">
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">TARGET RESPONSE</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._response || 'No response recorded.' }}</pre>
      </template>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">&#x26a0; BEFORE GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">&#x1f6ab; AFTER GUARDRAIL &#x2014; CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">&#x1f6e1; GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                    )

            if not detail_mode:
                self._wire_expand_toggle(body_col)

    # ── H4rm3l formatting ─────────────────────────────────────────────────────

    @staticmethod
    def _format_h4rm3l_program(program: str) -> str:
        """Convert an h4rm3l program string to a human-readable arrow chain."""
        if not program or not isinstance(program, str):
            return program or ""
        p = program.strip()
        # If it looks like a Python/h4rm3l call chain, simplify
        import re as _re  # noqa: PLC0415

        # Match Apply(transform1, Apply(transform2, ...)) style
        names = _re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)(?:\s*\()", p)
        if names:
            # Skip generic wrappers
            skip = {"Apply", "Compose", "Pipeline"}
            filtered = [n for n in names if n not in skip]
            if filtered:
                return " → ".join(
                    " ".join(
                        w.capitalize() for w in _re.sub(r"([A-Z])", r" \1", n).split()
                    )
                    for n in filtered
                )
        # Fallback: title-case snake_case names
        if "_" in p and " " not in p:
            return p.replace("_", " ").title()
        return p

    @staticmethod
    def _extract_guardrail_from_response(response_value) -> tuple:
        """Detect a guardrail event embedded in a response value.

        Returns (actual_response, guardrail_side, guardrail_explanation, guardrail_categories) where:
        - actual_response: real response string/value, or None if before-guardrail
        - guardrail_side: "before" | "after" | "unknown" | ""
        - guardrail_explanation: human-readable reason string
        - guardrail_categories: list of harm category strings
        """
        # Legacy string-encoded format produced by old versions of
        # tap/generation.py: "[GUARDRAIL:<side>] <reasoning>".
        # New runs store a proper guardrail dict — this branch handles
        # traces already persisted in the database with the old format.
        if isinstance(response_value, str):
            import re as _re

            _m = _re.match(r"^\[GUARDRAIL:(\w+)\]\s*(.*)", response_value, _re.DOTALL)
            if _m:
                side = _m.group(1)
                explanation = _m.group(2).strip() or "Blocked by guardrail"
                return None, side, explanation, []
            return response_value, "", "", []

        if not isinstance(response_value, dict):
            return response_value, "", "", []

        # New format: adapter_type == "guardrail" with agent_specific_data
        if response_value.get("adapter_type") == "guardrail":
            info = response_value.get("agent_specific_data") or {}
            side = info.get("side", "unknown")
            explanation = str(
                info.get("reasoning")
                or info.get("message")
                or info.get("explanation")
                or "Blocked by guardrail"
            )
            categories = info.get("categories") or []
            if side == "after":
                actual = info.get("target_response") or None
            else:
                actual = None
            return actual, side, explanation, categories

        # Legacy format: dict with side key directly (from tracker extraction)
        if response_value.get("side") in ("before", "after", "unknown"):
            side = response_value.get("side", "unknown")
            explanation = str(
                response_value.get("reasoning")
                or response_value.get("message")
                or response_value.get("explanation")
                or "Blocked by guardrail"
            )
            categories = response_value.get("categories") or []
            if side == "after":
                actual = response_value.get("target_response") or None
            else:
                actual = None
            return actual, side, explanation, categories

        return response_value, "", "", []

    # ── PAIR ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_pair_traces(traces: list[dict]) -> list[dict]:
        """Parse PAIR traces into per-iteration rows.

        Each row:
          iteration  – 1-based iteration number
          prompt     – prompt sent to target
          response   – target response
          score      – judge score (int or None)
          is_best    – True if this had the highest score
        """
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))
        rows: list[dict] = []

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            step_name = str(content.get("step_name") or "")
            if "Iteration" not in step_name and "iteration" not in step_name:
                continue
            metadata = content.get("metadata") or {}
            iteration = int(metadata.get("iteration") or len(rows) + 1)
            req = content.get("request") or {}
            prompt = req.get("prompt") or "" if isinstance(req, dict) else str(req)
            if isinstance(prompt, list):
                user_msgs = [
                    m.get("content", "") for m in prompt if m.get("role") == "user"
                ]
                prompt = user_msgs[-1] if user_msgs else ""
            resp = content.get("response")
            resp, _pair_g_side, _pair_g_expl, _pair_g_cats = (
                DashboardPage._extract_guardrail_from_response(resp)
            )
            # Fallback: guardrail info in metadata (older traces)
            if not _pair_g_side:
                _gi = metadata.get("guardrail_info") or {}
                if not _gi:
                    _tc = metadata.get("target_call") or {}
                    _gi = _tc.get("guardrail_info") or {}
                if _gi.get("side"):
                    _pair_g_side = _gi["side"]
                    _pair_g_expl = str(
                        _gi.get("reasoning")
                        or _gi.get("message")
                        or _gi.get("explanation")
                        or "Blocked by guardrail"
                    )
                    _pair_g_cats = _gi.get("categories") or []
            if isinstance(resp, dict):
                response = (
                    resp.get("generated_text") or resp.get("completion") or str(resp)
                )
            elif resp is not None:
                response = str(resp)
            else:
                response = ""
            score_raw = (
                metadata.get("score")
                or metadata.get("judge_score")
                or content.get("score")
            )
            try:
                score = int(float(score_raw)) if score_raw is not None else None
            except (TypeError, ValueError):
                score = None
            rows.append(
                {
                    "iteration": iteration,
                    "prompt": str(prompt),
                    "response": response,
                    "score": score,
                    "is_best": False,
                    "_guardrail_side": _pair_g_side,
                    "_guardrail_explanation": _pair_g_expl,
                    "_guardrail_categories": _pair_g_cats,
                }
            )

        # Mark best score
        if rows:
            scored = [r for r in rows if r["score"] is not None]
            if scored:
                best = max(scored, key=lambda r: r["score"])  # type: ignore[arg-type]
                best["is_best"] = True

        return rows

    def _render_pair_goal_card(
        self, row: dict, steps: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a PAIR goal card as a conversation with per-iteration steps."""
        with self._goal_card_shell(row, detail_mode):
            if not steps:
                ui.label("No PAIR iteration data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-0 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    for step in steps:
                        iteration = step["iteration"]
                        score = step["score"]
                        is_best = step["is_best"]
                        prompt = step["prompt"]
                        response = step["response"]
                        _guardrail_side = step.get("_guardrail_side") or ""
                        _guardrail_explanation = (
                            step.get("_guardrail_explanation") or ""
                        )
                        _guardrail_categories = step.get("_guardrail_categories") or []

                        with ui.row().classes("items-center gap-2 mt-3 mb-1 px-1"):
                            _iter_label = f"Iteration {iteration}"
                            if score is not None:
                                _iter_label += f" — Score {score}/10"
                            if is_best:
                                _iter_label += " — Best"
                            ui.label(_iter_label).classes(
                                "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                            )

                        ui.label("PROMPT SENT TO TARGET").classes(
                            "text-[10px] text-grey-6 font-semibold uppercase tracking-wide px-1"
                        )
                        ui.html(
                            '<pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;'
                            'border-radius:4px;margin-bottom:6px;white-space:pre-wrap;word-break:break-word">'
                            + html.escape(prompt or "—")
                            + "</pre>"
                        )

                        if _guardrail_side == "before":
                            self._render_guardrail_event_block(
                                {
                                    "side": "before",
                                    "explanation": _guardrail_explanation,
                                    "categories": _guardrail_categories,
                                }
                            )
                        else:
                            ui.label("TARGET RESPONSE").classes(
                                "text-[10px] text-grey-6 font-semibold uppercase tracking-wide px-1"
                            )
                            ui.html(
                                '<pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;'
                                'border-radius:4px;white-space:pre-wrap;word-break:break-word">'
                                + html.escape(response or "No response recorded.")
                                + "</pre>"
                            )
                            if _guardrail_side:
                                self._render_guardrail_event_block(
                                    {
                                        "side": _guardrail_side,
                                        "explanation": _guardrail_explanation,
                                        "categories": _guardrail_categories,
                                    }
                                )

                        if iteration < steps[-1]["iteration"]:
                            ui.separator().classes("mt-2 mb-0")

                if not detail_mode:
                    self._wire_expand_toggle(body_col)

    # ── AutoDAN-Turbo ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_autodan_traces(traces: list[dict]) -> list[dict]:
        """Parse AutoDAN-Turbo traces into per-epoch step rows."""
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        steps: dict[tuple, dict] = {}
        warmup_summary: dict | None = None

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            step_name = str(content.get("step_name") or "")
            # AutoDAN-Turbo stores all payload fields directly in content
            # (no nested "metadata" dict), so read epoch/iteration/stream
            # from content directly.
            metadata = content.get("metadata") or {}

            # phase / subphase are stored directly in content by emit_phase_trace.
            # step_name is NOT persisted to the backend, so we cannot use it for
            # phase detection when reading DB traces.
            phase_raw = str(content.get("phase") or "").upper()
            subphase_raw = str(content.get("subphase") or "").upper()
            if not phase_raw:
                # Legacy fallback: derive from step_name for locally-stored traces
                phase_raw = "WARMUP" if "warmup" in step_name.lower() else "LIFELONG"

            if phase_raw == "WARMUP" and subphase_raw == "SUMMARIZATION":
                warmup_summary = {
                    "phase": "WARMUP_SUMMARY",
                    "iteration": int(
                        content.get("iteration") or metadata.get("iteration") or 0
                    ),
                    "epoch": -1,
                    "stream": -1,
                    "strategy": (content.get("strategy") or metadata.get("strategy")),
                    "score": None,
                    "is_best": False,
                    "generated_prompt": None,
                    "target_response": None,
                    "assessment": None,
                    "score_delta": None,
                }
                continue

            # Skip bookend traces — no display content
            if subphase_raw in ("PHASE_START", "PHASE_END", "SKIP_FINALIZED"):
                continue

            phase = phase_raw if phase_raw in ("WARMUP", "LIFELONG") else "LIFELONG"
            # Payload fields are top-level in content; prefer them over the
            # (usually empty) nested metadata dict.
            iteration = int(content.get("iteration") or metadata.get("iteration") or 0)
            epoch = int(content.get("epoch") or metadata.get("epoch") or 0)
            stream = int(content.get("stream") or metadata.get("stream") or 0)
            # Use (phase, iteration, epoch, stream) so each inner-loop step
            # gets its own row while still merging the 3 sub-traces
            # (Generation / Target Query / Scoring) that share the same key.
            key = (phase, iteration, epoch, stream)

            if key not in steps:
                steps[key] = {
                    "phase": phase,
                    "iteration": iteration,
                    "epoch": epoch,
                    "stream": stream,
                    "score": None,
                    "is_best": False,
                    "generated_prompt": None,
                    "target_response": None,
                    "assessment": None,
                    "strategy": None,
                    "score_delta": None,
                    "_guardrail_side": "",
                    "_guardrail_explanation": "",
                }

            step = steps[key]

            # ── Attacker / jailbreak prompt ───────────────────────────────
            # Traces store the final prompt directly as "generated_prompt".
            # Older/router-style traces may nest it under request["prompt"].
            if content.get("generated_prompt"):
                step["generated_prompt"] = str(content["generated_prompt"])
            else:
                req = content.get("request") or {}
                if isinstance(req, dict) and req.get("prompt"):
                    step["generated_prompt"] = req["prompt"]

            # ── Target response ───────────────────────────────────────────
            # Traces store it as "target_response"; legacy path uses "response".
            raw_resp = content.get("target_response") or content.get("response")
            if raw_resp:
                raw_resp, _adan_g_side, _adan_g_expl, _adan_g_cats = (
                    DashboardPage._extract_guardrail_from_response(raw_resp)
                )
                if _adan_g_side:
                    step["_guardrail_side"] = _adan_g_side
                    step["_guardrail_explanation"] = _adan_g_expl
                    step["_guardrail_categories"] = _adan_g_cats
                if raw_resp is not None:
                    if isinstance(raw_resp, dict):
                        step["target_response"] = (
                            raw_resp.get("generated_text")
                            or raw_resp.get("completion")
                            or str(raw_resp)
                        )
                    else:
                        step["target_response"] = str(raw_resp)

            # ── Score / assessment / strategy ─────────────────────────────
            score_raw = content.get("score") or metadata.get("judge_score")
            if score_raw is not None:
                try:
                    step["score"] = float(score_raw)
                except (TypeError, ValueError):
                    pass

            if content.get("assessment"):
                step["assessment"] = str(content["assessment"])
            if content.get("strategy"):
                step["strategy"] = content["strategy"]

            score_delta_raw = content.get("score_delta") or metadata.get("score_delta")
            if score_delta_raw is not None:
                try:
                    step["score_delta"] = float(score_delta_raw)
                except (TypeError, ValueError):
                    pass

        _phase_order = {"WARMUP": 0, "LIFELONG": 1}
        result = [
            steps[k]
            for k in sorted(
                steps,
                key=lambda t: (_phase_order.get(t[0], 9), t[1], t[2], t[3]),
            )
        ]
        for phase_label in ("WARMUP", "LIFELONG"):
            phase_steps = [s for s in result if s["phase"] == phase_label]
            scored = [s for s in phase_steps if s["score"] is not None]
            if scored:
                best = max(scored, key=lambda s: s["score"])  # type: ignore[arg-type]
                best["is_best"] = True

        if warmup_summary:
            last_warmup_idx = -1
            for i, s in enumerate(result):
                if s["phase"] == "WARMUP":
                    last_warmup_idx = i
            result.insert(last_warmup_idx + 1, warmup_summary)

        return result

    def _render_autodan_goal_card(
        self, row: dict, steps: list[dict], detail_mode: bool = False
    ) -> None:
        """Render AutoDAN-Turbo goal card as a phase-divided conversation."""
        with self._goal_card_shell(row, detail_mode):
            if not steps:
                ui.label("No AutoDAN-Turbo trace data recorded.").classes(
                    "text-sm text-grey-6"
                )
                return

            with ui.column().classes("w-full gap-3 mt-2") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                phase_groups: list[tuple[str, list[dict]]] = []
                for step in steps:
                    phase = step["phase"]
                    display_phase = (
                        "WARMUP"
                        if phase in ("WARMUP", "WARMUP_SUMMARY")
                        else "LIFELONG"
                    )
                    if not phase_groups or phase_groups[-1][0] != display_phase:
                        phase_groups.append((display_phase, []))
                    phase_groups[-1][1].append(step)

                for display_phase, phase_steps in phase_groups:
                    _is_warmup = display_phase == "WARMUP"
                    _phase_border = (
                        "border-blue-grey-3" if _is_warmup else "border-teal-3"
                    )
                    _phase_header_bg = (
                        "background:#eceff1" if _is_warmup else "background:#e0f2f1"
                    )
                    _phase_label_text = "Warm-Up" if _is_warmup else "Lifelong"
                    _phase_icon = "explore" if _is_warmup else "loop"

                    with ui.card().tight().classes(f"w-full border {_phase_border}"):
                        with (
                            ui.row()
                            .classes("items-center gap-2 px-3 py-2 w-full")
                            .style(_phase_header_bg)
                        ):
                            ui.icon(_phase_icon, size="xs").classes("text-grey-7")
                            ui.label(_phase_label_text).classes(
                                "text-xs font-bold text-grey-8 uppercase tracking-widest"
                            )

                        with ui.column().classes("w-full gap-2 p-2"):
                            # Split WARMUP_SUMMARY out first, then group the
                            # remaining steps by iteration so each outer-loop
                            # iteration gets a single collapsible header with
                            # its epoch cards nested inside.
                            _summary_steps = [
                                s for s in phase_steps if s["phase"] == "WARMUP_SUMMARY"
                            ]
                            _iter_steps = [
                                s for s in phase_steps if s["phase"] != "WARMUP_SUMMARY"
                            ]

                            # Build ordered iteration groups preserving sort order
                            _iter_groups: list[tuple[int, list[dict]]] = []
                            for _step in _iter_steps:
                                _it = _step.get("iteration", 0)
                                if not _iter_groups or _iter_groups[-1][0] != _it:
                                    _iter_groups.append((_it, []))
                                _iter_groups[-1][1].append(_step)

                            for _iter_num, _epoch_steps in _iter_groups:
                                # Iteration sub-header (only shown when there
                                # are multiple iterations in this phase)
                                _iter_has_best = any(
                                    s.get("is_best") for s in _epoch_steps
                                )
                                _iter_best_score = max(
                                    (
                                        s["score"]
                                        for s in _epoch_steps
                                        if s.get("score") is not None
                                    ),
                                    default=None,
                                )
                                if len(_iter_groups) > 1:
                                    with ui.row().classes(
                                        "items-center gap-2 px-1 py-0.5"
                                    ):
                                        ui.label(f"Iteration {_iter_num + 1}").classes(
                                            "text-[11px] font-bold text-grey-6 uppercase tracking-widest"
                                        )
                                        if _iter_has_best:
                                            _ib_str = (
                                                f"  best {_iter_best_score:.1f} / 10"
                                                if _iter_best_score is not None
                                                else ""
                                            )
                                            ui.badge(
                                                f"Best{_ib_str}", color="positive"
                                            ).classes("text-xs")

                                for step in _epoch_steps:
                                    score = step["score"]
                                    is_best = step["is_best"]
                                    generated_prompt = step["generated_prompt"]
                                    target_response = step["target_response"]
                                    assessment = step.get("assessment") or ""
                                    strategy = step.get("strategy")
                                    score_delta = step.get("score_delta")
                                    _adan_g_side = step.get("_guardrail_side") or ""
                                    _adan_g_expl = (
                                        step.get("_guardrail_explanation") or ""
                                    )
                                    _epoch_border = (
                                        "border-positive"
                                        if is_best
                                        else "border-grey-3"
                                    )

                                    with (
                                        ui.card()
                                        .tight()
                                        .classes(f"w-full border {_epoch_border}")
                                    ):
                                        with (
                                            ui.row()
                                            .classes(
                                                "items-center gap-2 px-3 py-1.5 w-full"
                                            )
                                            .style("background:#f5f5f5")
                                        ):
                                            _score_str = (
                                                f" — score {score:.1f} / 10"
                                                if score is not None
                                                else ""
                                            )
                                            _ep = step.get("epoch", 0)
                                            # Only show "Epoch N" when there
                                            # are multiple epochs per iteration
                                            _ep_count = max(
                                                (
                                                    s.get("epoch", 0)
                                                    for s in _epoch_steps
                                                ),
                                                default=0,
                                            )
                                            if _ep_count > 0:
                                                _step_label = (
                                                    f"Epoch {_ep + 1}{_score_str}"
                                                )
                                            else:
                                                _step_label = f"Iteration {_iter_num + 1}{_score_str}"
                                            ui.label(_step_label).classes(
                                                "text-xs font-semibold text-grey-7 uppercase tracking-wide"
                                            )
                                            if is_best:
                                                ui.badge(
                                                    "Best", color="positive"
                                                ).classes("text-xs")
                                            ui.space()

                                        with ui.column().classes("p-3 gap-2"):
                                            ui.label("Attacker").classes(
                                                "text-[10px] font-semibold text-grey-5 uppercase tracking-wide"
                                            )
                                            ui.html(
                                                '<pre style="font-size:11px;padding:8px;background:white;'
                                                "border:1px solid #e0e0e0;border-radius:4px;margin:0;"
                                                'white-space:pre-wrap;word-break:break-word">'
                                                + html.escape(generated_prompt or "—")
                                                + "</pre>"
                                            )

                                            if _adan_g_side == "before":
                                                self._render_guardrail_event_block(
                                                    {
                                                        "side": "before",
                                                        "explanation": _adan_g_expl,
                                                    }
                                                )
                                            else:
                                                ui.label("Target response").classes(
                                                    "text-[10px] font-semibold text-grey-5 uppercase tracking-wide"
                                                )
                                                ui.html(
                                                    '<pre style="font-size:11px;padding:8px;background:white;'
                                                    "border:1px solid #e0e0e0;border-radius:4px;margin:0;"
                                                    'white-space:pre-wrap;word-break:break-word">'
                                                    + html.escape(
                                                        target_response
                                                        or "No response recorded."
                                                    )
                                                    + "</pre>"
                                                )
                                                if _adan_g_side:
                                                    self._render_guardrail_event_block(
                                                        {
                                                            "side": _adan_g_side,
                                                            "explanation": _adan_g_expl,
                                                        }
                                                    )

                                            if assessment:
                                                ui.label("Scorer assessment").classes(
                                                    "text-[10px] font-semibold text-grey-5 uppercase tracking-wide"
                                                )
                                                ui.html(
                                                    '<pre style="font-size:11px;padding:8px;background:#fff8e1;'
                                                    "border:1px solid #ffe082;border-radius:4px;margin:0;"
                                                    'white-space:pre-wrap;word-break:break-word">'
                                                    + html.escape(assessment)
                                                    + "</pre>"
                                                )

                                            if strategy is not None and isinstance(
                                                strategy, dict
                                            ):
                                                s_name = strategy.get("Strategy")
                                                s_defn = strategy.get("Definition")
                                                if s_name or s_defn:
                                                    _delta_str = (
                                                        f" (+{score_delta:.1f})"
                                                        if score_delta
                                                        else ""
                                                    )
                                                    ui.label(
                                                        f"New strategy{_delta_str}"
                                                    ).classes(
                                                        "text-[10px] font-semibold text-indigo-6 uppercase tracking-wide"
                                                    )
                                                    _strat_text = ""
                                                    if s_name:
                                                        _strat_text += (
                                                            f"Strategy: {s_name}\n"
                                                        )
                                                    if s_defn:
                                                        _strat_text += (
                                                            f"Definition: {s_defn}"
                                                        )
                                                    ui.html(
                                                        '<pre style="font-size:11px;padding:8px;background:#f3f4fd;'
                                                        "border:1px solid #c5cae9;border-radius:4px;margin:0;"
                                                        'white-space:pre-wrap;word-break:break-word">'
                                                        + html.escape(
                                                            _strat_text.strip()
                                                        )
                                                        + "</pre>"
                                                    )

                            # Render WARMUP_SUMMARY cards (strategy extracted
                            # by the summarizer after the warmup loop)
                            for _ws in _summary_steps:
                                _ws_strategy = _ws.get("strategy") or {}
                                _ws_name = (
                                    _ws_strategy.get("Strategy")
                                    if isinstance(_ws_strategy, dict)
                                    else None
                                )
                                _ws_defn = (
                                    _ws_strategy.get("Definition")
                                    if isinstance(_ws_strategy, dict)
                                    else None
                                )
                                if _ws_name or _ws_defn:
                                    with (
                                        ui.card()
                                        .tight()
                                        .classes("w-full border border-indigo-2")
                                    ):
                                        with (
                                            ui.row()
                                            .classes("items-center gap-2 px-3 py-2")
                                            .style("background:#e8eaf6")
                                        ):
                                            ui.icon("summarize", size="xs").classes(
                                                "text-indigo-6"
                                            )
                                            ui.label(
                                                "Summarizer — Strategy Extracted"
                                            ).classes(
                                                "text-xs font-bold text-indigo-8 uppercase tracking-widest"
                                            )
                                        with ui.column().classes("p-3 gap-1"):
                                            _strat_text = ""
                                            if _ws_name:
                                                _strat_text += f"Strategy: {_ws_name}\n"
                                            if _ws_defn:
                                                _strat_text += f"Definition: {_ws_defn}"
                                            ui.html(
                                                '<pre style="font-size:11px;padding:8px;background:white;'
                                                "border:1px solid #c5cae9;border-radius:4px;margin:0;"
                                                'white-space:pre-wrap;word-break:break-word">'
                                                + html.escape(_strat_text.strip())
                                                + "</pre>"
                                            )

            if not detail_mode:
                self._wire_expand_toggle(body_col)

    # ── AdvPrefix ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_advprefix_traces(
        traces: list[dict],
    ) -> tuple[list[dict], dict]:
        """Parse AdvPrefix traces into per-prefix rows grouped by meta_prefix."""
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        gen_stats: dict = {
            "raw_generated": 0,
            "after_phase1": 0,
            "after_phase2": 0,
        }

        candidates: dict[str, dict] = {}

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            if "candidates" not in content and "raw_generated" not in content:
                continue
            gen_stats["raw_generated"] += int(content.get("raw_generated") or 0)
            gen_stats["after_phase1"] += int(content.get("after_phase1_filtering") or 0)
            gen_stats["after_phase2"] += int(content.get("after_phase2_filtering") or 0)
            for cand in content.get("candidates") or []:
                if not isinstance(cand, dict):
                    continue
                prefix_text = str(cand.get("prefix") or "")
                if not prefix_text:
                    continue
                if prefix_text not in candidates:
                    _raw_mp = str(cand.get("meta_prefix") or "")
                    _mp_parts = [p.strip() for p in _raw_mp.split(",") if p.strip()]
                    _seen: set[str] = set()
                    _mp_dedup: list[str] = []
                    for _p in _mp_parts:
                        if _p not in _seen:
                            _seen.add(_p)
                            _mp_dedup.append(_p)
                    _meta_prefix_str = ", ".join(_mp_dedup)
                    candidates[prefix_text] = {
                        "prefix": prefix_text,
                        "_meta_prefix": _meta_prefix_str,
                        "_nll": cand.get("prefix_nll"),
                        "completion": "",
                        "_bucket": "pending",
                        "result": "Pending",
                        "_filtered": "Pending",
                        "_error": "",
                    }

        completion_by_prefix: dict[str, dict] = {}

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            if str(content.get("step_name") or "") != "Target Completion":
                continue

            metadata = content.get("metadata") or {}
            full_prefix = str(metadata.get("prefix") or "")
            lookup_key = full_prefix[:300]
            error_msg = metadata.get("error_message")
            surrogate = str(metadata.get("surrogate_attack_prompt") or "")

            response = content.get("response")
            response, _adv_g_side, _adv_g_expl, _adv_g_cats = (
                DashboardPage._extract_guardrail_from_response(response)
            )
            if isinstance(response, dict):
                completion = (
                    response.get("generated_text") or response.get("completion") or ""
                )
            elif isinstance(response, str):
                completion = response
            elif response is None:
                completion = ""
            else:
                completion = str(response)

            # error_message may carry the guardrail block description when the
            # guardrail info was not embedded in the response object itself
            # (e.g. for runs recorded before guardrail_event propagation was added).
            if not _adv_g_side and error_msg:
                _emsg_lower = str(error_msg).lower()
                if (
                    "before_guardrail" in _emsg_lower
                    or "before guardrail" in _emsg_lower
                ):
                    _adv_g_side = "before"
                    _adv_g_expl = str(error_msg)
                    error_msg = None
                elif (
                    "after_guardrail" in _emsg_lower or "after guardrail" in _emsg_lower
                ):
                    _adv_g_side = "after"
                    _adv_g_expl = str(error_msg)
                    error_msg = None

            if _adv_g_side:
                bucket = "mitigated"
                result_label = "Mitigated"
                error_msg = None  # guardrail takes precedence over any error_msg
            elif error_msg:
                bucket = "error"
                result_label = "Error"
            elif completion:
                bucket = "mitigated"
                result_label = "Mitigated"
            else:
                bucket = "error"
                result_label = "Error"

            comp_data = {
                "prefix": full_prefix,
                "completion": completion,
                "_bucket": bucket,
                "result": result_label,
                "_filtered": "No",
                "_error": str(error_msg) if error_msg else "",
                "_meta_prefix": "",
                "_surrogate": surrogate,
                "_guardrail_side": _adv_g_side,
                "_guardrail_explanation": _adv_g_expl,
            }
            completion_by_prefix[lookup_key] = comp_data

            if lookup_key not in candidates:
                candidates[lookup_key] = {
                    "prefix": full_prefix,
                    "_meta_prefix": "",
                    "_nll": None,
                    "completion": "",
                    "_bucket": "pending",
                    "result": "Pending",
                    "_filtered": "Pending",
                    "_error": "",
                    "_surrogate": surrogate,
                }

        rows: list[dict] = []
        for key, cand in candidates.items():
            comp = completion_by_prefix.get(key)
            if comp:
                cand["prefix"] = comp["prefix"]
                cand["completion"] = comp["completion"]
                cand["_bucket"] = comp["_bucket"]
                cand["result"] = comp["result"]
                cand["_filtered"] = comp["_filtered"]
                cand["_error"] = comp["_error"]
                cand["_surrogate"] = comp.get("_surrogate", "")
                if not cand.get("_meta_prefix") and comp["_meta_prefix"]:
                    cand["_meta_prefix"] = comp["_meta_prefix"]
                cand["_guardrail_side"] = comp.get("_guardrail_side") or ""
                cand["_guardrail_explanation"] = (
                    comp.get("_guardrail_explanation") or ""
                )
            _surrogate = cand.get("_surrogate") or ""
            _prefix = cand["prefix"]
            if _surrogate:
                if "{prefix}" in _surrogate:
                    cand["_sent_prompt"] = _surrogate.format(prefix=_prefix)
                else:
                    cand["_sent_prompt"] = _prefix + " " + _surrogate
            else:
                cand["_sent_prompt"] = _prefix
            rows.append(cand)

        rows.sort(key=lambda r: (r["_meta_prefix"], r["prefix"][:40]))
        for i, r in enumerate(rows):
            r["num"] = i + 1

        unmatched_jailbreaks = 0
        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            if str(content.get("step_name") or "") != "Evaluation":
                continue
            # Skip coordinator summary traces — they are goal-level aggregates,
            # not per-prefix evaluation signals.
            if str(content.get("evaluator") or "") == "tracking_coordinator":
                continue
            _result_val = content.get("result")
            is_success = (
                content.get("success") is True
                or content.get("is_success") is True
                or (
                    isinstance(_result_val, dict) and _result_val.get("success") is True
                )
                or (content.get("score") or 0) > 0
            )
            if not is_success:
                continue
            meta = content.get("metadata") or {}
            eval_prefix = str(meta.get("prefix") or "")
            if eval_prefix:
                eval_key = eval_prefix[:300]
                matched = False
                for r in rows:
                    if r["prefix"][:300] == eval_key:
                        r["_bucket"] = "jailbreak"
                        r["result"] = "Jailbreak"
                        matched = True
                if not matched:
                    unmatched_jailbreaks += 1
            else:
                unmatched_jailbreaks += 1

        if unmatched_jailbreaks:
            marked = 0
            for r in rows:
                if marked >= unmatched_jailbreaks:
                    break
                if r["_bucket"] in ("mitigated", "error") and not r.get(
                    "_guardrail_side"
                ):
                    r["_bucket"] = "jailbreak"
                    r["result"] = "Jailbreak"
                    marked += 1

        return rows, gen_stats

    def _render_advprefix_goal_card(
        self,
        row: dict,
        prefix_rows: list[dict],
        gen_stats: dict,
        detail_mode: bool = False,
    ) -> None:
        """Render an AdvPrefix goal card as a single flat table."""
        n_jailbreaks = sum(1 for r in prefix_rows if r["_bucket"] == "jailbreak")
        n_mitigated = sum(1 for r in prefix_rows if r["_bucket"] == "mitigated")
        n_errors = sum(1 for r in prefix_rows if r["_bucket"] == "error")
        n_pending = sum(1 for r in prefix_rows if r["_bucket"] == "pending")

        with self._goal_card_shell(row, detail_mode):
            if not prefix_rows:
                ui.label("No AdvPrefix completion data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-2 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    _raw = gen_stats.get("raw_generated", 0)
                    _p1 = gen_stats.get("after_phase1", 0)
                    _p2 = gen_stats.get("after_phase2", 0)
                    if _raw > 0:
                        with ui.row().classes(
                            "items-center gap-1 text-[10px] text-grey-5 mb-1"
                        ):
                            ui.label(f"{_raw} generated").classes("font-mono")
                            ui.label("→").classes("text-grey-4")
                            ui.label(f"{_p1} after pattern filter").classes("font-mono")
                            ui.label("→").classes("text-grey-4")
                            ui.label(f"{_p2} after CE + top-k").classes(
                                "font-mono font-semibold text-grey-7"
                            )

                    columns = [
                        {
                            "name": "num",
                            "label": "#",
                            "field": "num",
                            "align": "center",
                            "style": "width:36px",
                        },
                        {
                            "name": "meta_prefix",
                            "label": "Meta Prefix",
                            "field": "meta_prefix",
                            "align": "left",
                        },
                        {
                            "name": "result",
                            "label": "Result",
                            "field": "result",
                            "align": "center",
                            "style": "width:100px",
                        },
                    ]

                    tbl_rows = [
                        {
                            "num": r["num"],
                            "meta_prefix": r.get("_meta_prefix") or "—",
                            "result": r["result"],
                            "_bucket": r["_bucket"],
                            "_full_sent_prompt": r.get("_sent_prompt") or r["prefix"],
                            "_full_prefix": r["prefix"],
                            "_completion": r.get("completion") or "",
                            "_error": r.get("_error") or "",
                            "_guardrail_side": r.get("_guardrail_side") or "",
                            "_guardrail_explanation": r.get("_guardrail_explanation")
                            or "",
                        }
                        for r in prefix_rows
                    ]

                    tbl = (
                        ui.table(columns=columns, rows=tbl_rows, row_key="num")
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        tbl.props(
                            f":expanded-rows='{json.dumps([r['num'] for r in tbl_rows])}'"
                        )

                    tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="num" :props="props" style="font-size:10px;color:#9e9e9e">{{ props.row.num }}</q-td>
  <q-td key="meta_prefix" :props="props"
        style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px">
    {{ props.row.meta_prefix }}
  </q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row._bucket === 'jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row._bucket === 'mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else-if="props.row._bucket === 'pending'" color="grey" class="text-xs">Pending</q-badge>
    <q-badge v-else color="warning" class="text-xs">Error</q-badge>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <template v-if="props.row._full_prefix !== props.row._full_sent_prompt">
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">RAW ADVERSARIAL PREFIX</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prefix || '—' }}</pre>
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">PROMPT SENT TO TARGET</div>
        <pre style="font-size:11px;padding:8px;background:#fff8e1;border:1px solid #ffe082;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_sent_prompt }}</pre>
      </template>
      <template v-else>
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">PROMPT SENT TO TARGET</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_sent_prompt || '—' }}</pre>
      </template>
      <template v-if="props.row._bucket !== 'pending' && props.row._guardrail_side !== 'before'">
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">TARGET COMPLETION</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;white-space:pre-wrap;word-break:break-word">{{ props.row._completion || 'No completion recorded.' }}</pre>
        <div v-if="props.row._error" class="text-caption text-negative text-italic q-mt-xs">
          Error: {{ props.row._error }}
        </div>
      </template>
      <div v-else-if="props.row._bucket === 'pending'" class="text-caption text-grey-6 text-italic q-mt-xs">
        This candidate was not executed against the target model.
      </div>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-top:4px;margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">⚠ BEFORE GUARDRAIL — BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-top:4px;margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">🚫 AFTER GUARDRAIL — CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-top:4px;margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">🛡 GUARDRAIL — BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                    )

                    ui.separator().classes("mt-2")
                    with ui.row().classes("items-center gap-2 mt-2 flex-wrap"):
                        ui.label("Summary:").classes(
                            "text-xs font-semibold text-grey-6"
                        )
                        ui.label(
                            f"{len(prefix_rows)} prefix{'es' if len(prefix_rows) != 1 else ''}"
                        ).classes("text-xs text-grey-6")
                        if n_jailbreaks:
                            ui.badge(
                                f"{n_jailbreaks} Jailbreak{'s' if n_jailbreaks != 1 else ''}",
                                color="negative",
                            ).classes("text-xs")
                        if n_mitigated:
                            ui.badge(
                                f"{n_mitigated} Mitigated", color="positive"
                            ).classes("text-xs")
                        if n_errors:
                            ui.badge(
                                f"{n_errors} Error{'s' if n_errors != 1 else ''}",
                                color="warning",
                            ).classes("text-xs")
                        if n_pending:
                            ui.badge(f"{n_pending} Pending", color="grey").classes(
                                "text-xs"
                            )

                if not detail_mode:
                    self._wire_expand_toggle(body_col)

    # ── PAP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_pap_traces(traces: list[dict]) -> list[dict]:
        """Parse PAP traces into per-technique rows for the result table."""
        candidates: dict[int, dict] = {}
        evaluations: dict[int, dict] = {}

        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            meta = content.get("metadata") or {}
            display_type = meta.get("display_type") or ""
            tech_idx = meta.get("technique_index")
            if tech_idx is None:
                continue
            if display_type == "pap_candidate":
                req = content.get("request") or {}
                prompt = req.get("prompt") or "" if isinstance(req, dict) else ""
                # If prompt is empty, check if there's messages format
                if not prompt and isinstance(req, dict):
                    msgs = req.get("messages") or []
                    for m in reversed(msgs):
                        if isinstance(m, dict) and m.get("role") == "user":
                            prompt = str(m.get("content") or "")
                            break
                _cand_resp = content.get("response")
                _cand_resp_actual, _cand_g_side, _cand_g_expl, _cand_g_cats = (
                    DashboardPage._extract_guardrail_from_response(_cand_resp)
                )
                candidates[tech_idx] = {
                    "technique": meta.get("technique") or "",
                    "prompt": prompt,
                    "response": str(_cand_resp_actual) if _cand_resp_actual else "",
                    "_guardrail_side": _cand_g_side,
                    "_guardrail_explanation": _cand_g_expl,
                    "_guardrail_categories": _cand_g_cats,
                }
            elif display_type == "pap_evaluation":
                _pap_raw_resp = content.get("response")
                _pap_raw_resp, _pap_g_side, _pap_g_expl, _pap_g_cats = (
                    DashboardPage._extract_guardrail_from_response(_pap_raw_resp)
                )
                _pap_response = (
                    _pap_raw_resp.get("target_response")
                    if isinstance(_pap_raw_resp, dict)
                    else None
                )
                evaluations[tech_idx] = {
                    "is_jailbreak": bool(meta.get("is_jailbreak")),
                    "judge_score": meta.get("judge_score"),
                    "response": _pap_response or "",
                    "_guardrail_side": _pap_g_side,
                    "_guardrail_explanation": _pap_g_expl,
                }

        rows = []
        for idx in sorted(candidates):
            cand = candidates[idx]
            ev = evaluations.get(idx, {})
            technique = cand["technique"]
            prompt = cand["prompt"]
            is_jailbreak = ev.get("is_jailbreak", False)
            response = ev.get("response") or cand.get("response") or ""
            _guardrail_side = (
                ev.get("_guardrail_side") or cand.get("_guardrail_side") or ""
            )
            _guardrail_explanation = (
                ev.get("_guardrail_explanation")
                or cand.get("_guardrail_explanation")
                or ""
            )
            if _guardrail_side:
                bucket = "mitigated"
            elif is_jailbreak:
                bucket = "jailbreak"
            elif ev:
                bucket = "mitigated"
            else:
                bucket = "error"
            rows.append(
                {
                    "num": idx + 1,
                    "technique": technique,
                    "prompt_short": (prompt[:80] + "\u2026")
                    if len(prompt) > 80
                    else prompt,
                    "result": "Jailbreak"
                    if bucket == "jailbreak"
                    else "Mitigated"
                    if bucket == "mitigated"
                    else "Error",
                    "_bucket": bucket,
                    "_full_prompt": prompt,
                    "_response": response,
                    "_guardrail_side": _guardrail_side,
                    "_guardrail_explanation": _guardrail_explanation,
                }
            )
        return rows

    def _render_pap_goal_card(
        self, row: dict, technique_rows: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a per-goal PAP result card with a per-technique table."""
        with self._goal_card_shell(row, detail_mode):
            if not technique_rows:
                ui.label("No PAP technique results recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-2 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    pap_cols = [
                        {
                            "name": "technique",
                            "label": "Technique",
                            "field": "technique",
                            "align": "left",
                        },
                        {
                            "name": "result",
                            "label": "Result",
                            "field": "result",
                            "align": "center",
                            "style": "width:100px",
                        },
                    ]

                    pap_tbl = (
                        ui.table(columns=pap_cols, rows=technique_rows, row_key="num")
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        pap_tbl.props(
                            f":expanded-rows='{json.dumps([r['num'] for r in technique_rows])}'"
                        )

                    pap_tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="technique" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:360px">
    {{ props.row.technique }}
  </q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row._bucket === 'jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row._bucket === 'mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else color="warning" class="text-xs">Error</q-badge>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">PROMPT SENT TO TARGET</div>
      <pre v-if="props.row._full_prompt" style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                  border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prompt }}</pre>
      <div v-else class="text-caption text-italic text-grey-5 q-mb-sm">Attacker failed to generate a persuasive prompt for this technique.</div>
      <template v-if="props.row._full_prompt && props.row._guardrail_side !== 'before'">
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">TARGET RESPONSE</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._response || 'No response recorded.' }}</pre>
      </template>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">⚠ BEFORE GUARDRAIL — BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">🚫 AFTER GUARDRAIL — CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">🛡 GUARDRAIL — BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                    )

                if not detail_mode:
                    self._wire_expand_toggle(body_col)

    # ── TAP ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_tap_traces(traces: list[dict]) -> tuple[list[dict], dict[int, dict]]:
        """Parse TAP traces into a list of candidate node dicts."""
        nodes: list[dict] = []
        seen_ids: set[str] = set()
        _interaction_counts: dict[int, int] = {}
        _summary_counts: dict[int, int] = {}

        def _add(node: dict) -> None:
            sid = node.get("self_id") or ""
            if sid and sid in seen_ids:
                return
            if sid:
                seen_ids.add(sid)
            nodes.append(node)

        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content")
            if not isinstance(content, dict):
                continue

            step_name = str(content.get("step_name") or "")

            if "Depth" in step_name and "Candidate" in step_name:
                meta = content.get("metadata") or {}
                req = content.get("request") or {}
                prompt = req.get("prompt", "") if isinstance(req, dict) else ""
                resp = content.get("response")
                resp, _tap_g_side, _tap_g_expl, _tap_g_cats = (
                    DashboardPage._extract_guardrail_from_response(resp)
                )
                response = str(resp) if resp not in (None, "") else ""
                depth_level = int(meta.get("iteration") or 0)
                _interaction_counts[depth_level] = (
                    _interaction_counts.get(depth_level, 0) + 1
                )
                _add(
                    {
                        "depth": depth_level,
                        "branch_index": meta.get("branch_index"),
                        "stream_index": meta.get("stream_index"),
                        "self_id": meta.get("self_id", ""),
                        "parent_id": meta.get("parent_id"),
                        "prompt": prompt,
                        "response": response,
                        "judge_score": meta.get("judge_score"),
                        "on_topic": meta.get("on_topic_score"),
                        "improvement": str(meta.get("improvement") or ""),
                        "_guardrail_side": _tap_g_side,
                        "_guardrail_explanation": _tap_g_expl,
                        "_guardrail_categories": _tap_g_cats,
                    }
                )
                continue

            if "Depth" in step_name and "Summary" in step_name:
                depth_level = int(content.get("depth") or 0)
                branches = [
                    b for b in (content.get("branches") or []) if isinstance(b, dict)
                ]
                _summary_counts[depth_level] = len(branches)
                for branch in branches:
                    _b_resp = branch.get("response")
                    _b_resp, _b_g_side, _b_g_expl, _b_g_cats = (
                        DashboardPage._extract_guardrail_from_response(_b_resp)
                    )
                    _add(
                        {
                            "depth": depth_level,
                            "branch_index": branch.get("branch_index"),
                            "stream_index": branch.get("stream_index"),
                            "self_id": branch.get("self_id", ""),
                            "parent_id": branch.get("parent_id"),
                            "prompt": str(branch.get("prompt") or ""),
                            "response": str(_b_resp or ""),
                            "judge_score": branch.get("judge_score"),
                            "on_topic": branch.get("on_topic_score"),
                            "improvement": str(branch.get("improvement") or ""),
                            "_guardrail_side": _b_g_side,
                            "_guardrail_explanation": _b_g_expl,
                            "_guardrail_categories": _b_g_cats,
                        }
                    )
                continue

            if not step_name and "depth" in content and "branches" in content:
                depth_level = int(content.get("depth") or 0)
                branches = [
                    b for b in (content.get("branches") or []) if isinstance(b, dict)
                ]
                _summary_counts[depth_level] = len(branches)
                for branch in branches:
                    _b_resp2 = branch.get("response")
                    _b_resp2, _b2_g_side, _b2_g_expl, _b2_g_cats = (
                        DashboardPage._extract_guardrail_from_response(_b_resp2)
                    )
                    _add(
                        {
                            "depth": depth_level,
                            "branch_index": branch.get("branch_index"),
                            "stream_index": branch.get("stream_index"),
                            "self_id": branch.get("self_id", ""),
                            "parent_id": branch.get("parent_id"),
                            "prompt": str(branch.get("prompt") or ""),
                            "response": str(_b_resp2 or ""),
                            "judge_score": branch.get("judge_score"),
                            "on_topic": branch.get("on_topic_score"),
                            "improvement": str(branch.get("improvement") or ""),
                            "_guardrail_side": _b2_g_side,
                            "_guardrail_explanation": _b2_g_expl,
                            "_guardrail_categories": _b2_g_cats,
                        }
                    )
                continue

        if not nodes:
            eval_idx = 0
            for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
                content = td.get("content")
                if not isinstance(content, dict):
                    continue
                if content.get("step_name") != "Evaluation":
                    continue
                evaluator = str(content.get("evaluator") or "")
                if evaluator == "tracking_coordinator":
                    continue
                meta = content.get("metadata") or {}
                prompt = str(meta.get("prefix") or "")
                response = str(meta.get("completion") or "")
                if not prompt and not response:
                    continue
                score_raw = content.get("score")
                try:
                    score_val = int(float(score_raw)) if score_raw is not None else None
                except (TypeError, ValueError):
                    score_val = None
                # Binary evaluators (HarmBench, JailbreakBench) return 0/1;
                # normalize to the 1–10 TAP scale so display is consistent
                # with scores from Candidate traces.
                _ev_lower = evaluator.lower()
                if score_val is not None and (
                    "harmbench" in _ev_lower or "jailbreakbench" in _ev_lower
                ):
                    score_val = 1 if score_val == 0 else 10
                eval_idx += 1
                nodes.append(
                    {
                        "depth": 0,
                        "branch_index": eval_idx - 1,
                        "stream_index": 0,
                        "self_id": "",
                        "parent_id": None,
                        "prompt": prompt,
                        "response": response,
                        "judge_score": score_val,
                        "on_topic": None,
                        "improvement": "",
                        "_guardrail_side": "",
                        "_guardrail_explanation": "",
                        "_guardrail_categories": [],
                    }
                )

        depth_stats: dict[int, dict] = {}
        all_depths = set(_interaction_counts) | set(_summary_counts)
        for _d in all_depths:
            _gen = _interaction_counts.get(_d)
            _surv = _summary_counts.get(_d)
            depth_stats[_d] = {
                "generated": _gen,
                "survived": _surv,
                "pruned": (_gen - _surv)
                if (_gen is not None and _surv is not None)
                else None,
            }

        return nodes, depth_stats

    def _render_tap_goal_card(
        self,
        row: dict,
        nodes: list[dict],
        depth_stats: dict[int, dict] | None = None,
        detail_mode: bool = False,
    ) -> None:
        """Render a TAP goal card: one table per depth."""
        with self._goal_card_shell(row, detail_mode):
            if not nodes:
                ui.label("No TAP candidate data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                by_depth: dict[int, list[dict]] = defaultdict(list)
                for n in nodes:
                    by_depth[n.get("depth") or 0].append(n)

                _global_num = 0
                _id_to_num: dict[str, int] = {}
                for depth_level in sorted(by_depth.keys()):
                    depth_nodes = by_depth[depth_level]
                    depth_nodes.sort(
                        key=lambda x: (
                            x.get("stream_index") or 0,
                            x.get("branch_index") or 0,
                        )
                    )
                    for n in depth_nodes:
                        _global_num += 1
                        n["_global_num"] = _global_num
                        sid = n.get("self_id") or ""
                        if sid:
                            _id_to_num[sid] = _global_num
                for n in nodes:
                    pid = n.get("parent_id") or ""
                    n["_parent_num"] = _id_to_num.get(pid)

                with ui.column().classes("w-full gap-2 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    for depth_level in sorted(by_depth.keys()):
                        depth_nodes = by_depth[depth_level]
                        _ds = (depth_stats or {}).get(depth_level, {})
                        _n_cands = len(depth_nodes)
                        _cand_label = f"{_n_cands} candidate{'s' if _n_cands != 1 else ''} after pruning"
                        _depth_header = (
                            "Final Evaluation"
                            if depth_level == 0
                            else f"Depth {depth_level}"
                        )
                        with ui.row().classes("items-center gap-2 mt-3 mb-0.5 px-1"):
                            ui.label(_depth_header).classes(
                                "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                            )
                            ui.badge(_cand_label, color="grey-5").classes("text-xs")

                        rows_data = []
                        for idx, n in enumerate(depth_nodes):
                            score = n.get("judge_score")
                            on_topic = n.get("on_topic")
                            prompt_text = n.get("prompt") or ""
                            parent_num = n.get("_parent_num")
                            _s_str = (
                                f"{int(float(score))}/10" if score is not None else "—"
                            )
                            rows_data.append(
                                {
                                    "_num": n["_global_num"],
                                    "parent_str": str(parent_num)
                                    if parent_num is not None
                                    else "—",
                                    "prompt_short": (prompt_text[:80] + "…")
                                    if len(prompt_text) > 80
                                    else prompt_text or "—",
                                    "score_val": float(score)
                                    if score is not None
                                    else -1,
                                    "score_str": _s_str,
                                    "on_topic_str": (
                                        "yes"
                                        if on_topic is not None
                                        and int(float(on_topic)) >= 1
                                        else "no"
                                        if on_topic is not None
                                        else "—"
                                    ),
                                    "_on_topic": on_topic,
                                    "_full_prompt": prompt_text,
                                    "_response": n.get("response") or "",
                                    "_guardrail_side": n.get("_guardrail_side") or "",
                                    "_guardrail_explanation": n.get(
                                        "_guardrail_explanation"
                                    )
                                    or "",
                                }
                            )

                        columns = [
                            {
                                "name": "_num",
                                "label": "#",
                                "field": "_num",
                                "align": "center",
                                "style": "width:40px",
                            },
                            {
                                "name": "parent_str",
                                "label": "Parent",
                                "field": "parent_str",
                                "align": "center",
                                "style": "width:55px",
                            },
                            {
                                "name": "prompt_short",
                                "label": "Prompt",
                                "field": "prompt_short",
                                "align": "left",
                            },
                            {
                                "name": "on_topic_str",
                                "label": "On-topic",
                                "field": "on_topic_str",
                                "align": "center",
                                "style": "width:80px",
                            },
                            {
                                "name": "score_str",
                                "label": "Score",
                                "field": "score_str",
                                "align": "center",
                                "style": "width:80px",
                            },
                        ]

                        tbl = (
                            ui.table(columns=columns, rows=rows_data, row_key="_num")
                            .classes("w-full text-xs")
                            .props("dense flat")
                        )
                        if detail_mode:
                            tbl.props(
                                f":expanded-rows='{json.dumps([r['_num'] for r in rows_data])}'"
                            )

                        tbl.add_slot(
                            "body",
                            r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="_num" :props="props" class="text-center text-grey-6">{{ props.row._num }}</q-td>
  <q-td key="parent_str" :props="props" class="text-center text-grey-5">{{ props.row.parent_str }}</q-td>
  <q-td key="prompt_short" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:360px">
    {{ props.row.prompt_short }}
  </q-td>
  <q-td key="on_topic_str" :props="props" class="text-center">
    <span class="text-grey-7">{{ props.row.on_topic_str }}</span>
  </q-td>
  <q-td key="score_str" :props="props" class="text-center">
    <span class="text-grey-7">{{ props.row.score_str }}</span>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">PROMPT SENT TO TARGET</div>
      <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                  border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prompt || '\u2014' }}</pre>
      <template v-if="props.row._guardrail_side !== 'before'">
        <div class="text-caption text-weight-bold text-uppercase text-grey-6 q-mb-xs">TARGET RESPONSE</div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._response || 'No response recorded.' }}</pre>
      </template>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">⚠ BEFORE GUARDRAIL — BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">🚫 AFTER GUARDRAIL — CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">🛡 GUARDRAIL — BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                        )

                if not detail_mode:
                    self._wire_expand_toggle(body_col)

    # ── Generic / fallback ────────────────────────────────────────────────────

    @staticmethod
    def _extract_prompt_response_from_traces(
        traces: list[dict],
    ) -> tuple[str, str]:
        """Extract the best (prompt, response) pair from generic attack traces."""
        best_req = ""
        best_resp = ""
        fallback_req = ""
        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            req, resp = DashboardPage._extract_request_response_candidates(content)
            req_str = (
                json.dumps(req, indent=2)
                if isinstance(req, (dict, list))
                else str(req)
                if req not in (None, "")
                else ""
            )
            resp_str = (
                json.dumps(resp, indent=2)
                if isinstance(resp, (dict, list))
                else str(resp)
                if resp not in (None, "")
                else ""
            )
            if req_str and resp_str:
                best_req = req_str
                best_resp = resp_str
            elif req_str:
                fallback_req = req_str
        if best_req:
            return best_req, best_resp
        if fallback_req:
            return fallback_req, "(no response recorded)"
        return "(not available)", "(not available)"

    def _render_generic_goal_card(
        self,
        row: dict,
        request_text: str,
        response_text: str,
        detail_mode: bool = False,
        guardrail_event: dict | None = None,
    ) -> None:
        """Render a per-goal result card for non-specific attacks."""
        with self._goal_card_shell(row, detail_mode):
            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                ui.label("PROMPT SENT TO TARGET").classes(
                    "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                )
                ui.html(
                    '<pre style="font-size:11px;padding:8px;background:white;'
                    "border:1px solid #e0e0e0;border-radius:4px;margin-bottom:8px;"
                    'white-space:pre-wrap;word-break:break-word">'
                    + html.escape(request_text or "\u2014")
                    + "</pre>"
                )

                _g_side = (guardrail_event or {}).get("side") or ""
                if _g_side == "before":
                    self._render_guardrail_event_block(guardrail_event)  # type: ignore[arg-type]
                else:
                    ui.label("TARGET RESPONSE").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    ui.html(
                        '<pre style="font-size:11px;padding:8px;background:white;'
                        "border:1px solid #e0e0e0;border-radius:4px;"
                        'white-space:pre-wrap;word-break:break-word">'
                        + html.escape(response_text or "No response recorded.")
                        + "</pre>"
                    )
                    if _g_side:
                        self._render_guardrail_event_block(guardrail_event)  # type: ignore[arg-type]

            if not detail_mode:
                self._wire_expand_toggle(body_col)

    async def _load_attack_specific_traces(
        self, row: dict, container: ui.column, attack_str: str
    ) -> None:
        """Load traces and render attack-specific goal card in detail_mode=True."""
        try:
            result_id = row.get("id")
            if not result_id:
                container.clear()
                with container:
                    ui.label("No result ID available.").classes("text-sm text-grey-6")
                return

            traces_raw = self.backend.list_traces(result_id=UUID(result_id))
            serialized_traces = [_serialize(t) for t in traces_raw]

            container.clear()
            atk = attack_str.lower()

            with container:
                if atk == "baseline":
                    detail_data = self._parse_baseline_traces(
                        serialized_traces, str(row.get("goal") or "")
                    )
                    self._render_baseline_goal_card(row, detail_data, detail_mode=True)
                elif atk == "bon":
                    detail_data = self._parse_bon_traces(serialized_traces)
                    self._render_bon_goal_card(row, detail_data, detail_mode=True)
                elif atk == "pap":
                    detail_data = self._parse_pap_traces(serialized_traces)
                    self._render_pap_goal_card(row, detail_data, detail_mode=True)
                elif atk == "pair":
                    detail_data = self._parse_pair_traces(serialized_traces)
                    self._render_pair_goal_card(row, detail_data, detail_mode=True)
                elif atk == "tap":
                    nodes, depth_stats = self._parse_tap_traces(serialized_traces)
                    self._render_tap_goal_card(
                        row, nodes, depth_stats, detail_mode=True
                    )
                elif atk == "advprefix":
                    prefix_rows, gen_stats = self._parse_advprefix_traces(
                        serialized_traces
                    )
                    self._render_advprefix_goal_card(
                        row, prefix_rows, gen_stats, detail_mode=True
                    )
                elif atk == "autodanturbo":
                    detail_data = self._parse_autodan_traces(serialized_traces)
                    self._render_autodan_goal_card(row, detail_data, detail_mode=True)
                else:
                    req_text, resp_text = self._extract_prompt_response_from_traces(
                        serialized_traces
                    )
                    # Detect guardrail event for the generic case
                    _generic_guardrail: dict | None = None
                    for _td in serialized_traces:
                        _r = (_td.get("content") or {}).get("response")
                        if isinstance(_r, dict) and _r.get("side") in (
                            "before",
                            "after",
                            "unknown",
                        ):
                            _generic_guardrail = _r
                            break
                    self._render_generic_goal_card(
                        row,
                        req_text,
                        resp_text,
                        detail_mode=True,
                        guardrail_event=_generic_guardrail,
                    )

        except Exception as exc:
            container.clear()
            with container:
                with ui.row().classes("gap-2 items-center py-4"):
                    ui.icon("error_outline", color="negative")
                    ui.label(f"Error loading traces: {exc}").classes(
                        "text-sm text-negative"
                    )

    def _render_trace_tabs_section(
        self,
        title: str,
        steps: list[dict],
        group_key: str,
    ) -> None:
        """Render one semantic trace section with tabbed step navigation."""
        if not steps:
            return

        with ui.column().classes("w-full gap-2 pb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label(title).classes("text-sm font-semibold")
                ui.badge(str(len(steps)), color="grey-6").classes("text-xs")

            first_name = f"{group_key}-{steps[0].get('sequence', 1)}"
            with (
                ui.tabs()
                .props("dense align=left no-caps inline-label")
                .classes("w-full") as tabs
            ):
                for step in steps:
                    sequence = step.get("sequence", "?")
                    name = f"{group_key}-{sequence}"
                    tab = ui.tab(name=name, label=f"#{sequence}")
                    if group_key == "evaluation" and self._is_harmful_evaluation_trace(
                        step
                    ):
                        tab.classes("text-negative font-semibold")

            with ui.tab_panels(tabs, value=first_name).classes("w-full"):
                for step in steps:
                    sequence = step.get("sequence", "?")
                    name = f"{group_key}-{sequence}"
                    with ui.tab_panel(name).classes("w-full p-0"):
                        with ui.card().tight().classes("w-full"):
                            with ui.column().classes("p-3 gap-2"):
                                with ui.row().classes(
                                    "items-center justify-between w-full"
                                ):
                                    ui.label(step.get("_display_label", title)).classes(
                                        "text-xs font-semibold"
                                    )
                                    ui.label(_rel_time(step.get("created_at"))).classes(
                                        "text-xs text-grey-6"
                                    )

                                content = step.get("content")
                                if content is not None:
                                    self._render_trace_content(
                                        step.get("step_type"), content
                                    )

    @staticmethod
    def _is_phase_trace(trace_data: dict) -> bool:
        """Return True when trace content includes phase metadata."""
        content = trace_data.get("content")
        return isinstance(content, dict) and bool(content.get("phase"))

    @staticmethod
    def _autodan_phase_title(phase_key: str) -> str:
        mapping = {
            "WARMUP": "Warmup",
            "LIFELONG": "Lifelong",
            "EVALUATION": "Evaluation",
        }
        key = str(phase_key or "").upper()
        return mapping.get(key, key.replace("_", " ").title() or "Phase")

    @staticmethod
    def _phase_sort_key(phase_key: str) -> tuple[int, str]:
        order = {
            "WARMUP": 0,
            "LIFELONG": 1,
            "EVALUATION": 2,
        }
        key = str(phase_key or "").upper()
        return order.get(key, 99), key

    @staticmethod
    def _render_trace_value_block(title: str, value: object) -> None:
        if value in (None, ""):
            return
        text = (
            json.dumps(value, indent=2)
            if isinstance(value, (dict, list))
            else str(value)
        )
        with ui.card().tight().classes("w-full"):
            with ui.column().classes("p-3 gap-1"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(title).classes("text-xs text-grey-6")
                    ui.button(
                        icon="content_copy",
                    ).props("flat dense size=xs color=grey-6").tooltip(
                        "Copy to clipboard"
                    ).on(
                        "click",
                        js_handler=f"() => navigator.clipboard.writeText({json.dumps(text)})",
                    )
                ui.label(text).classes("text-sm whitespace-pre-wrap")

    def _render_autodan_role_section(
        self,
        title: str,
        role: object,
        fields: list[tuple[str, object]],
    ) -> None:
        visible = [(label, value) for label, value in fields if value not in (None, "")]
        if not visible:
            return

        with ui.card().tight().classes("w-full border border-grey-3"):
            with ui.column().classes("p-3 gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(title).classes("text-xs font-semibold")
                    if role not in (None, ""):
                        ui.badge(str(role), color="primary").classes("text-xs")
                for label, value in visible:
                    self._render_trace_value_block(label, value)

    def _render_autodan_trace_content(self, content: dict) -> None:
        """Render AutoDAN phase trace with explicit role-labeled blocks."""
        phase = str(content.get("phase") or "").upper()
        subphase = str(content.get("subphase") or "").upper()
        is_evaluation_trace = phase == "EVALUATION" or "JUDGE_SCORING" in subphase

        with ui.row().classes("w-full flex-wrap gap-2"):
            for label, value in (
                ("Goal Index", content.get("goal_index")),
                ("Iteration", content.get("iteration")),
                ("Epoch", content.get("epoch")),
                ("Subphase", content.get("subphase")),
            ):
                if value is None:
                    continue
                ui.badge(f"{label}: {value}", color="grey-7").classes("text-xs")

        if is_evaluation_trace:
            hb_raw = content.get("eval_hb")
            hb_norm = "unknown"

            def _is_yes_marker(value: object) -> bool:
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return float(value) > 0.0
                if isinstance(value, str):
                    token = value.strip().lower()
                    if token in {"yes", "true", "harmful", "hb", "jailbreak"}:
                        return True
                    with contextlib.suppress(ValueError):
                        return float(token) > 0.0
                return False

            def _is_no_marker(value: object) -> bool:
                if isinstance(value, bool):
                    return not value
                if isinstance(value, (int, float)):
                    return float(value) <= 0.0
                if isinstance(value, str):
                    token = value.strip().lower()
                    if token in {"no", "false", "benign", "safe"}:
                        return True
                    with contextlib.suppress(ValueError):
                        return float(token) <= 0.0
                return False

            if _is_yes_marker(hb_raw):
                hb_norm = "yes"
            elif _is_no_marker(hb_raw):
                hb_norm = "no"
            elif _is_yes_marker(content.get("eval_jb")):
                hb_norm = "yes"
            elif _is_yes_marker(content.get("judge_success")):
                hb_norm = "yes"

            if hb_norm == "unknown":
                hb_expl = str(content.get("explanation_hb") or "").strip().lower()
                if "harmbenchvariant" in hb_expl and "yes" in hb_expl:
                    hb_norm = "yes"
                elif "harmbenchvariant" in hb_expl and "no" in hb_expl:
                    hb_norm = "no"
                elif "harmful" in hb_expl and "not harmful" not in hb_expl:
                    hb_norm = "yes"

            if hb_norm == "unknown":
                hb_norm = "no"

            verdict = (
                "Harmful (HarmBenchVariant: yes)"
                if hb_norm == "yes"
                else "Safe (HarmBenchVariant: no)"
            )
            with ui.card().tight().classes("w-full border border-grey-3"):
                with ui.column().classes("p-3 gap-1"):
                    ui.label("Explanation").classes("text-xs text-grey-6")
                    ui.label(verdict).classes("text-sm font-medium")

        target_prompt = None if is_evaluation_trace else content.get("prompt")
        target_response = content.get("target_response")
        if is_evaluation_trace and target_response in (None, ""):
            target_response = content.get("response")

        self._render_autodan_role_section(
            "Attacker",
            content.get("attacker_role"),
            [
                ("System Prompt", content.get("system_prompt")),
                ("Attacker Raw Response", content.get("attacker_raw_response")),
                ("Generated Prompt", content.get("generated_prompt")),
            ],
        )

        self._render_autodan_role_section(
            "Target",
            content.get("target_role"),
            [
                ("Prompt", target_prompt),
                ("Target Response", target_response),
            ],
        )

        self._render_autodan_role_section(
            "Scorer",
            content.get("scorer_role"),
            [
                ("Assessment", content.get("assessment")),
                ("Score", content.get("score")),
                ("Previous Score", content.get("prev_score")),
            ],
        )

        self._render_autodan_role_section(
            "Summarizer",
            content.get("summarizer_role"),
            [
                ("Weak Prompt", content.get("weak_prompt")),
                ("Strong Prompt", content.get("strong_prompt")),
                ("Strategy", content.get("strategy")),
                ("Score Delta", content.get("score_delta")),
            ],
        )

        ignored = {
            "phase",
            "subphase",
            "timestamp_utc",
            "goal",
            "goal_index",
            "dashboard_section",
            "dashboard_group",
            "dashboard_item",
            "step_name",
            "iteration",
            "epoch",
            "attacker_role",
            "target_role",
            "scorer_role",
            "summarizer_role",
            "system_prompt",
            "attacker_raw_response",
            "generated_prompt",
            "prompt",
            "target_response",
            "response",
            "assessment",
            "score",
            "prev_score",
            "weak_prompt",
            "strong_prompt",
            "strategy",
            "score_delta",
            "autodan_score",
            "judge_best_score",
            "judge_success",
            "eval_hb",
            "eval_jb",
            "eval_nj",
            "explanation_hb",
            "explanation_jb",
            "explanation_nj",
        }

        extras = [
            (k, v)
            for k, v in content.items()
            if k not in ignored and v not in (None, "")
        ]
        if extras:
            with ui.expansion("Additional Fields", icon="notes").classes("w-full"):
                with ui.column().classes("w-full gap-2 p-2"):
                    for key, value in extras:
                        self._render_trace_value_block(key, value)

        with ui.expansion("View Raw JSON", icon="code").classes("w-full"):
            ui.code(json.dumps(content, indent=2), language="json").classes(
                "w-full text-xs max-h-72 overflow-auto"
            )

    def _render_standard_trace_sections(self, traces: list[dict]) -> None:
        grouped: dict[str, list[dict]] = {
            "goal": [],
            "evaluation": [],
            "generation": [],
            "tools": [],
            "other": [],
        }

        for td in traces:
            group, label = self._classify_trace_step(td)
            td["_display_label"] = label
            grouped[group].append(td)

        self._render_trace_tabs_section("Goal", grouped["goal"], "goal")
        self._render_trace_tabs_section(
            "Evaluation", grouped["evaluation"], "evaluation"
        )
        self._render_trace_tabs_section(
            "Attack / Generation",
            grouped["generation"],
            "generation",
        )
        self._render_trace_tabs_section("Tools", grouped["tools"], "tools")
        self._render_trace_tabs_section("Other", grouped["other"], "other")

    @staticmethod
    def _is_tap_trace_set(traces: list[dict]) -> bool:
        """Return True when trace payload matches TAP candidate/summary format."""
        for td in traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue

            step_name = str(content.get("step_name") or "").strip().lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )

            if (
                step_name.startswith("depth")
                and "candidate" in step_name
                and metadata.get("self_id")
            ):
                return True

            branches = content.get("branches")
            if isinstance(branches, list):
                for branch in branches:
                    if isinstance(branch, dict) and branch.get("self_id"):
                        return True

        return False

    @staticmethod
    def _tap_tree_style_block() -> str:
        return """
<style>
.tap-tree-root {
  width: 100%;
}
.tap-tree-node {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
  transition: transform 120ms ease, box-shadow 120ms ease;
}
.tap-tree-node:hover {
  transform: scale(1.08);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}
.tap-tree-node-selected {
  box-shadow: 0 0 0 3px #3b82f6;
}
.tap-tree-node-black {
  background: #111827;
}
.tap-tree-node-red {
  background: #dc2626;
}
.tap-tree-node-green {
  background: #16a34a;
}
.tap-tree-vline {
  width: 2px;
  background: #6b7280;
}
.tap-tree-hline {
  height: 2px;
  background: #6b7280;
}
</style>
"""

    @staticmethod
    def _tap_node_color_class(node: dict) -> str:
        """Color sink nodes by verdict; all others are black."""
        children = node.get("children", [])
        is_leaf = not children
        if not is_leaf:
            return "tap-tree-node-black"

        if node.get("synthetic_pruned") or node.get("pruned_on_topic"):
            return "tap-tree-node-black"

        if node.get("has_judge_signal"):
            score = node.get("judge_score")
            try:
                numeric = float(score)
            except Exception:
                numeric = 0.0
            return "tap-tree-node-red" if numeric >= 1.0 else "tap-tree-node-green"

        return "tap-tree-node-black"

    @staticmethod
    def _tap_node_sort_key(node: dict) -> tuple[int, int, str]:
        depth = node.get("depth") if isinstance(node.get("depth"), int) else 0
        branch_index = (
            node.get("branch_index")
            if isinstance(node.get("branch_index"), int)
            else 999
        )
        return depth, branch_index, str(node.get("self_id") or "")

    @staticmethod
    def _build_tap_stream_trees(
        traces: list[dict],
    ) -> tuple[dict[int, list[dict]], int, int]:
        """Build per-stream TAP trees from candidate and depth-summary traces."""
        nodes_by_id: dict[str, dict] = {}
        max_depth = 0
        width_hint = 0

        def _clean_text(value: object) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, (dict, list)):
                try:
                    return json.dumps(value, ensure_ascii=True)
                except Exception:
                    return str(value)
            return str(value)

        def _to_int(value: object, default: int = 0) -> int:
            if isinstance(value, int):
                return value
            try:
                return int(value)  # type: ignore[arg-type]
            except Exception:
                return default

        def _has_value(value: object) -> bool:
            return value not in (None, "")

        def _upsert_node(raw: dict, trace_data: dict, inferred_depth: int = 0) -> None:
            nonlocal max_depth, width_hint
            self_id = raw.get("self_id")
            if not self_id:
                return

            stream_index = raw.get("stream_index")
            if not isinstance(stream_index, int):
                return

            depth = _to_int(raw.get("iteration"), 0)
            if depth <= 0:
                depth = _to_int(raw.get("depth"), inferred_depth)
            if depth <= 0:
                depth = 1
            max_depth = max(max_depth, depth)

            branch_index = raw.get("branch_index")
            if isinstance(branch_index, int):
                width_hint = max(width_hint, branch_index + 1)

            prompt_value = raw.get("prompt")
            if isinstance(prompt_value, dict):
                prompt_value = (
                    prompt_value.get("prompt")
                    or prompt_value.get("request")
                    or prompt_value
                )
            prompt = _clean_text(prompt_value)

            response_value = raw.get("response")
            # Detect guardrail-blocked responses before converting to text
            _node_g_side = ""
            _node_g_expl = ""
            _node_g_cats: list = []
            if isinstance(response_value, dict) and (
                response_value.get("adapter_type") == "guardrail"
                or response_value.get("side") in ("before", "after", "unknown")
            ):
                _, _node_g_side, _node_g_expl, _node_g_cats = (
                    DashboardPage._extract_guardrail_from_response(response_value)
                )
                response_text = ""
                target_present = True
            else:
                response_text = _clean_text(response_value)
                target_present = "response" in raw

            judge_score = raw.get("judge_score")
            has_judge_signal = (
                "judge_score" in raw and raw.get("judge_score") is not None
            )

            node = nodes_by_id.get(str(self_id))
            if node is None:
                node = {
                    "self_id": str(self_id),
                    "parent_id": raw.get("parent_id"),
                    "stream_index": stream_index,
                    "depth": depth,
                    "branch_index": branch_index,
                    "prompt": prompt,
                    "improvement": _clean_text(raw.get("improvement")),
                    "on_topic_score": raw.get("on_topic_score"),
                    "target_response": response_text,
                    "target_present": target_present,
                    "judge_score": judge_score,
                    "has_judge_signal": has_judge_signal,
                    "pruned_on_topic": False,
                    "synthetic_pruned": False,
                    "_guardrail_side": _node_g_side,
                    "_guardrail_explanation": _node_g_expl,
                    "_guardrail_categories": _node_g_cats,
                    "children": [],
                    "trace_data": trace_data,
                }
                nodes_by_id[str(self_id)] = node
                return

            # Merge richer values from another payload (candidate/summary).
            if node.get("parent_id") in (None, "") and _has_value(raw.get("parent_id")):
                node["parent_id"] = raw.get("parent_id")
            if not isinstance(node.get("depth"), int) or node.get("depth", 0) <= 0:
                node["depth"] = depth
            if node.get("branch_index") is None and isinstance(branch_index, int):
                node["branch_index"] = branch_index
            if not _has_value(node.get("prompt")) and prompt:
                node["prompt"] = prompt
            if not _has_value(node.get("improvement")) and _has_value(
                raw.get("improvement")
            ):
                node["improvement"] = _clean_text(raw.get("improvement"))
            if (
                node.get("on_topic_score") is None
                and raw.get("on_topic_score") is not None
            ):
                node["on_topic_score"] = raw.get("on_topic_score")
            if not node.get("target_present") and target_present:
                node["target_present"] = True
                node["target_response"] = response_text
                if _node_g_side:
                    node["_guardrail_side"] = _node_g_side
                    node["_guardrail_explanation"] = _node_g_expl
                    node["_guardrail_categories"] = _node_g_cats
            elif not _has_value(node.get("target_response")) and response_text:
                node["target_response"] = response_text
            if not node.get("has_judge_signal") and has_judge_signal:
                node["has_judge_signal"] = True
                node["judge_score"] = judge_score
            elif node.get("judge_score") is None and judge_score is not None:
                node["judge_score"] = judge_score
            if node.get("trace_data") is None and trace_data is not None:
                node["trace_data"] = trace_data

        for td in traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue

            if isinstance(content.get("depth"), int):
                max_depth = max(max_depth, content.get("depth") or 0)
            if isinstance(content.get("width"), int):
                width_hint = max(width_hint, content.get("width") or 0)

            step_name = str(content.get("step_name") or "").strip().lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )

            if step_name.startswith("depth") and "candidate" in step_name:
                request_payload = content.get("request")
                prompt_payload = request_payload
                if isinstance(request_payload, dict):
                    prompt_payload = (
                        request_payload.get("prompt")
                        or request_payload.get("request")
                        or request_payload
                    )
                raw_candidate = {
                    "self_id": metadata.get("self_id"),
                    "parent_id": metadata.get("parent_id"),
                    "stream_index": metadata.get("stream_index"),
                    "iteration": metadata.get("iteration"),
                    "branch_index": metadata.get("branch_index"),
                    "prompt": prompt_payload,
                    "improvement": metadata.get("improvement"),
                    "on_topic_score": metadata.get("on_topic_score"),
                    "response": content.get("response"),
                    "judge_score": metadata.get("judge_score"),
                }
                _upsert_node(
                    raw_candidate, td, inferred_depth=metadata.get("iteration") or 0
                )

            branches = content.get("branches")
            if isinstance(branches, list):
                for branch in branches:
                    if not isinstance(branch, dict):
                        continue
                    branch_payload = dict(branch)
                    if (
                        "response" not in branch_payload
                        and "target_response" in branch_payload
                    ):
                        branch_payload["response"] = branch_payload.get(
                            "target_response"
                        )
                    branch_depth = (
                        content.get("depth")
                        if isinstance(content.get("depth"), int)
                        else 0
                    )
                    if branch_depth > 0:
                        branch_payload.setdefault("depth", branch_depth)
                    _upsert_node(branch_payload, td, inferred_depth=branch_depth)

        # Link parent/child relations and build roots per stream.
        for node in nodes_by_id.values():
            node["children"] = []

        roots_by_stream: dict[int, list[dict]] = defaultdict(list)
        for node in nodes_by_id.values():
            parent_id = node.get("parent_id")
            if parent_id and str(parent_id) in nodes_by_id:
                parent = nodes_by_id[str(parent_id)]
                if parent.get("stream_index") == node.get("stream_index"):
                    parent["children"].append(node)
                    continue
            roots_by_stream[node.get("stream_index", 0)].append(node)

        def _sort_tree(curr: dict) -> None:
            curr["children"].sort(key=DashboardPage._tap_node_sort_key)
            for child in curr["children"]:
                _sort_tree(child)

        for stream_idx, roots in roots_by_stream.items():
            roots.sort(key=DashboardPage._tap_node_sort_key)
            for root in roots:
                _sort_tree(root)

        if max_depth <= 0:
            max_depth = 1
        if width_hint <= 0:
            width_hint = 1

        # Add synthetic sink nodes for pruned branches so dead ends are explicit.
        placeholder_seed = 0

        def _add_pruned_placeholders(curr: dict) -> None:
            nonlocal placeholder_seed
            if curr.get("synthetic_pruned"):
                return
            curr_depth = curr.get("depth") if isinstance(curr.get("depth"), int) else 1
            if curr_depth >= max_depth:
                return

            real_children = [
                c for c in curr.get("children", []) if not c.get("synthetic_pruned")
            ]
            missing = max(0, width_hint - len(real_children))
            for idx in range(missing):
                placeholder_seed += 1
                curr["children"].append(
                    {
                        "self_id": f"__tap_pruned_{placeholder_seed}",
                        "parent_id": curr.get("self_id"),
                        "stream_index": curr.get("stream_index"),
                        "depth": curr_depth + 1,
                        "branch_index": width_hint + idx,
                        "prompt": "",
                        "improvement": "",
                        "on_topic_score": None,
                        "target_response": "",
                        "target_present": False,
                        "judge_score": None,
                        "has_judge_signal": False,
                        "pruned_on_topic": False,
                        "synthetic_pruned": True,
                        "children": [],
                        "trace_data": None,
                    }
                )

            curr["children"].sort(key=DashboardPage._tap_node_sort_key)
            for child in real_children:
                _add_pruned_placeholders(child)

        for roots in roots_by_stream.values():
            for root in roots:
                _add_pruned_placeholders(root)

        # Mark on-topic pruning: no target, no judge, and failing on-topic score.
        def _mark_flags(curr: dict) -> None:
            on_topic_score = curr.get("on_topic_score")
            pruned_on_topic = (
                (on_topic_score in (0, False))
                and not curr.get("target_present")
                and not curr.get("has_judge_signal")
            )
            curr["pruned_on_topic"] = bool(pruned_on_topic)
            for child in curr.get("children", []):
                _mark_flags(child)

        for roots in roots_by_stream.values():
            for root in roots:
                _mark_flags(root)

        return dict(roots_by_stream), max_depth, width_hint

    def _render_tap_trace_tree_view(self, traces: list[dict]) -> None:
        """Render TAP traces as per-stream vertical trees with node drill-down."""
        trees_by_stream, max_depth, width_hint = self._build_tap_stream_trees(traces)
        if not trees_by_stream:
            ui.label("No TAP tree traces found for this goal.").classes(
                "text-sm text-grey-6"
            )
            return

        ui.html(self._tap_tree_style_block())

        with ui.row().classes("items-center gap-4 text-xs text-grey-6 pb-1"):
            ui.label(f"Depth: {max_depth}")
            ui.label(f"Width: {width_hint}")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("tap-tree-node tap-tree-node-red")
                ui.label("Sink harmful")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("tap-tree-node tap-tree-node-green")
                ui.label("Sink safe")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("tap-tree-node tap-tree-node-black")
                ui.label("Intermediate / pruned")

        for stream_index in sorted(trees_by_stream.keys()):
            roots = trees_by_stream[stream_index]
            with ui.expansion(
                f"Stream {stream_index + 1}",
                icon="account_tree",
            ).classes("w-full") as stream_exp:
                stream_exp.props("default-opened")
                with ui.column().classes("w-full gap-4 p-2 tap-tree-root"):
                    selected_element: list[object | None] = [None]
                    detail_panel: list[object | None] = [None]

                    with ui.scroll_area().classes("w-full").style("max-height: 620px;"):
                        with ui.row().classes(
                            "w-full items-start justify-center gap-6"
                        ):
                            for root in roots:
                                self._render_tap_tree_node_recursive(
                                    root,
                                    detail_panel,
                                    selected_element,
                                )

                    ui.separator()

                    with ui.column().classes("w-full gap-2") as details:
                        with ui.row().classes("items-center gap-2 py-3 justify-center"):
                            ui.icon("ads_click").classes("text-grey-5")
                            ui.label(
                                "Click a node to inspect (stream, depth, width slot)"
                            ).classes("text-sm text-grey-5 italic")
                    detail_panel[0] = details

    def _render_tap_tree_node_recursive(
        self,
        node: dict,
        detail_panel: list[object | None],
        selected_element: list[object | None],
    ) -> None:
        """Render one TAP node and its subtree."""
        children = node.get("children", [])
        color_class = self._tap_node_color_class(node)

        depth = node.get("depth") if isinstance(node.get("depth"), int) else 0
        branch_index = node.get("branch_index")
        node_label = f"{depth}"
        if isinstance(branch_index, int):
            node_label = f"{depth}:{branch_index + 1}"

        with ui.column().classes("items-center gap-0"):
            circle = ui.element("div").classes(f"tap-tree-node {color_class}")
            with circle:
                ui.label(node_label).classes("text-[9px] font-bold text-white")

            circle.on(
                "click",
                lambda _evt, curr=node, el=circle: self._on_tap_tree_node_click(
                    curr,
                    detail_panel,
                    selected_element,
                    el,
                ),
            )

            if children:
                ui.element("div").classes("tap-tree-vline").style("height: 16px;")

                branch_width = max(42, len(children) * 52)
                ui.element("div").classes("tap-tree-hline").style(
                    f"width: {branch_width}px;"
                )

                with ui.row().classes("items-start justify-center gap-4"):
                    for child in children:
                        with ui.column().classes("items-center gap-0"):
                            ui.element("div").classes("tap-tree-vline").style(
                                "height: 14px;"
                            )
                            self._render_tap_tree_node_recursive(
                                child,
                                detail_panel,
                                selected_element,
                            )

    def _on_tap_tree_node_click(
        self,
        node: dict,
        detail_panel: list[object | None],
        selected_element: list[object | None],
        element: object,
    ) -> None:
        """Select node and render the requested TAP detail expansions."""
        previous = selected_element[0]
        if previous is not None:
            with contextlib.suppress(Exception):
                previous.classes(remove="tap-tree-node-selected")

        with contextlib.suppress(Exception):
            element.classes(add="tap-tree-node-selected")
        selected_element[0] = element

        details = detail_panel[0]
        if details is None:
            return
        details.clear()
        with details:
            self._render_tap_node_detail_panels(node)

    def _render_tap_node_detail_panels(self, node: dict) -> None:
        """Render node details with Attacker/On-Topic/Target/Judge expansions."""
        stream_index = node.get("stream_index")
        depth = node.get("depth")
        branch_index = node.get("branch_index")

        stream_label = stream_index + 1 if isinstance(stream_index, int) else "?"
        depth_label = depth if isinstance(depth, int) else "?"
        width_slot = branch_index + 1 if isinstance(branch_index, int) else "?"

        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label(
                    f"Stream {stream_label} · Depth {depth_label} · Width slot {width_slot}"
                ).classes("text-sm font-semibold")
                if node.get("synthetic_pruned"):
                    ui.badge("Pruned sink", color="grey-7").classes("text-xs")
                elif node.get("pruned_on_topic"):
                    ui.badge("Pruned by on-topic", color="grey-7").classes("text-xs")
                elif node.get("has_judge_signal"):
                    score = node.get("judge_score")
                    try:
                        harmful = float(score) >= 1.0
                    except Exception:
                        harmful = False
                    ui.badge(
                        "Harmful" if harmful else "Safe",
                        color="negative" if harmful else "positive",
                    ).classes("text-xs")
                else:
                    ui.badge("Intermediate", color="grey-7").classes("text-xs")

            with ui.expansion("Attacker", icon="smart_toy").classes("w-full"):
                with ui.column().classes("w-full gap-2 p-2"):
                    improvement = str(node.get("improvement") or "").strip()
                    prompt = str(node.get("prompt") or "")
                    if improvement:
                        with ui.card().tight().classes("w-full"):
                            with ui.column().classes("p-3 gap-1"):
                                ui.label("Improvement").classes(
                                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                                )
                                ui.label(improvement).classes(
                                    "text-sm whitespace-pre-wrap"
                                )
                    with ui.card().tight().classes("w-full"):
                        with ui.column().classes("p-3 gap-1"):
                            ui.label("Generated prompt").classes(
                                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                            )
                            ui.label(prompt or "(not available)").classes(
                                "text-sm whitespace-pre-wrap"
                            )

            with ui.expansion("On-Topic Judge", icon="rule").classes("w-full"):
                with ui.column().classes("w-full gap-2 p-2"):
                    on_topic_score = node.get("on_topic_score")
                    if on_topic_score is None:
                        ui.badge("No on-topic score", color="grey-7").classes("text-xs")
                    else:
                        is_on_topic = on_topic_score not in (0, False)
                        ui.badge(
                            f"Score: {on_topic_score}",
                            color="positive" if is_on_topic else "negative",
                        ).classes("text-xs")
                        ui.label(
                            "Classified as on-topic"
                            if is_on_topic
                            else "Classified as off-topic"
                        ).classes("text-sm")

            if node.get("pruned_on_topic"):
                with ui.card().tight().classes("w-full border border-grey-4 bg-grey-2"):
                    with ui.column().classes("p-3 gap-1"):
                        ui.label("Pruned after on-topic judge").classes(
                            "text-xs font-semibold"
                        )
                        ui.label(
                            "Target and Judge steps are intentionally hidden for this node."
                        ).classes("text-sm text-grey-7")
            else:
                with ui.expansion("Target", icon="ads_click").classes("w-full"):
                    with ui.column().classes("w-full gap-2 p-2"):
                        _g_side = node.get("_guardrail_side") or ""
                        if _g_side:
                            _g_expl = (
                                node.get("_guardrail_explanation")
                                or "Blocked by guardrail"
                            )
                            _g_cats = node.get("_guardrail_categories") or []
                            self._render_guardrail_event_block(
                                _g_side, _g_expl, _g_cats
                            )
                        elif node.get("target_present"):
                            response = str(node.get("target_response") or "")
                            if response:
                                ui.label(response).classes(
                                    "text-sm whitespace-pre-wrap"
                                )
                            else:
                                ui.label("(empty response)").classes(
                                    "text-sm text-grey-6 italic"
                                )
                        else:
                            ui.label("(target response not available)").classes(
                                "text-sm text-grey-6 italic"
                            )

                with ui.expansion("Judge", icon="gavel").classes("w-full"):
                    with ui.column().classes("w-full gap-2 p-2"):
                        if node.get("has_judge_signal"):
                            score = node.get("judge_score")
                            try:
                                harmful = float(score) >= 1.0
                            except Exception:
                                harmful = False
                            ui.badge(
                                f"Score: {score}",
                                color="negative" if harmful else "positive",
                            ).classes("text-xs")
                            ui.label("Harmful" if harmful else "Safe").classes(
                                "text-sm"
                            )
                        else:
                            ui.label("(judge result not available)").classes(
                                "text-sm text-grey-6 italic"
                            )

            with ui.expansion("Metadata", icon="info").classes("w-full"):
                trace_data = node.get("trace_data")
                content = (
                    trace_data.get("content") if isinstance(trace_data, dict) else {}
                )
                with ui.column().classes("w-full gap-1 p-2"):
                    ui.label(f"self_id: {node.get('self_id')}").classes("text-xs")
                    ui.label(f"parent_id: {node.get('parent_id')}").classes("text-xs")
                    ui.code(
                        json.dumps(content or {}, indent=2, default=str),
                        language="json",
                    ).classes("w-full text-xs max-h-64")

    @staticmethod
    def _autodan_step_bucket(content: dict) -> str:
        """Map an AutoDAN step payload to the requested role bucket."""
        subphase = str(content.get("subphase") or "").upper()
        dashboard_item = str(content.get("dashboard_item") or "").upper()
        token = f"{subphase} {dashboard_item}"

        if "SUMMAR" in token:
            return "summarizer"
        if "TARGET" in token:
            return "target"
        if "SCOR" in token or "JUDGE" in token:
            return "scorer"
        if "GENERATION" in token or "ATTACK" in token:
            return "attacker"

        if any(
            key in content
            for key in ("attacker_role", "system_prompt", "generated_prompt")
        ):
            return "attacker"
        if any(key in content for key in ("target_role", "target_response")):
            return "target"
        if any(
            key in content
            for key in (
                "scorer_role",
                "score",
                "assessment",
                "autodan_score",
                "judge_best_score",
            )
        ):
            return "scorer"
        if any(
            key in content
            for key in ("summarizer_role", "strategy", "weak_prompt", "strong_prompt")
        ):
            return "summarizer"

        return "attacker"

    def _render_autodan_steps_cards(self, steps: list[dict]) -> None:
        if not steps:
            ui.label("No traces for this section.").classes("text-xs text-grey-6")
            return

        for step in steps:
            with ui.card().tight().classes("w-full"):
                with ui.column().classes("p-3 gap-2"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(
                            str(
                                step.get("content", {}).get("step_name")
                                or step.get("_display_label")
                                or "Step"
                            )
                        ).classes("text-xs font-semibold")
                        ui.label(_rel_time(step.get("created_at"))).classes(
                            "text-xs text-grey-6"
                        )

                    content = step.get("content")
                    if isinstance(content, dict):
                        self._render_autodan_trace_content(content)
                    elif content is not None:
                        self._render_trace_content(step.get("step_type"), content)

    def _render_autodan_epoch_group(
        self,
        steps: list[dict],
    ) -> None:
        ordered = sorted(steps, key=lambda td: td.get("sequence", 0))
        sections: dict[str, list[dict]] = {
            "attacker": [],
            "target": [],
            "scorer": [],
            "summarizer": [],
        }

        for step in ordered:
            content = (
                step.get("content") if isinstance(step.get("content"), dict) else {}
            )
            bucket = self._autodan_step_bucket(content)
            sections.setdefault(bucket, []).append(step)

        menu_spec = [
            ("Attacker", "smart_toy", "attacker"),
            ("Target", "ads_click", "target"),
            ("Scorer", "analytics", "scorer"),
        ]
        if sections.get("summarizer"):
            menu_spec.append(("Summarizer", "summarize", "summarizer"))

        for label, icon, key in menu_spec:
            entries = sections.get(key, [])
            with ui.expansion(f"{label} ({len(entries)})", icon=icon).classes("w-full"):
                with ui.column().classes("w-full gap-2 p-2"):
                    self._render_autodan_steps_cards(entries)

    @staticmethod
    def _extract_autodan_iteration_index(content: dict) -> int | None:
        """Best-effort extraction of zero-based iteration index."""
        iteration_value = content.get("iteration")
        if isinstance(iteration_value, int) and iteration_value >= 0:
            return iteration_value

        dashboard_group = str(content.get("dashboard_group") or "")
        match = re.search(r"iteration\s+(\d+)", dashboard_group, flags=re.IGNORECASE)
        if match:
            parsed = int(match.group(1)) - 1
            return parsed if parsed >= 0 else 0

        step_name = str(content.get("step_name") or "")
        match = re.search(r"iteration\s+(\d+)", step_name, flags=re.IGNORECASE)
        if match:
            parsed = int(match.group(1)) - 1
            return parsed if parsed >= 0 else 0

        return None

    def _render_autodan_phase_timeline(self, traces: list[dict]) -> bool:
        """Render phase-first timeline for AutoDAN traces."""
        phase_traces = [td for td in traces if self._is_phase_trace(td)]
        if not phase_traces:
            return False

        phase_groups: dict[str, dict[str, list[dict]]] = {}
        ordered_phase_keys: list[str] = []
        # Track latest explicit iteration seen, keyed by phase+goal_index for
        # robust summarizer placement in the correct iteration tab.
        phase_goal_last_iteration: dict[tuple[str, object], int] = {}
        phase_last_iteration: dict[str, int] = {}

        sorted_traces = sorted(phase_traces, key=lambda td: td.get("sequence", 0))
        for td in sorted_traces:
            content = td.get("content") if isinstance(td.get("content"), dict) else {}
            phase_key = str(
                content.get("phase") or content.get("dashboard_section") or "OTHER"
            ).upper()

            if phase_key in {"WARMUP", "LIFELONG"}:
                iteration_idx = self._extract_autodan_iteration_index(content)
                step_bucket = self._autodan_step_bucket(content)
                goal_key = content.get("goal_index")

                if iteration_idx is None and step_bucket == "summarizer":
                    iteration_idx = phase_goal_last_iteration.get(
                        (phase_key, goal_key),
                        phase_last_iteration.get(phase_key),
                    )

                # Hide non-iteration tabs like "Warmup" and "Warmup Summary".
                if iteration_idx is None:
                    continue

                # Keep "last seen" (not max) to avoid dragging late summarizers
                # into a newer iteration when traces are slightly out of order.
                phase_last_iteration[phase_key] = iteration_idx
                phase_goal_last_iteration[(phase_key, goal_key)] = iteration_idx
                group_name = f"{self._autodan_phase_title(phase_key)} Iteration {iteration_idx + 1}"
            else:
                group_name = str(
                    content.get("dashboard_group")
                    or content.get("dashboard_item")
                    or content.get("subphase")
                    or td.get("_display_label")
                    or f"Step {td.get('sequence', '?')}"
                )

            if phase_key not in phase_groups:
                phase_groups[phase_key] = {}
                ordered_phase_keys.append(phase_key)
            phase_groups[phase_key].setdefault(group_name, []).append(td)

        ordered_phase_keys.sort(key=self._phase_sort_key)

        for phase_key in ordered_phase_keys:
            groups = phase_groups[phase_key]
            total_steps = sum(len(steps) for steps in groups.values())
            phase_title = self._autodan_phase_title(phase_key)

            with ui.column().classes("w-full gap-2 pb-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(phase_title).classes("text-sm font-semibold")
                    ui.badge(str(total_steps), color="grey-6").classes("text-xs")

                group_items = list(groups.items())
                first_name = f"{phase_key.lower()}-0"
                with (
                    ui.tabs()
                    .props("dense align=left no-caps inline-label")
                    .classes("w-full") as tabs
                ):
                    for idx, (group_name, steps) in enumerate(group_items):
                        tab_name = f"{phase_key.lower()}-{idx}"
                        ui.tab(
                            name=tab_name,
                            label=f"{group_name} ({len(steps)})",
                        )

                with ui.tab_panels(tabs, value=first_name).classes("w-full"):
                    for idx, (_, steps) in enumerate(group_items):
                        tab_name = f"{phase_key.lower()}-{idx}"
                        with ui.tab_panel(tab_name).classes("w-full p-0"):
                            with ui.column().classes("w-full gap-2"):
                                if phase_key in {"WARMUP", "LIFELONG"}:
                                    epoch_groups: dict[int, list[dict]] = {}

                                    ordered_steps = sorted(
                                        steps, key=lambda td: td.get("sequence", 0)
                                    )
                                    for step in ordered_steps:
                                        content = (
                                            step.get("content")
                                            if isinstance(step.get("content"), dict)
                                            else {}
                                        )
                                        epoch_value = content.get("epoch")
                                        if (
                                            isinstance(epoch_value, int)
                                            and epoch_value >= 0
                                        ):
                                            epoch_key = epoch_value
                                        else:
                                            epoch_key = max(
                                                epoch_groups.keys(),
                                                default=0,
                                            )
                                        epoch_groups.setdefault(epoch_key, []).append(
                                            step
                                        )

                                    for epoch_key in sorted(epoch_groups.keys()):
                                        epoch_steps = epoch_groups[epoch_key]
                                        epoch_label = f"Epoch {epoch_key + 1}"
                                        with ui.expansion(
                                            f"{epoch_label} ({len(epoch_steps)} traces)",
                                            icon="expand_more",
                                        ).classes("w-full"):
                                            with ui.column().classes(
                                                "w-full gap-2 p-2"
                                            ):
                                                self._render_autodan_epoch_group(
                                                    epoch_steps
                                                )
                                else:
                                    self._render_autodan_steps_cards(
                                        sorted(
                                            steps,
                                            key=lambda td: td.get("sequence", 0),
                                        )
                                    )

        return True

    def _render_trace_content(self, step_type: str | None, content: object) -> None:
        """Render trace content with dashboard-friendly grouping."""
        st = (step_type or "").upper()

        if isinstance(content, dict):
            # -----------------------------------------------------------------
            # TAP Goals block
            # -----------------------------------------------------------------
            goal = content.get("goal")
            if isinstance(goal, str) and goal.strip():
                with (
                    ui.card().tight().classes("w-full border border-red-200 bg-red-50")
                ):
                    with ui.column().classes("p-3 gap-1"):
                        ui.label("Target Goal").classes("text-xs text-grey-6")
                        ui.label(goal).classes("text-sm font-medium")

            # -----------------------------------------------------------------
            # Summary cards (Result/Config-like)
            # -----------------------------------------------------------------
            summary = [
                ("Goal Index", content.get("goal_index")),
                ("Attack Type", content.get("attack_type")),
                ("Depth", content.get("depth")),
                ("Width", content.get("width")),
                ("Best Score", content.get("best_score")),
                ("Results", content.get("num_results")),
                ("Traces", content.get("total_traces")),
                ("Success", content.get("success")),
                ("Judge Model", content.get("judge_model")),
            ]
            if "EVALUATION" in st and content.get("evaluator") is not None:
                summary.append(("Evaluator", content.get("evaluator")))
            visible = [(k, v) for k, v in summary if v is not None]
            if visible:
                with ui.row().classes("w-full flex-wrap gap-2"):
                    for label, value in visible:
                        with ui.card().tight().classes("min-w-36"):
                            with ui.column().classes("px-3 py-2 gap-0"):
                                ui.label(label).classes("text-[11px] text-grey-6")
                                ui.label(str(value)).classes("text-sm font-medium")

            # -----------------------------------------------------------------
            # Evaluation-style blocks
            # -----------------------------------------------------------------
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )
            nested_result = (
                content.get("result") if isinstance(content.get("result"), dict) else {}
            )
            request_value = content.get("request")
            response_value = content.get("response")

            if isinstance(request_value, dict):
                request_value = (
                    request_value.get("prompt")
                    or request_value.get("request")
                    or request_value
                )
            if isinstance(response_value, dict):
                # BoN evaluation traces carry the model output under target_response.
                response_value = (
                    response_value.get("target_response")
                    or response_value.get("response")
                    or response_value.get("completion")
                    or response_value.get("generated_text")
                    or response_value
                )

            # In many evaluation traces, prompt/completion are stored as
            # prefix/completion (sometimes inside metadata). Surface them
            # directly so they are visible without expanding metadata.
            if request_value in (None, ""):
                request_value = content.get("prefix")
            if response_value in (None, ""):
                response_value = content.get("completion")

            # BoN and some evaluators place payloads under `result`.
            if request_value in (None, "") and nested_result:
                request_value = (
                    nested_result.get("request")
                    or nested_result.get("prefix")
                    or nested_result.get("prompt")
                )
            if response_value in (None, "") and nested_result:
                response_value = (
                    nested_result.get("response")
                    or nested_result.get("completion")
                    or nested_result.get("answer")
                )

            if request_value in (None, ""):
                request_value = metadata.get("prefix")
            if response_value in (None, ""):
                response_value = metadata.get("completion")

            # Last fallback where request/response are inside metadata.
            if request_value in (None, ""):
                request_value = metadata.get("request") or metadata.get("prompt")
            if response_value in (None, ""):
                response_value = metadata.get("response") or metadata.get("answer")

            scorer_explanation = (
                content.get("scorer_explanation")
                or nested_result.get("scorer_explanation")
                or metadata.get("scorer_explanation")
            )

            # ------------------------------------------------------------------
            # Guardrail event: detect and strip from the blocks list so we can
            # render dedicated visual boxes instead of a generic "Response" card.
            # ------------------------------------------------------------------
            _guardrail_event: dict | None = None
            if isinstance(response_value, dict) and response_value.get("side") in (
                "before",
                "after",
                "unknown",
            ):
                _guardrail_event = response_value
                if response_value.get("side") == "after":
                    # Show the original target response, then the censor box below.
                    response_value = response_value.get("target_response") or ""
                else:
                    # Before-guardrail: request was never sent — no response to show.
                    response_value = None

            blocks = [
                ("Explanation", content.get("explanation")),
                ("Scorer Explanation", scorer_explanation),
                ("Attack Prompt", content.get("attack_prompt")),
                ("Agent Completion", content.get("agent_completion")),
                ("Request", request_value),
                ("Response", response_value),
            ]

            # In evaluation traces, highlight the decision banner first.
            if "EVALUATION" in st:
                success = content.get("success")
                if success is not None:
                    label = "Success" if bool(success) else "No Success"
                    color = "positive" if bool(success) else "warning"
                    ui.badge(label, color=color).classes("text-xs")

            # MML: render encoded image inline if present in metadata
            mml_image_url = metadata.get("image_data_url", "")
            if mml_image_url:
                mml_enc_mode = metadata.get("encoding_mode", "unknown")
                with (
                    ui.card()
                    .tight()
                    .classes(
                        "w-full border border-purple-200 bg-purple-50 dark:border-purple-700 dark:bg-purple-900/20"
                    )
                ):
                    with ui.column().classes("p-3 gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("image", color="purple").classes("text-base")
                            ui.label("Encoded Image").classes(
                                "text-xs font-semibold text-grey-6"
                            )
                            ui.badge(mml_enc_mode, color="purple").classes("text-xs")
                        ui.html(
                            f'<img src="{mml_image_url}" '
                            f'alt="MML encoded prompt ({mml_enc_mode})" '
                            f'style="max-width:100%;height:auto;border-radius:4px;'
                            f'border:1px solid var(--q-grey-3);" />'
                        ).classes("w-full")

            for title, value in blocks:
                if value is None or value == "":
                    continue

                # For request payloads render only the prompt text.
                if title == "Request" and isinstance(value, dict) and "prompt" in value:
                    value = value.get("prompt")

                text = (
                    json.dumps(value, indent=2)
                    if isinstance(value, (dict, list))
                    else str(value)
                )
                with ui.card().tight().classes("w-full"):
                    with ui.column().classes("p-3 gap-1"):
                        ui.label(title).classes("text-xs text-grey-6")
                        ui.label(text).classes("text-sm whitespace-pre-wrap")

            if isinstance(metadata, dict) and metadata:
                with ui.expansion("Metadata", icon="info").classes("w-full"):
                    with ui.column().classes("w-full gap-1 p-2"):
                        branch_idx = metadata.get(
                            "branch_index", content.get("branch_index")
                        )
                        stream_idx = metadata.get(
                            "stream_index", content.get("stream_index")
                        )
                        if branch_idx is not None or stream_idx is not None:
                            with ui.row().classes("w-full items-center gap-3"):
                                if branch_idx is not None:
                                    ui.badge(
                                        f"branch_index: {branch_idx}",
                                        color="grey-7",
                                    ).classes("text-xs")
                                if stream_idx is not None:
                                    ui.badge(
                                        f"stream_index: {stream_idx}",
                                        color="grey-7",
                                    ).classes("text-xs")
                        for key, value in metadata.items():
                            if key in {"prefix", "completion", "image_data_url"}:
                                continue
                            with ui.row().classes("w-full items-start gap-2"):
                                ui.label(f"{key}:").classes("text-xs text-grey-6")
                                ui.label(str(value)).classes(
                                    "text-xs whitespace-pre-wrap break-all"
                                )
            elif isinstance(content, dict):
                branch_idx = content.get("branch_index")
                stream_idx = content.get("stream_index")
                if branch_idx is not None or stream_idx is not None:
                    with ui.expansion("Metadata", icon="info").classes("w-full"):
                        with ui.row().classes("w-full items-center gap-3 p-2"):
                            if branch_idx is not None:
                                ui.badge(
                                    f"branch_index: {branch_idx}",
                                    color="grey-7",
                                ).classes("text-xs")
                            if stream_idx is not None:
                                ui.badge(
                                    f"stream_index: {stream_idx}",
                                    color="grey-7",
                                ).classes("text-xs")

            # Keep raw payload available but secondary.
            with ui.expansion("View Raw JSON", icon="code").classes("w-full"):
                ui.code(json.dumps(content, indent=2), language="json").classes(
                    "w-full text-xs max-h-72 overflow-auto"
                )

            # Guardrail event boxes rendered after all other content.
            if _guardrail_event is not None:
                self._render_guardrail_event_block(_guardrail_event)

            return

        if isinstance(content, list):
            ui.label(f"List content ({len(content)} items)").classes("text-sm")
            with ui.expansion("View Raw JSON", icon="code").classes("w-full"):
                ui.code(json.dumps(content, indent=2), language="json").classes(
                    "w-full text-xs max-h-72 overflow-auto"
                )
            return

        ui.label(str(content)).classes("text-sm whitespace-pre-wrap")

    @staticmethod
    def _render_guardrail_event_block(event: dict) -> None:
        """Render a visual banner for a guardrail-blocked trace step.

        * ``side="before"`` — prompt was blocked before reaching the target model:
          shows an orange warning box.  No target response is displayed because
          the request was never sent.
        * ``side="after"`` — model response was censored after it was received:
          shows a red box below the (visible) target response.
        """
        side = event.get("side", "unknown")
        explanation = str(event.get("explanation") or "Blocked by guardrail")
        categories = event.get("categories", [])

        cat_html = ""
        if categories:
            cat_str = ", ".join(str(c) for c in categories)
            if side == "before":
                cat_html = f'<span style="font-weight:700;color:#c2410c">Categories: </span><span style="color:#9a3412">{cat_str}</span><br><br>'
            elif side == "after":
                cat_html = f'<span style="font-weight:700;color:#dc2626">Categories: </span><span style="color:#991b1b">{cat_str}</span><br><br>'
            else:
                cat_html = f'<span style="font-weight:700;color:#616161">Categories: </span><span style="color:#374151">{cat_str}</span><br><br>'

        if side == "before":
            heading = "⚠ BEFORE GUARDRAIL — BLOCKED"
            border_color = "#f97316"
            bg_color = "#fff7ed"
            heading_color = "#c2410c"
            expl_label = (
                '<span style="font-weight:700;color:#c2410c">Explanation: </span>'
            )
        elif side == "after":
            heading = "🚫 AFTER GUARDRAIL — CENSORED"
            border_color = "#ef4444"
            bg_color = "#fef2f2"
            heading_color = "#dc2626"
            expl_label = (
                '<span style="font-weight:700;color:#dc2626">Explanation: </span>'
            )
        else:
            heading = "🛡 GUARDRAIL — BLOCKED"
            border_color = "#9e9e9e"
            bg_color = "#f5f5f5"
            heading_color = "#616161"
            expl_label = (
                '<span style="font-weight:700;color:#616161">Explanation: </span>'
            )

        from html import escape

        ui.html(
            f'<div style="margin-bottom:8px">'
            f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:4px;color:{heading_color}">{heading}</div>'
            f'<pre style="font-size:11px;padding:10px;background:{bg_color};border:2px solid {border_color};border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0">'
            f"{cat_html}"
            f"{expl_label}"
            f'<span style="color:#6b7280">{escape(explanation)}</span>'
            f"</pre></div>"
        )

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
            elif _v == "reports":
                await self._load_history_reports()
        except Exception as exc:
            ui.notify(f"Failed to load data: {exc}", type="negative")
        finally:
            self.loading_spinner.set_visibility(False)

    # ── Result detail (right drawer) ──────────────────────────────────────────

    async def show_result_detail(self, result: dict, foreground: bool = False) -> None:
        """Populate and open result detail either in drawer or foreground modal."""
        detail_area = self.result_modal_area
        detail_title = self.result_modal_title

        if detail_area is None or detail_title is None:
            return

        detail_area.clear()
        eval_status = result.get("evaluation_status", "")
        eval_notes = result.get("evaluation_notes")
        bucket = _result_bucket(eval_status, eval_notes)

        with detail_area:
            with ui.column().classes("w-full gap-4 p-5"):
                ui.label(result.get("id", "")).classes(
                    "font-mono text-xs text-grey-6 select-all"
                )
                result_num = result.get("goal_number") or (
                    (result.get("goal_index", 0) or 0) + 1
                )
                detail_title.text = f"Result · #{result_num}"

                # Evaluation banner
                if bucket == "jailbreak":
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
                elif bucket == "mitigated":
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
                elif bucket == "failed":
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
                        _eval_label(eval_status, eval_notes),
                        color=_eval_color(eval_status, eval_notes),
                    ).classes("text-xs px-2 py-0.5")
                    ui.label(f"Goal #{result_num}").classes("text-xs text-grey-6")

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

        self.result_modal_dialog.open()

        # Load traces async
        try:
            traces_raw = self.backend.list_traces(result_id=UUID(result["id"]))
            trace_container.clear()

            serialized_traces = [_serialize(t) for t in traces_raw]
            synthetic_eval = self._build_synthetic_evaluation_trace(result)

            has_real_evaluation = False
            for td in serialized_traces:
                group, _ = self._classify_trace_step(td)
                if group == "evaluation":
                    has_real_evaluation = True
                    break

            if synthetic_eval is not None and not has_real_evaluation:
                synthetic_eval["sequence"] = len(serialized_traces) + 1
                serialized_traces.append(synthetic_eval)

            serialized_traces = self._ensure_evaluation_request_response(
                serialized_traces,
                result,
            )

            if not serialized_traces:
                with trace_container:
                    ui.label("No traces recorded for this result.").classes(
                        "text-sm text-grey-6 text-center py-6"
                    )
                trace_count_badge.set_text("0")
                trace_count_badge.props("color=grey-6")
            else:
                trace_count_badge.set_text(str(len(serialized_traces)))
                trace_count_badge.props("color=primary")
                with trace_container:
                    for td in serialized_traces:
                        _, label = self._classify_trace_step(td)
                        td["_display_label"] = label

                    rendered_phase_view = self._render_autodan_phase_timeline(
                        serialized_traces
                    )
                    if rendered_phase_view:
                        # AutoDAN phase view is authoritative; hide generic
                        # fallback sections to avoid duplicated Evaluation/Goal
                        # blocks below Lifelong/Evaluation.
                        pass
                    elif self._is_tap_trace_set(serialized_traces):
                        self._render_tap_trace_tree_view(serialized_traces)
                    else:
                        self._render_standard_trace_sections(serialized_traces)
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
        self.recent_runs_table.rows.clear()
        self.recent_runs_table.rows.extend(rows)
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
        result = self.backend.list_runs(
            page=self.runs_current_page,
            page_size=_RUNS_VIEW_PAGE_SIZE,
        )
        self.runs_total_pages = max(
            1,
            (result.total + _RUNS_VIEW_PAGE_SIZE - 1) // _RUNS_VIEW_PAGE_SIZE,
        )
        if self.runs_current_page > self.runs_total_pages:
            self.runs_current_page = self.runs_total_pages
            result = self.backend.list_runs(
                page=self.runs_current_page,
                page_size=_RUNS_VIEW_PAGE_SIZE,
            )

        run_attack_ids = {str(run.attack_id) for run in result.items}
        run_agent_ids = {str(run.agent_id) for run in result.items}
        attack_type_by_id = self._attack_type_map_for_ids(run_attack_ids)
        agent_name_by_id = self._agent_name_map_for_ids(run_agent_ids)
        rows = []
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
                result.total
                - ((self.runs_current_page - 1) * _RUNS_VIEW_PAGE_SIZE + idx),
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
            rows.append(d)

        # Render expandable run list in the runs area
        if self._history_runs_area is not None:
            self._history_runs_area.clear()
            with self._history_runs_area:
                self._render_runs_table(rows, result.total)

        start = (
            (self.runs_current_page - 1) * _RUNS_VIEW_PAGE_SIZE + 1
            if result.total
            else 0
        )
        end = start + len(rows) - 1 if rows else 0
        self.runs_count_label.text = f"Showing {start}-{end} of {result.total} run{'s' if result.total != 1 else ''}"
        if self.runs_page_label is not None:
            self.runs_page_label.text = (
                f"Page {self.runs_current_page} / {self.runs_total_pages}"
            )

    def _render_runs_table(self, rows: list[dict], total: int) -> None:
        """Render expandable run rows as a table-like layout."""
        self._history_visible_run_ids = [str(r.get("id") or "") for r in rows]

        def _toggle_all(e) -> None:
            checked = bool(e.value)
            page_ids = [rid for rid in self._history_visible_run_ids if rid]
            if checked:
                for rid in page_ids:
                    if rid not in self._selected_run_ids:
                        self._selected_run_ids.append(rid)
            else:
                self._selected_run_ids = [
                    rid for rid in self._selected_run_ids if rid not in page_ids
                ]
            self._on_runs_select()
            ui.timer(0, self._load_runs, once=True)

        all_checked = bool(self._history_visible_run_ids) and all(
            rid in self._selected_run_ids for rid in self._history_visible_run_ids
        )

        # Header row
        with ui.row().classes(
            "w-full min-w-[1220px] flex-nowrap items-center px-3 py-2 border-b "
            "border-grey-3 text-xs font-semibold text-grey-6 gap-0"
        ):
            with ui.element("div").classes("w-10 flex items-center justify-center"):
                ui.checkbox(value=all_checked, on_change=_toggle_all).props("dense")
            ui.label("").classes("w-8")  # expand chevron
            ui.label("Run #").classes("w-16")
            ui.label("Agent").classes("flex-1 min-w-24")
            ui.label("Attack").classes("w-32")
            ui.label("Status").classes("w-28")
            ui.label("Total Latency").classes("w-24")
            ui.label("Per-Goal Latency (AVG)").classes("w-32")
            ui.label("Timestamp").classes("w-28")
            ui.label("ASR").classes("w-16")

        for run_row in rows:
            self._render_expandable_run_row(run_row)

    def _render_expandable_run_row(self, run: dict) -> None:
        """Render a single run row with inline expansion for goals."""
        run_id = str(run.get("id") or "")
        status = str(run.get("status") or "—")
        status_color = (
            "positive"
            if status == "COMPLETED"
            else "info"
            if status == "RUNNING"
            else "negative"
            if status == "FAILED"
            else "warning"
        )

        # Container for the run + its expanded goals
        run_container = ui.column().classes("w-full gap-0")
        with run_container:
            row_shell = ui.row().classes(
                "w-full min-w-[1220px] flex-nowrap items-center px-3 py-2 border-b "
                "border-grey-2 gap-0 hover:bg-grey-1 dark:hover:bg-grey-9 transition-colors"
            )

            run_checked = run_id in self._selected_run_ids

            def _toggle_selected(e, rid=run_id) -> None:
                checked = bool(e.value)
                if checked:
                    if rid not in self._selected_run_ids:
                        self._selected_run_ids.append(rid)
                else:
                    self._selected_run_ids = [
                        x for x in self._selected_run_ids if x != rid
                    ]
                self._on_runs_select()

            with row_shell:
                with ui.element("div").classes("w-10 flex items-center justify-center"):
                    ui.checkbox(value=run_checked, on_change=_toggle_selected).props(
                        "dense"
                    )

                run_header = ui.row().classes(
                    "flex-1 flex-nowrap items-center gap-0 cursor-pointer"
                )
                with run_header:
                    ui.icon("expand_more", size="sm").classes(
                        "w-8 text-grey-6 transition-transform"
                    )
                    ui.label(str(run.get("run_progress", "—"))).classes(
                        "w-16 font-mono text-sm font-medium whitespace-nowrap"
                    )
                    ui.label(str(run.get("agent_name") or "—")).classes(
                        "flex-1 min-w-24 text-sm truncate whitespace-nowrap"
                    )
                    with ui.element("div").classes("w-32"):
                        ui.badge(
                            str(run.get("attack_type") or "—"), color="orange"
                        ).classes("text-xs")
                    with ui.element("div").classes("w-28"):
                        ui.badge(status, color=status_color).classes("text-xs")
                        if status == "RUNNING":
                            ui.spinner(color="info", size="xs").classes("ml-1")
                    ui.label(str(run.get("_latency") or "—")).classes("w-24 text-sm")
                    ui.label(str(run.get("_goal_latency_avg") or "—")).classes(
                        "w-32 text-sm"
                    )
                    with ui.column().classes("w-28 gap-0"):
                        ui.label(str(run.get("_rel") or "—")).classes("text-xs")
                        ui.label(str(run.get("_date") or "—")).classes(
                            "text-[10px] text-grey-6"
                        )

                    jb = int(run.get("successful_jailbreaks") or 0)
                    failed_attacks = int(run.get("failed_attacks") or 0)
                    denominator = jb + failed_attacks
                    asr_value = str(run.get("overall_asr") or "").strip()
                    if not asr_value:
                        asr_value = (
                            f"{(jb * 100.0 / denominator):.1f}%"
                            if denominator > 0
                            else "—"
                        )
                    ui.label(asr_value).classes("w-16 text-sm")

            # Goals area (kept for structural compatibility but unused)
            ui.column().classes("w-full gap-0").style("display:none")

            def _open_dialog(r=run):
                ui.timer(
                    0,
                    lambda rr=r: asyncio.create_task(
                        self._open_run_history_results(rr)
                    ),
                    once=True,
                )

            run_header.on("click", lambda e, fn=_open_dialog: fn())

            # Auto-open dialog when navigation requested from Dashboard -> Recent Runs.
            if self._history_expanded_run_id == run_id:
                self._history_expanded_run_id = None
                ui.timer(
                    0,
                    lambda r=run: asyncio.create_task(
                        self._open_run_history_results(r)
                    ),
                    once=True,
                )

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
                    if goal_multi_metrics:
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
                            majority_vote_asr is not None and majority_vote_asr > 0.5
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

                        strictness = run_eval_summary.get("per_judge_strictness")
                        if not isinstance(strictness, dict):
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

    async def _open_run_results(self, run: dict) -> None:  # noqa: C901
        """Open report details side-by-side for a single run."""
        run_id_raw = str(run.get("id") or "")
        self._report_current_run = run

        report_area: ui.column | None = self.run_report_area
        if self.run_dialog_title is not None:
            self.run_dialog_title.text = f"Report — Run {run_id_raw[:8]}…"
        self._report_results_left_col = None
        self._report_goal_detail_panel = None
        self._report_current_run_results = []

        # ── Resolve run configuration ─────────────────────────────────
        raw_run_config = run.get("run_config")
        run_config: object = {}
        raw_config_is_str = False
        if isinstance(raw_run_config, dict):
            run_config = raw_run_config
        elif isinstance(raw_run_config, str) and raw_run_config.strip():
            try:
                run_config = json.loads(raw_run_config)
            except Exception:
                run_config = raw_run_config
                raw_config_is_str = True

        if not run_config:
            with contextlib.suppress(Exception):
                fetched_run = self.backend.get_run(UUID(run_id_raw))
                fetched_dict = _serialize(fetched_run)
                fetched_raw = fetched_dict.get("run_config")
                if isinstance(fetched_raw, dict):
                    run_config = fetched_raw
                    raw_config_is_str = False
                elif isinstance(fetched_raw, str) and fetched_raw.strip():
                    try:
                        run_config = json.loads(fetched_raw)
                        raw_config_is_str = False
                    except Exception:
                        run_config = fetched_raw
                        raw_config_is_str = True

        # ── Show loading skeleton immediately ─────────────────────────
        if report_area is not None:
            report_area.clear()
            with report_area:
                with ui.row().classes("items-center gap-2 py-8 justify-center w-full"):
                    ui.spinner("dots", size="xl")
                    ui.label("Loading report…").classes("text-sm text-grey-6")
        if self.run_dialog is not None:
            self.run_dialog.open()
        await asyncio.sleep(0)

        # ── Fetch results ─────────────────────────────────────────────
        try:
            run_uuid = UUID(run_id_raw)

            def _fetch_results():
                items = []
                pg = 1
                while True:
                    rp = self.backend.list_results(
                        run_id=run_uuid, page=pg, page_size=100
                    )
                    items.extend(rp.items)
                    total = int(rp.total or 0)
                    if (total > 0 and len(items) >= total) or not rp.items:
                        break
                    pg += 1
                return items

            all_items = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_results
            )

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

            new_rows = []
            n_jailbreaks = n_mitigated = n_errors = 0
            goal_latencies: list[float] = []
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
                d["evaluation_label"] = _eval_label(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["evaluation_notes"] = d.get("evaluation_notes") or "—"
                d["_goal_latency_s"] = self._extract_goal_latency_seconds(d)
                d["_goal_latency"] = _format_latency(d.get("_goal_latency_s"))
                bucket = _result_bucket(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["_bucket"] = bucket
                if bucket == "jailbreak":
                    n_jailbreaks += 1
                elif bucket == "mitigated":
                    n_mitigated += 1
                elif bucket == "failed":
                    n_errors += 1
                lat = d.get("_goal_latency_s")
                if isinstance(lat, (int, float)):
                    goal_latencies.append(float(lat))
                new_rows.append(d)

            total_tests = len(new_rows)
            self._report_current_run_results = new_rows
            asr_pct = (100.0 * n_jailbreaks / total_tests) if total_tests > 0 else 0.0
            robustness_pct = 100.0 - asr_pct
            risk_label, risk_badge_color = self._risk_level_from_asr(asr_pct)
            risk_hex = (
                "#ef4444"
                if asr_pct >= 70
                else "#f97316"
                if asr_pct >= 40
                else "#eab308"
                if asr_pct >= 10
                else "#22c55e"
            )

            category_stats: dict[str, dict[str, int]] = defaultdict(
                lambda: {"total": 0, "vulnerable": 0, "mitigated": 0, "errors": 0}
            )
            category_subcategory_stats: dict[str, dict[str, dict[str, int]]] = (
                defaultdict(lambda: defaultdict(lambda: {"total": 0, "vulnerable": 0}))
            )
            for row in new_rows:
                label = self._extract_category_label(row)
                if not label:
                    continue
                bucket = row.get("_bucket", "pending")
                entry = category_stats[label]
                entry["total"] += 1
                if bucket == "jailbreak":
                    entry["vulnerable"] += 1
                elif bucket == "mitigated":
                    entry["mitigated"] += 1
                elif bucket == "failed":
                    entry["errors"] += 1

                sub_label = row.get("_goal_subcategory") or "N/A"
                sub_entry = category_subcategory_stats[str(label)][str(sub_label)]
                sub_entry["total"] += 1
                if bucket == "jailbreak":
                    sub_entry["vulnerable"] += 1

            status_str = str(run.get("status") or "—")
            agent_str = str(run.get("agent_name") or "—")
            attack_str = str(run.get("attack_type") or "—")
            created_str = _short_date(run.get("created_at") or run.get("timestamp"))

            if (not agent_str or agent_str == "—") and run.get("agent_id"):
                agent_id = str(run.get("agent_id") or "")
                if agent_id:
                    agent_str = self._agent_name_map_for_ids({agent_id}).get(
                        agent_id, agent_str
                    )
            if (not attack_str or attack_str == "—") and run.get("attack_id"):
                attack_id = str(run.get("attack_id") or "")
                if attack_id:
                    attack_str = self._attack_type_map_for_ids({attack_id}).get(
                        attack_id, attack_str
                    )
            run_latency_s = self._compute_run_latency_seconds(run)
            run_latency_str = _format_latency(run_latency_s)
            avg_goal_latency_str = _format_latency(
                sum(goal_latencies) / len(goal_latencies) if goal_latencies else None
            )

        except Exception as exc:
            if report_area is not None:
                report_area.clear()
                with report_area:
                    with ui.row().classes("gap-2 items-center py-8"):
                        ui.icon("error_outline", color="negative")
                        ui.label(f"Failed to load results: {exc}").classes(
                            "text-sm text-negative"
                        )
            ui.notify(f"Error loading results: {exc}", type="negative")
            return

        # ── Build report UI ───────────────────────────────────────────
        if report_area is None:
            return
        report_area.clear()

        with report_area:
            # ── 1) Summary stat cards ─────────────────────────────────
            with ui.row().classes("w-full flex-wrap gap-4"):
                for s_label, s_value, s_icon, s_color in [
                    ("Total Tests", str(total_tests), "quiz", "blue"),
                    ("Vulnerabilities", str(n_jailbreaks), "lock_open", "red"),
                    ("Mitigated", str(n_mitigated), "security", "green"),
                    ("Errors", str(n_errors), "warning_amber", "orange"),
                ]:
                    with ui.card().classes("flex-1 min-w-36"):
                        with ui.row().classes("items-center justify-between mb-2"):
                            ui.label(s_label).classes("text-sm text-grey-6")
                            ui.icon(s_icon, color=s_color).classes("text-xl")
                        ui.label(s_value).classes("text-3xl font-bold")

            # ── 2) Risk Score + Robustness ────────────────────────────
            with ui.row().classes("w-full flex-wrap gap-4 items-stretch"):
                # Risk donut
                with ui.card().classes("flex-1 min-w-64"):
                    ui.label("Risk Score").classes("font-semibold text-sm mb-1")
                    ui.label(
                        "Attack Success Rate across all tests in this run"
                    ).classes("text-xs text-grey-6 mb-3")
                    with ui.row().classes("items-center gap-6 flex-wrap"):
                        no_data = total_tests == 0
                        ui.echart(
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
                                                    "value": n_jailbreaks,
                                                    "name": "Jailbreaks",
                                                    "itemStyle": {"color": "#ef4444"},
                                                },
                                                {
                                                    "value": n_mitigated,
                                                    "name": "Mitigated",
                                                    "itemStyle": {"color": "#22c55e"},
                                                },
                                                {
                                                    "value": n_errors,
                                                    "name": "Errors",
                                                    "itemStyle": {"color": "#f97316"},
                                                },
                                                {
                                                    "value": max(
                                                        0,
                                                        total_tests
                                                        - n_jailbreaks
                                                        - n_mitigated
                                                        - n_errors,
                                                    ),
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
                                                        "text": f"{asr_pct:.0f}%",
                                                        "textAlign": "center",
                                                        "fontSize": 22,
                                                        "fontWeight": "bold",
                                                        "fill": risk_hex,
                                                    },
                                                    "top": -14,
                                                },
                                                {
                                                    "type": "text",
                                                    "style": {
                                                        "text": risk_label,
                                                        "textAlign": "center",
                                                        "fontSize": 11,
                                                        "fill": risk_hex,
                                                    },
                                                    "top": 12,
                                                },
                                            ],
                                        }
                                    ]
                                ),
                                "tooltip": {
                                    "trigger": "item" if not no_data else "none"
                                },
                            }
                        ).classes("w-36 h-36 shrink-0")

                        # Legend beside donut
                        with ui.column().classes("gap-1"):
                            for leg_label, leg_count, leg_color in [
                                ("Jailbreaks", n_jailbreaks, "#ef4444"),
                                ("Mitigated", n_mitigated, "#22c55e"),
                                ("Errors", n_errors, "#f97316"),
                                (
                                    "Pending",
                                    max(
                                        0,
                                        total_tests
                                        - n_jailbreaks
                                        - n_mitigated
                                        - n_errors,
                                    ),
                                    "#94a3b8",
                                ),
                            ]:
                                if leg_count > 0 or not no_data:
                                    with ui.row().classes("items-center gap-2"):
                                        ui.element("div").classes(
                                            "w-2.5 h-2.5 rounded-full shrink-0"
                                        ).style(f"background:{leg_color}")
                                        ui.label(f"{leg_label}: {leg_count}").classes(
                                            "text-xs"
                                        )

                # Robustness bar
                with ui.card().classes("flex-1 min-w-64"):
                    ui.label("Robustness").classes("font-semibold text-sm mb-1")
                    ui.label(
                        "Percentage of tests the agent successfully resisted"
                    ).classes("text-xs text-grey-6 mb-3")

                    with ui.column().classes("gap-3 w-full"):
                        with ui.row().classes("items-end gap-2"):
                            ui.label(f"{robustness_pct:.0f}%").classes(
                                "text-4xl font-bold"
                            )
                            robustness_color = (
                                "positive"
                                if robustness_pct >= 80
                                else "warning"
                                if robustness_pct >= 50
                                else "negative"
                            )
                            robustness_word = (
                                "Strong"
                                if robustness_pct >= 80
                                else "Moderate"
                                if robustness_pct >= 50
                                else "Weak"
                            )
                            ui.badge(robustness_word, color=robustness_color).classes(
                                "text-xs mb-1"
                            )

                        ui.linear_progress(
                            value=robustness_pct / 100.0,
                            show_value=False,
                            color=(
                                "positive"
                                if robustness_pct >= 80
                                else "warning"
                                if robustness_pct >= 50
                                else "negative"
                            ),
                        ).classes("w-full").props("rounded size=12px")

                        with ui.row().classes("w-full justify-between"):
                            ui.label(f"{n_mitigated} mitigated").classes(
                                "text-xs text-grey-6"
                            )
                            ui.label(f"{n_jailbreaks} vulnerable").classes(
                                "text-xs text-grey-6"
                            )

            # ── 2b) Robustness by Category (radar) ───────────────────
            if category_stats:
                category_items = []
                for label, stats in category_stats.items():
                    total = int(stats.get("total") or 0)
                    vulnerable = int(stats.get("vulnerable") or 0)
                    mitigated = int(stats.get("mitigated") or 0)
                    if total <= 0:
                        continue
                    robustness = 100.0 * (total - vulnerable) / total
                    sub_stats = category_subcategory_stats.get(label, {})
                    sub_rows = []
                    for sub_label, sub_counts in sub_stats.items():
                        sub_total = int(sub_counts.get("total") or 0)
                        sub_vulnerable = int(sub_counts.get("vulnerable") or 0)
                        if sub_total <= 0:
                            continue
                        sub_rows.append(
                            {
                                "label": str(sub_label),
                                "total": sub_total,
                                "vulnerable": sub_vulnerable,
                                "rate": sub_vulnerable / sub_total,
                            }
                        )
                    sub_rows.sort(
                        key=lambda item: (item["rate"], item["total"]), reverse=True
                    )
                    category_items.append(
                        {
                            "label": label,
                            "total": total,
                            "vulnerable": vulnerable,
                            "mitigated": mitigated,
                            "errors": int(stats.get("errors") or 0),
                            "robustness": robustness,
                            "vuln_rate": vulnerable / total,
                            "subcategories": sub_rows,
                        }
                    )

                category_items.sort(
                    key=lambda item: (item["vuln_rate"], item["total"]),
                    reverse=True,
                )
                top_items = category_items[:9]
                top_items.sort(key=lambda item: item["label"])
                if len(top_items) > 1:
                    top_items = [top_items[0], *reversed(top_items[1:])]

                def _wrap_label(text: str, line_limit: int = 18) -> str:
                    text = str(text).strip()
                    if not text:
                        return text
                    words = text.split()
                    lines = []
                    current_line = words[0]
                    for word in words[1:]:
                        candidate = f"{current_line} {word}"
                        if len(candidate) <= line_limit:
                            current_line = candidate
                        else:
                            lines.append(current_line)
                            current_line = word
                    lines.append(current_line)
                    return "\n".join(lines)

                def _format_indicator_name(item: dict) -> str:
                    wrapped_label = _wrap_label(item["label"])
                    robustness_pct = item["robustness"]
                    return f"{wrapped_label}\n{robustness_pct:.0f}%"

                def _build_category_tooltip(item: dict) -> str:
                    lines = [
                        f"<div style='font-size:14px;font-weight:700;margin-bottom:4px'>{item['label']}</div>",
                        f"<div>Robustness: <span style='color:#16a34a;font-weight:700'>{item['robustness']:.0f}%</span></div>",
                        f"<div>Vulnerable: <span style='color:#ef4444;font-weight:700'>{item['vulnerable']} / {item['total']}</span></div>",
                        f"<div>Mitigated: <span style='color:#22c55e;font-weight:700'>{item['mitigated']}</span></div>",
                        f"<div>Error: <span style='color:#f59e0b;font-weight:700'>{item['errors']}</span></div>",
                    ]
                    if item["subcategories"]:
                        lines.append(
                            "<div style='margin-top:6px;font-weight:600'>Subcategory vulnerabilities</div>"
                        )
                        for sub_item in item["subcategories"][:8]:
                            lines.append(
                                f"<div>{sub_item['label']}: {sub_item['vulnerable']} / {sub_item['total']}</div>"
                            )
                    return "".join(lines)

                indicators = [
                    {"name": _format_indicator_name(item), "max": 100}
                    for item in top_items
                ]
                indicator_labels = [indicator["name"] for indicator in indicators]
                full_labels = [item["label"] for item in top_items]
                values = [round(item["robustness"], 1) for item in top_items]
                category_tooltips = [
                    _build_category_tooltip(item) for item in top_items
                ]

                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-start justify-between mb-1"):
                        with ui.column().classes("gap-0"):
                            ui.label("OVERALL ROBUSTNESS").classes(
                                "text-[10px] tracking-[0.24em] text-grey-6 font-semibold"
                            )
                            ui.label(f"{robustness_pct:.0f}%").classes(
                                "text-[44px] leading-none font-bold text-green-7"
                            )

                    with ui.row().classes("w-full justify-center"):
                        ui.echart(
                            {
                                "toolbox": {
                                    "show": True,
                                    "right": 8,
                                    "top": 4,
                                    "feature": {
                                        "saveAsImage": {
                                            "show": True,
                                            "type": "svg",
                                            "title": "Download SVG",
                                            "name": "robustness-by-category",
                                        }
                                    },
                                },
                                "tooltip": {
                                    "trigger": "axis",
                                    ":formatter": (
                                        "function(params) {"
                                        "const p = Array.isArray(params) ? (params[0] || {}) : (params || {});"
                                        "const d = (p && p.data) || {};"
                                        "const categoryTooltips = Array.isArray(d.categoryTooltips) ? d.categoryTooltips : [];"
                                        "if (!categoryTooltips.length) { return ''; }"
                                        "const indicatorLabels = Array.isArray(d.indicatorLabels) ? d.indicatorLabels : [];"
                                        "const fullLabels = Array.isArray(d.fullLabels) ? d.fullLabels : [];"
                                        "const normalizeName = function(value) {"
                                        "  return String(value || '')"
                                        "    .replace(/\\n+/g, ' ')"
                                        "    .replace(/\\s+\\d+(?:\\.\\d+)?%$/i, '')"
                                        "    .trim();"
                                        "};"
                                        "const candidates = [];"
                                        "if (typeof p.axisValueLabel === 'string' && p.axisValueLabel.length > 0) { candidates.push(p.axisValueLabel); }"
                                        "if (typeof p.axisValue === 'string' && p.axisValue.length > 0) { candidates.push(p.axisValue); }"
                                        "if (typeof p.name === 'string' && p.name.length > 0) { candidates.push(p.name); }"
                                        "for (const name of candidates) {"
                                        "  let idx = indicatorLabels.indexOf(name);"
                                        "  if (idx < 0) { idx = fullLabels.indexOf(name); }"
                                        "  if (idx < 0) {"
                                        "    const normalized = normalizeName(name);"
                                        "    idx = fullLabels.findIndex((label) => normalizeName(label) === normalized);"
                                        "  }"
                                        "  if (idx >= 0 && idx < categoryTooltips.length) { return categoryTooltips[idx] || ''; }"
                                        "}"
                                        "const dimensionIndex = typeof p.dimensionIndex === 'number' ? p.dimensionIndex : -1;"
                                        "if (dimensionIndex >= 0 && dimensionIndex < categoryTooltips.length) {"
                                        "  return categoryTooltips[dimensionIndex] || '';"
                                        "}"
                                        "return categoryTooltips[0] || '';"
                                        "}"
                                    ),
                                    "backgroundColor": "#ffffff",
                                    "borderColor": "#d1d5db",
                                    "borderWidth": 1,
                                    "textStyle": {"color": "#111827", "fontSize": 13},
                                    "padding": 10,
                                },
                                "radar": {
                                    "shape": "polygon",
                                    "indicator": indicators,
                                    "splitNumber": 5,
                                    "center": ["50%", "49%"],
                                    "radius": "64%",
                                    "axisName": {
                                        "fontSize": 12,
                                        "lineHeight": 15,
                                        "color": "#111827",
                                        "fontWeight": 500,
                                    },
                                    "splitLine": {"lineStyle": {"color": "#d1d5db"}},
                                    "splitArea": {"areaStyle": {"color": ["#ffffff"]}},
                                },
                                "series": [
                                    {
                                        "type": "radar",
                                        "silent": False,
                                        "z": 3,
                                        "symbol": "circle",
                                        "symbolSize": 11,
                                        "itemStyle": {
                                            "color": "#dc2626",
                                            "borderColor": "#ffffff",
                                            "borderWidth": 1.5,
                                        },
                                        "lineStyle": {
                                            "color": "#3b82f6",
                                            "width": 2,
                                        },
                                        "areaStyle": {
                                            "color": "rgba(59, 130, 246, 0.18)"
                                        },
                                        "data": [
                                            {
                                                "value": values,
                                                "name": "Robustness",
                                                "categoryTooltips": category_tooltips,
                                                "indicatorLabels": indicator_labels,
                                                "fullLabels": full_labels,
                                            }
                                        ],
                                    },
                                ],
                            }
                        ).classes("w-[740px] h-[500px] max-w-full").props(
                            "renderer=svg"
                        )

                    ui.label(
                        "Robustness = 100 - vulnerability rate per category. Hover a point for details."
                    ).classes("text-xs text-grey-6 w-full text-center mt-2")

                with ui.card().classes("w-full"):
                    ui.label("Vulnerability by Category").classes(
                        "font-semibold text-sm mb-1"
                    )
                    ui.label(
                        "Stacked distribution of outcomes per harm category"
                    ).classes("text-xs text-grey-6 mb-3")

                    bar_items = list(reversed(top_items))
                    bar_y_labels = [item["label"] for item in bar_items]
                    vulnerable_data = []
                    mitigated_data = []
                    error_data = []

                    for item in bar_items:
                        tooltip_text = _build_category_tooltip(item)
                        vulnerable_data.append(
                            {
                                "value": int(item["vulnerable"]),
                                "name": item["label"],
                                "tooltip": {"formatter": tooltip_text},
                            }
                        )
                        mitigated_data.append(
                            {
                                "value": int(item["mitigated"]),
                                "name": item["label"],
                                "tooltip": {"formatter": tooltip_text},
                            }
                        )
                        error_data.append(
                            {
                                "value": int(item["errors"]),
                                "name": item["label"],
                                "tooltip": {"formatter": tooltip_text},
                            }
                        )

                    ui.echart(
                        {
                            "tooltip": {
                                "trigger": "item",
                                "backgroundColor": "#ffffff",
                                "borderColor": "#d1d5db",
                                "borderWidth": 1,
                                "textStyle": {"color": "#111827", "fontSize": 13},
                                "padding": 10,
                            },
                            "legend": {
                                "bottom": 0,
                                "itemWidth": 12,
                                "itemHeight": 10,
                                "textStyle": {"fontSize": 12},
                            },
                            "grid": {
                                "left": "16%",
                                "right": "2%",
                                "top": "8%",
                                "bottom": "18%",
                                "containLabel": True,
                            },
                            "xAxis": {
                                "type": "value",
                                "splitLine": {
                                    "lineStyle": {"type": "dashed", "color": "#e5e7eb"}
                                },
                            },
                            "yAxis": {
                                "type": "category",
                                "data": bar_y_labels,
                                "axisTick": {"show": False},
                                "axisLabel": {
                                    "fontSize": 11,
                                    "lineHeight": 14,
                                    "interval": 0,
                                },
                            },
                            "series": [
                                {
                                    "name": "Vulnerable",
                                    "type": "bar",
                                    "stack": "total",
                                    "itemStyle": {"color": "#ef4444"},
                                    "emphasis": {"disabled": True},
                                    "data": vulnerable_data,
                                },
                                {
                                    "name": "Mitigated",
                                    "type": "bar",
                                    "stack": "total",
                                    "itemStyle": {"color": "#22c55e"},
                                    "emphasis": {"disabled": True},
                                    "data": mitigated_data,
                                },
                                {
                                    "name": "Error",
                                    "type": "bar",
                                    "stack": "total",
                                    "itemStyle": {"color": "#f59e0b"},
                                    "emphasis": {"disabled": True},
                                    "data": error_data,
                                },
                            ],
                        }
                    ).classes("w-full h-[320px]")

            # ── 3) Scope of Testing ───────────────────────────────────
            with ui.card().classes("w-full"):
                ui.label("Scope of Testing").classes("font-semibold text-sm mb-3")
                with ui.row().classes("w-full flex-wrap gap-x-8 gap-y-2"):
                    for info_label, info_value, info_icon in [
                        ("Run ID", f"{run_id_raw[:12]}…", "fingerprint"),
                        ("Agent", agent_str, "smart_toy"),
                        ("Attack", attack_str, "flash_on"),
                        ("Status", status_str, "flag"),
                        ("Created", created_str, "schedule"),
                        ("Duration", run_latency_str, "timer"),
                        ("Avg Goal Latency", avg_goal_latency_str, "speed"),
                    ]:
                        with ui.row().classes("items-center gap-2"):
                            ui.icon(info_icon, size="xs").classes(
                                "text-grey-6 shrink-0"
                            )
                            ui.label(f"{info_label}:").classes(
                                "text-xs text-grey-6 font-semibold"
                            )
                            ui.label(str(info_value)).classes(
                                "text-xs font-mono select-all"
                            )

            # ── 4) Configuration (expandable) ─────────────────────────
            if run_config:
                with ui.expansion("Configuration", icon="settings").classes("w-full"):
                    config_text = (
                        json.dumps(run_config, indent=2, default=str)
                        if not raw_config_is_str and not isinstance(run_config, str)
                        else str(run_config)
                    )
                    ui.code(config_text, language="json").classes("w-full text-xs")

            # ── 5) Test Results ───────────────────────────────────────
            with ui.column().classes("w-full gap-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("TEST RESULTS").classes(
                        "text-[10px] font-semibold tracking-widest "
                        "text-grey-5 uppercase"
                    )
                    ui.badge(str(total_tests), color="primary").classes("text-xs")

                if not new_rows:
                    ui.label("No results found for this run.").classes(
                        "text-sm text-grey-6 py-4"
                    )
                else:
                    with ui.row().classes(
                        "w-full gap-0 items-stretch h-[calc(100vh-360px)] min-h-[420px] overflow-hidden"
                    ):
                        self._report_results_left_col = ui.column().classes(
                            "w-full h-full min-h-0 gap-2 transition-all duration-300"
                        )
                        with self._report_results_left_col:
                            with ui.scroll_area().classes("w-full flex-1 min-h-0"):
                                with ui.column().classes("w-full gap-2"):
                                    for row in new_rows:
                                        bucket = row.get("_bucket", "pending")
                                        border_color = (
                                            "border-red-400"
                                            if bucket == "jailbreak"
                                            else "border-green-400"
                                            if bucket == "mitigated"
                                            else "border-orange-400"
                                            if bucket == "failed"
                                            else "border-grey-300"
                                        )
                                        with (
                                            ui.card()
                                            .tight()
                                            .classes(
                                                f"w-full border-l-4 {border_color}"
                                            )
                                        ):
                                            with ui.column().classes(
                                                "w-full gap-2 p-4"
                                            ):
                                                with ui.row().classes(
                                                    "items-center justify-between w-full"
                                                ):
                                                    with ui.column().classes("gap-1"):
                                                        ui.label(
                                                            f"Goal #{row.get('goal_number', '?')}"
                                                        ).classes(
                                                            "font-semibold text-sm"
                                                        )
                                                        ui.badge(
                                                            self._goal_category_badge_text(
                                                                row
                                                            ),
                                                            color="blue-7",
                                                        ).classes(
                                                            "text-sm px-3 py-2 font-medium"
                                                        )

                                                    with ui.row().classes(
                                                        "items-center gap-3"
                                                    ):
                                                        ui.badge(
                                                            row.get("evaluation_label")
                                                            or "Pending",
                                                            color=_eval_color(
                                                                row.get(
                                                                    "evaluation_status",
                                                                    "",
                                                                ),
                                                                row.get(
                                                                    "evaluation_notes"
                                                                ),
                                                            ),
                                                        ).classes("text-xs")

                                                    with ui.row().classes(
                                                        "items-center gap-2"
                                                    ):
                                                        ui.badge(
                                                            f"Latency: {row.get('_goal_latency', '—')}",
                                                            color="grey-7",
                                                        ).classes("text-xs")
                                                        ui.button(
                                                            "Details",
                                                            icon="open_in_new",
                                                            on_click=lambda r=row: (
                                                                ui.timer(
                                                                    0,
                                                                    lambda rr=r: (
                                                                        asyncio.create_task(
                                                                            self._open_report_goal_detail(
                                                                                rr
                                                                            )
                                                                        )
                                                                    ),
                                                                    once=True,
                                                                )
                                                            ),
                                                        ).props(
                                                            "flat dense no-caps color=primary"
                                                        )

                                                ui.label(
                                                    str(row.get("goal") or "—")
                                                ).classes("text-sm whitespace-pre-wrap")

                                                notes = str(
                                                    row.get("evaluation_notes") or "—"
                                                )
                                                if notes != "—":
                                                    ui.label(notes).classes(
                                                        "text-xs text-grey-6 whitespace-pre-wrap"
                                                    )

                        self._report_goal_detail_panel = (
                            ui.column()
                            .classes("h-full min-h-0 gap-0 border-l shrink-0")
                            .style(
                                "width: 0; min-width: 0; overflow: hidden; "
                                "transition: all 0.3s ease;"
                            )
                        )

    async def _open_run_history_results(self, run: dict) -> None:
        """Open the compact results list dialog for History/Dashboard views."""
        run_id_raw = str(run.get("id") or "")

        if self.history_run_dialog_title is not None:
            self.history_run_dialog_title.text = f"Run Results — {run_id_raw[:8]}…"

        agent = str(run.get("agent_name") or "—")
        _hr_jailbreaks = int(run.get("successful_jailbreaks") or 0)
        _hr_errors = int(run.get("errors") or 0)
        _hr_run_latency_str = _format_latency(self._compute_run_latency_seconds(run))

        raw_run_config = run.get("run_config")
        run_config = {}
        fetched_dict = None
        if isinstance(raw_run_config, dict):
            run_config = raw_run_config
        elif isinstance(raw_run_config, str) and raw_run_config.strip():
            try:
                run_config = json.loads(raw_run_config)
            except Exception:
                run_config = raw_run_config

        if not run_config:
            with contextlib.suppress(Exception):
                fetched_run = self.backend.get_run(UUID(run_id_raw))
                fetched_dict = _serialize(fetched_run)
                fetched_raw = fetched_dict.get("run_config")
                if isinstance(fetched_raw, dict):
                    run_config = fetched_raw
                elif isinstance(fetched_raw, str) and fetched_raw.strip():
                    try:
                        run_config = json.loads(fetched_raw)
                    except Exception:
                        run_config = fetched_raw
        # Configuration panel should show ATTACK configuration (not run metrics payload).
        display_config: object = {}
        attack_id = str(run.get("attack_id") or "")
        if not attack_id and isinstance(fetched_dict, dict):
            attack_id = str(fetched_dict.get("attack_id") or "")

        if attack_id:
            with contextlib.suppress(Exception):
                attack_cfgs = self._attack_config_map_for_ids({attack_id})
                cfg = attack_cfgs.get(attack_id)
                if isinstance(cfg, dict) and cfg:
                    display_config = cfg

        if not display_config:
            if isinstance(run_config, dict):
                # Fallback: strip evaluation summary noise from run_config view.
                display_config = {
                    k: v for k, v in run_config.items() if k != "evaluation_summary"
                }
            elif run_config:
                display_config = run_config

        # Resolve attack type early (needed by the interpretation panel below).
        attack_type_str = str(run.get("attack_type") or "—")
        if attack_type_str == "—":
            _attack_id_hr = str(run.get("attack_id") or "")
            if _attack_id_hr:
                _atm_hr = self._attack_type_map_for_ids({_attack_id_hr})
                attack_type_str = _atm_hr.get(_attack_id_hr, "—")

        if self.history_run_config_area is not None:
            self.history_run_config_area.clear()
            with self.history_run_config_area:
                _hcfg = display_config if isinstance(display_config, dict) else {}
                _hrc = run_config if isinstance(run_config, dict) else {}
                _h_evaluator_type = (
                    _hcfg.get("evaluator_type")
                    or _hrc.get("evaluator_type")
                    or "pattern"
                )
                _h_judge_cfg = (
                    _hcfg.get("judge_config") or _hrc.get("judge_config") or {}
                )
                _h_judge_model = (
                    (_h_judge_cfg.get("model_id") or _h_judge_cfg.get("model") or "")
                    if isinstance(_h_judge_cfg, dict)
                    else ""
                )
                _h_attack_str = (
                    attack_type_str
                    if attack_type_str and attack_type_str != "—"
                    else agent
                )
                _h_attack_display: dict[str, str] = {
                    "baseline": "Baseline",
                    "pair": "PAIR",
                    "tap": "TAP",
                    "bon": "Best-of-N",
                    "advprefix": "AdvPrefix",
                    "autodanturbo": "AutoDAN-Turbo",
                    "cipherchat": "CipherChat",
                    "flipattack": "FlipAttack",
                    "pap": "PAP",
                    "h4rm3l": "H4rm3l",
                }

                def _h_resolve_eval_label(
                    attack: str,
                    cfg: dict,
                    ev_type: str,
                    jmodel: str,
                ) -> str:
                    if attack.lower() == "baseline":
                        if ev_type == "llm_judge":
                            return f"LLM judge{f' · {jmodel}' if jmodel else ''}"
                        if ev_type == "keyword":
                            return "Keyword matching"
                        return "Pattern matching"
                    judges = cfg.get("judges") or []
                    if isinstance(judges, list) and judges:
                        names = []
                        for j in judges:
                            if isinstance(j, dict):
                                n = (
                                    j.get("model_id")
                                    or j.get("identifier")
                                    or j.get("model")
                                    or ""
                                )
                                if n and n not in names:
                                    names.append(n)
                        if names:
                            if len(names) == 1:
                                return f"LLM judge · {names[0]}"
                            return f"LLM judges ({len(names)}): {', '.join(names)}"
                        return (
                            f"LLM judge{'s' if len(judges) > 1 else ''} × {len(judges)}"
                        )
                    if jmodel:
                        return f"LLM judge · {jmodel}"
                    return "LLM judge"

                ui.label("CONFIGURATION").classes(
                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase mb-1"
                )

                def _chip(_ic, _il, _iv):
                    with ui.row().classes(
                        "items-center gap-1 bg-grey-1 rounded px-2 py-1"
                    ):
                        ui.icon(_ic, size="xs").classes("text-grey-6")
                        ui.label(_il).classes(
                            "text-[10px] text-grey-5 font-semibold uppercase tracking-wide"
                        )
                        ui.label(_iv).classes("text-xs font-medium text-grey-9")

                # ── Line 1: Attack + attack-specific params ───────────
                _atk_lower = _h_attack_str.lower()
                with ui.row().classes("flex-wrap gap-2 items-center"):
                    _chip(
                        "flash_on",
                        "Attack",
                        _h_attack_display.get(
                            _h_attack_str.lower(), _h_attack_str.capitalize()
                        ),
                    )
                    if _atk_lower == "flipattack":
                        _fa_params = _hcfg.get("flipattack_params") or {}
                        _flip_mode = (
                            _fa_params.get("flip_mode", "FCS")
                            if isinstance(_fa_params, dict)
                            else "FCS"
                        )
                        _flip_mode_labels = {
                            "FWO": "Flip Word Order",
                            "FCW": "Flip Chars in Word",
                            "FCS": "Flip Chars in Sentence",
                            "FMM": "Fool Model Mode",
                        }
                        _chip(
                            "flip",
                            "Mode",
                            _flip_mode_labels.get(
                                str(_flip_mode).upper(), str(_flip_mode)
                            ),
                        )
                    elif _atk_lower == "h4rm3l":
                        _h4_params = _hcfg.get("h4rm3l_params") or {}
                        _h4_program = (
                            _h4_params.get("program", "")
                            if isinstance(_h4_params, dict)
                            else ""
                        )
                        if _h4_program:
                            _chip(
                                "layers",
                                "Decorators",
                                self._format_h4rm3l_program(_h4_program),
                            )
                    elif _atk_lower == "cipherchat":
                        _cc_params = _hcfg.get("cipherchat_params") or {}
                        _cc_cipher = (
                            _cc_params.get("encode_method", "—")
                            if isinstance(_cc_params, dict)
                            else "—"
                        )
                        _chip("lock", "Cipher", str(_cc_cipher))
                    elif _atk_lower == "bon":
                        _bon_params = _hcfg.get("bon_params") or {}
                        if isinstance(_bon_params, dict):
                            _chip(
                                "auto_awesome",
                                "Steps",
                                str(_bon_params.get("n_steps", 4)),
                            )
                            _chip(
                                "auto_awesome",
                                "Candidates/step",
                                str(_bon_params.get("num_concurrent_k", 5)),
                            )
                    elif _atk_lower == "tap":
                        _tap_p = _hcfg.get("tap_params") or {}
                        if isinstance(_tap_p, dict):
                            _chip("account_tree", "Depth", str(_tap_p.get("depth", 3)))
                            _chip("width", "Width", str(_tap_p.get("width", 4)))
                            _chip(
                                "call_split",
                                "Branching",
                                str(_tap_p.get("branching_factor", 3)),
                            )

                # ── Line 2: Dataset ───────────────────────────────────
                _h_dataset_raw = _hcfg.get("dataset") or _hrc.get("dataset")
                if _h_dataset_raw is not None:
                    if isinstance(_h_dataset_raw, dict):
                        _h_ds_preset = _h_dataset_raw.get("preset") or ""
                        if _h_ds_preset:
                            _h_dataset_str = _h_ds_preset.replace("_", " ").title()
                        else:
                            _h_ds_desc = _h_dataset_raw.get("description") or ""
                            if _h_ds_desc:
                                _h_dataset_str = _h_ds_desc.split(" - ")[0].strip()
                            else:
                                _h_ds_path = _h_dataset_raw.get("path") or ""
                                _h_dataset_str = (
                                    _h_ds_path.rsplit("/", 1)[-1]
                                    if "/" in _h_ds_path
                                    else _h_ds_path or "Custom"
                                )
                    else:
                        _h_dataset_str = str(_h_dataset_raw)
                    if _h_dataset_str:
                        _h_ds_limit = (
                            _h_dataset_raw.get("limit")
                            if isinstance(_h_dataset_raw, dict)
                            else None
                        )
                        _h_ds_shuffle = (
                            _h_dataset_raw.get("shuffle")
                            if isinstance(_h_dataset_raw, dict)
                            else None
                        )
                        with ui.row().classes("flex-wrap gap-2 items-center mt-1"):
                            _chip("dataset", "Dataset", _h_dataset_str)
                            if _h_ds_limit is not None:
                                _chip("filter_list", "Limit", str(_h_ds_limit))
                            if _h_ds_shuffle is not None:
                                _chip("shuffle", "Shuffle", str(_h_ds_shuffle))

                # ── Line 3: Roles (Target, Judge/Scorer, Attacker, Generator, Decorator, …) ──
                with ui.row().classes("flex-wrap gap-2 items-center mt-1"):
                    _chip("smart_toy", "Target", agent)
                    _h_atk_lower_r = _h_attack_str.lower()
                    # PAIR / AutoDAN: scorer IS the judge — show Scorer, not Judge
                    if _h_atk_lower_r in ("pair", "autodanturbo"):
                        _h_scorer_cfg = _hcfg.get("scorer") or {}
                        if isinstance(_h_scorer_cfg, dict):
                            _h_scorer_id = (
                                _h_scorer_cfg.get("identifier")
                                or _h_scorer_cfg.get("model_id")
                                or ""
                            )
                            if _h_scorer_id:
                                _chip("analytics", "Scorer", str(_h_scorer_id))
                    else:
                        _chip(
                            "gavel",
                            "Judge",
                            _h_resolve_eval_label(
                                _h_attack_str, _hcfg, _h_evaluator_type, _h_judge_model
                            ),
                        )
                    # TAP: optional separate on-topic judge
                    if _h_atk_lower_r == "tap":
                        _h_ot_judge_cfg = _hcfg.get("on_topic_judge")
                        if isinstance(_h_ot_judge_cfg, dict):
                            _h_ot_id = (
                                _h_ot_judge_cfg.get("identifier")
                                or _h_ot_judge_cfg.get("model_id")
                                or ""
                            )
                            if _h_ot_id:
                                _chip("fact_check", "On-Topic Judge", str(_h_ot_id))
                    # Attacker LLM
                    _h_attacker_cfg = _hcfg.get("attacker") or {}
                    if isinstance(_h_attacker_cfg, dict):
                        _h_attacker_id = (
                            _h_attacker_cfg.get("identifier")
                            or _h_attacker_cfg.get("model_id")
                            or ""
                        )
                        if _h_attacker_id:
                            _chip("psychology", "Attacker", str(_h_attacker_id))
                    # AdvPrefix: generator role
                    if _h_atk_lower_r == "advprefix":
                        _h_gen_cfg = _hcfg.get("generator") or {}
                        if isinstance(_h_gen_cfg, dict):
                            _h_gen_id = (
                                _h_gen_cfg.get("identifier")
                                or _h_gen_cfg.get("model_id")
                                or ""
                            )
                            if _h_gen_id:
                                _chip("build", "Generator", str(_h_gen_id))
                    # AutoDAN: Summarizer + Embedder
                    if _h_atk_lower_r == "autodanturbo":
                        _h_summarizer_cfg = _hcfg.get("summarizer") or {}
                        if isinstance(_h_summarizer_cfg, dict):
                            _h_summarizer_id = (
                                _h_summarizer_cfg.get("identifier")
                                or _h_summarizer_cfg.get("model_id")
                                or ""
                            )
                            if _h_summarizer_id:
                                _chip("summarize", "Summarizer", str(_h_summarizer_id))
                        _h_embedder_cfg = _hcfg.get("embedder") or {}
                        if isinstance(_h_embedder_cfg, dict):
                            _h_embedder_id = (
                                _h_embedder_cfg.get("identifier")
                                or _h_embedder_cfg.get("model_id")
                                or ""
                            )
                            if _h_embedder_id:
                                _chip("hub", "Embedder", str(_h_embedder_id))
                    # h4rm3l: decorator LLM
                    if _h_atk_lower_r == "h4rm3l":
                        _h4_p = _hcfg.get("h4rm3l_params") or {}
                        _h_dec_llm_cfg = (
                            _h4_p.get("decorator_llm")
                            if isinstance(_h4_p, dict)
                            else None
                        ) or _hcfg.get("decorator_llm")
                        if isinstance(_h_dec_llm_cfg, dict):
                            _h_dec_id = (
                                _h_dec_llm_cfg.get("identifier")
                                or _h_dec_llm_cfg.get("model_id")
                                or ""
                            )
                            if _h_dec_id:
                                _chip("layers", "Decorator LLM", str(_h_dec_id))

        # ── Populate metrics area ─────────────────────────────────────────
        if self.metrics_area is not None:
            self.metrics_area.clear()
            eval_summary = (
                run_config.get("evaluation_summary")
                if isinstance(run_config, dict)
                else None
            )

            if isinstance(eval_summary, dict):
                with self.metrics_area:
                    total = eval_summary.get("total_attacks", 0)
                    overall = eval_summary.get("overall_success_rate", 0.0)
                    mv_asr = eval_summary.get("majority_vote_asr", 0.0)
                    kappa = eval_summary.get("fleiss_kappa", None)
                    per_judge = eval_summary.get("per_judge_strictness") or {}
                    _hr_n_judges = len(
                        [
                            k
                            for k in per_judge
                            if k != "bias_gap" and not k.endswith("_mean")
                        ]
                    )
                    # Use run-level goal counts for the summary cards so they
                    # match _hr_jailbreaks/_hr_errors (which are also goal-level).
                    _hr_total_goals = int(run.get("total_results") or 0) or int(total)
                    _hr_mitigated = max(
                        0, _hr_total_goals - _hr_jailbreaks - _hr_errors
                    )

                    def _fmt_pct(value: object) -> str:
                        try:
                            return f"{float(value) * 100:.1f}%"
                        except (TypeError, ValueError):
                            return str(value)

                    def _is_risky(v: object) -> bool:
                        return isinstance(v, (int, float)) and float(v) > 0

                    # ── Results Summary ───────────────────────────────
                    ui.label("RESULTS SUMMARY").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase mb-2"
                    )
                    with ui.row().classes("flex-wrap gap-2 items-start"):
                        for _ml, _mv, _mc, _mi in [
                            ("Total Attacks", str(_hr_total_goals), "grey-8", "quiz"),
                            (
                                "Jailbreaks",
                                str(_hr_jailbreaks),
                                "negative",
                                "lock_open",
                            ),
                            (
                                "Mitigated",
                                str(_hr_mitigated),
                                "positive" if _hr_mitigated > 0 else "grey-7",
                                "security",
                            ),
                            (
                                "Errors",
                                str(_hr_errors),
                                "warning" if _hr_errors > 0 else "grey-7",
                                "warning_amber",
                            ),
                            ("Duration", _hr_run_latency_str, "grey-7", "timer"),
                        ]:
                            with ui.card().classes("flex-none min-w-[110px] px-3 py-2"):
                                with ui.row().classes("items-center gap-1 mb-1"):
                                    ui.icon(_mi, color=_mc, size="xs")
                                    ui.label(_ml).classes(
                                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                                    )
                                ui.label(_mv).classes("text-xl font-bold")

                    ui.separator().classes("my-2")

                    # ── Evaluation Metrics ────────────────────────────
                    ui.label("EVALUATION METRICS").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase mb-2"
                    )
                    with ui.row().classes("flex-wrap gap-2 items-start"):
                        for _ml, _mv, _mc, _mi in (
                            [
                                (
                                    "Attack Success Rate",
                                    _fmt_pct(overall),
                                    "negative" if _is_risky(overall) else "positive",
                                    "lock_open" if _is_risky(overall) else "security",
                                ),
                            ]
                            + (
                                [
                                    (
                                        "Majority-vote ASR",
                                        _fmt_pct(mv_asr),
                                        "negative" if _is_risky(mv_asr) else "positive",
                                        "how_to_vote",
                                    ),
                                ]
                                if _hr_n_judges > 1
                                else []
                            )
                            + (
                                [
                                    (
                                        "Fleiss' Kappa",
                                        f"{float(kappa):.3f}",
                                        "grey-7",
                                        "balance",
                                    )
                                ]
                                if kappa is not None and _hr_n_judges > 1
                                else []
                            )
                            + (
                                [
                                    (
                                        "Bias Gap",
                                        _fmt_pct(per_judge.get("bias_gap")),
                                        "grey-7",
                                        "compare_arrows",
                                    )
                                ]
                                if isinstance(per_judge, dict)
                                and per_judge.get("bias_gap") is not None
                                and _hr_n_judges > 1
                                else []
                            )
                        ):
                            with ui.card().classes("flex-none min-w-[110px] px-3 py-2"):
                                with ui.row().classes("items-center gap-1 mb-1"):
                                    ui.icon(_mi, color=_mc, size="xs")
                                    ui.label(_ml).classes(
                                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                                    )
                                ui.label(_mv).classes("text-xl font-bold")

                        if (
                            _hr_n_judges > 1
                            and isinstance(per_judge, dict)
                            and any(k != "bias_gap" for k in per_judge)
                        ):
                            with ui.card().classes("flex-none px-3 py-2"):
                                ui.label("PER-JUDGE ASR").classes(
                                    "text-[10px] text-grey-6 font-semibold uppercase tracking-wide mb-1"
                                )
                                with ui.column().classes("gap-1"):
                                    for judge_name, asr_val in per_judge.items():
                                        if judge_name == "bias_gap":
                                            continue
                                        with ui.row().classes("items-center gap-2"):
                                            ui.label(judge_name).classes(
                                                "text-xs text-grey-7 font-mono"
                                            )
                                            ui.badge(
                                                _fmt_pct(asr_val),
                                                color="grey-6",
                                            ).classes("text-xs font-mono")
            else:
                # No evaluation_summary in run_config (e.g. BoN) — show
                # a basic results summary from the run-level counters.
                _hr_total = int(run.get("total_results") or 0)
                _hr_mitigated_fb = int(run.get("mitigations") or 0)
                with self.metrics_area:
                    if _hr_total > 0:
                        ui.label("RESULTS SUMMARY").classes(
                            "text-[10px] font-semibold tracking-widest "
                            "text-grey-5 uppercase mb-2"
                        )
                        with ui.row().classes("flex-wrap gap-2 items-start"):
                            for _ml, _mv, _mc, _mi in [
                                ("Total Tests", str(_hr_total), "grey-8", "quiz"),
                                (
                                    "Vulnerabilities",
                                    str(_hr_jailbreaks),
                                    "negative" if _hr_jailbreaks else "grey-7",
                                    "lock_open",
                                ),
                                (
                                    "Mitigated",
                                    str(_hr_mitigated_fb),
                                    "positive" if _hr_mitigated_fb else "grey-7",
                                    "security",
                                ),
                                (
                                    "Errors",
                                    str(_hr_errors),
                                    "warning" if _hr_errors else "grey-7",
                                    "warning_amber",
                                ),
                                ("Duration", _hr_run_latency_str, "grey-7", "timer"),
                            ]:
                                with ui.card().classes(
                                    "flex-none min-w-[110px] px-3 py-2"
                                ):
                                    with ui.row().classes("items-center gap-1 mb-1"):
                                        ui.icon(_mi, color=_mc, size="xs")
                                        ui.label(_ml).classes(
                                            "text-[10px] text-grey-6 font-semibold "
                                            "uppercase tracking-wide"
                                        )
                                    ui.label(_mv).classes("text-xl font-bold")
                    else:
                        ui.label("No results available yet.").classes(
                            "text-sm text-grey-6 py-4"
                        )

        if self.history_results_list_area is not None:
            self.history_results_list_area.clear()
        if self.history_results_empty_label is not None:
            self.history_results_empty_label.text = "Loading results…"
            self.history_results_empty_label.set_visibility(True)

        if self.history_run_dialog is not None:
            self.history_run_dialog.open()

        await asyncio.sleep(0)

        try:
            run_uuid = UUID(run_id_raw)

            def _fetch_results():
                items = []
                page = 1
                while True:
                    rp = self.backend.list_results(
                        run_id=run_uuid, page=page, page_size=100
                    )
                    items.extend(rp.items)
                    if len(items) >= rp.total or not rp.items:
                        break
                    page += 1
                return items

            all_items = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_results
            )

            sorted_items = sorted(
                all_items,
                key=lambda item: (
                    int(getattr(item, "goal_index", 0)),
                    getattr(item, "created_at", None),
                ),
            )

            new_rows = []
            for idx, r in enumerate(sorted_items, start=1):
                d = _serialize(r)
                d["_rel"] = _rel_time(d.get("created_at"))
                d["goal_number"] = idx
                d["_goal_category"] = self._extract_goal_classifier_label(d, "category")
                d["_goal_subcategory"] = self._extract_goal_classifier_label(
                    d, "subcategory"
                )
                d["evaluation_label"] = _eval_label(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["evaluation_notes"] = d.get("evaluation_notes") or "—"
                d["_goal_latency_s"] = self._extract_goal_latency_seconds(d)
                d["_goal_latency"] = _format_latency(d.get("_goal_latency_s"))
                bucket = _result_bucket(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["_bucket"] = bucket
                new_rows.append(d)

            # Pre-fetch traces for Baseline / BoN views
            baseline_traces_map_hr: dict[str, list[dict]] = {}
            if attack_type_str.lower() == "baseline" and new_rows:
                _hr_ids = [str(r.get("id") or "") for r in new_rows if r.get("id")]

                def _load_hr_traces() -> dict[str, list[dict]]:
                    _res: dict[str, list[dict]] = {}
                    for _rid in _hr_ids:
                        try:
                            _ts = self.backend.list_traces(result_id=UUID(_rid))
                            _res[_rid] = [_serialize(t) for t in _ts]
                        except Exception:
                            _res[_rid] = []
                    return _res

                baseline_traces_map_hr = await asyncio.get_event_loop().run_in_executor(
                    None, _load_hr_traces
                )

            bon_traces_map_hr: dict[str, list[dict]] = {}
            if attack_type_str.lower() == "bon" and new_rows:
                _bon_hr_ids = [str(r.get("id") or "") for r in new_rows if r.get("id")]

                def _load_bon_hr_traces() -> dict[str, list[dict]]:
                    _res: dict[str, list[dict]] = {}
                    for _rid in _bon_hr_ids:
                        try:
                            _ts = self.backend.list_traces(result_id=UUID(_rid))
                            _res[_rid] = [_serialize(t) for t in _ts]
                        except Exception:
                            _res[_rid] = []
                    return _res

                bon_traces_map_hr = await asyncio.get_event_loop().run_in_executor(
                    None, _load_bon_hr_traces
                )

            generic_traces_map_hr: dict[str, list[dict]] = {}
            if attack_type_str.lower() not in ("baseline", "bon") and new_rows:
                _gen_hr_ids = [str(r.get("id") or "") for r in new_rows if r.get("id")]

                def _load_gen_hr_traces() -> dict[str, list[dict]]:
                    _res: dict[str, list[dict]] = {}
                    for _rid in _gen_hr_ids:
                        try:
                            _ts = self.backend.list_traces(result_id=UUID(_rid))
                            _res[_rid] = [_serialize(t) for t in _ts]
                        except Exception:
                            _res[_rid] = []
                    return _res

                generic_traces_map_hr = await asyncio.get_event_loop().run_in_executor(
                    None, _load_gen_hr_traces
                )

            if self.history_results_list_area is not None:
                self.history_results_list_area.clear()

            if self.history_detail_area is not None:
                self.history_detail_area.clear()
                with self.history_detail_area:
                    ui.label("← Select a goal to view details").classes(
                        "text-grey-4 text-sm italic mt-16 w-full text-center"
                    )

            if self.history_results_empty_label is not None:
                if all_items:
                    self.history_results_empty_label.set_visibility(False)
                else:
                    self.history_results_empty_label.text = (
                        "No results found for this run."
                    )
                    self.history_results_empty_label.set_visibility(True)

            if all_items and self.history_results_list_area is not None:
                with self.history_results_list_area:
                    # ── Pre-parse detail data for all rows ─────────────
                    _h_atk = attack_type_str.lower()
                    _h_detail_data: dict[str, object] = {}
                    for _row in new_rows:
                        _rid = str(_row.get("id") or "")
                        if _h_atk == "baseline":
                            _t = baseline_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_baseline_traces(
                                _t, str(_row.get("goal") or "")
                            )
                        elif _h_atk == "bon":
                            _t = bon_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_bon_traces(_t)
                        elif _h_atk == "pap":
                            _t = generic_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_pap_traces(_t)
                        elif _h_atk == "pair":
                            _t = generic_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_pair_traces(_t)
                        elif _h_atk == "tap":
                            _t = generic_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_tap_traces(_t)
                        elif _h_atk == "advprefix":
                            _t = generic_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_advprefix_traces(_t)
                        elif _h_atk == "autodanturbo":
                            _t = generic_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = self._parse_autodan_traces(_t)
                        else:
                            _t = generic_traces_map_hr.get(_rid, [])
                            _h_detail_data[_rid] = (
                                self._extract_prompt_response_from_traces(_t)
                            )

                    # ── Group rows by category ─────────────────────────
                    _h_cat_groups: dict[str, list[dict]] = {}
                    for _row in new_rows:
                        _cat = _row.get("_goal_category") or "Uncategorised"
                        _h_cat_groups.setdefault(str(_cat), []).append(_row)

                    _h_left_num = 0
                    for _cat_label in sorted(_h_cat_groups.keys()):
                        _rows_in_cat = _h_cat_groups[_cat_label]
                        with ui.row().classes("items-center gap-2 mt-3 mb-1 px-1"):
                            ui.label(_cat_label).classes(
                                "text-xs font-semibold text-grey-6 uppercase "
                                "tracking-wide"
                            )

                        # ── Group by subcategory within category ──────
                        _h_subcat_groups: dict[str, list[dict]] = {}
                        for _row in _rows_in_cat:
                            _sub = str(_row.get("_goal_subcategory") or "")
                            if _sub == "N/A":
                                _sub = ""
                            _h_subcat_groups.setdefault(_sub, []).append(_row)

                        for _h_sub_label in sorted(_h_subcat_groups.keys()):
                            _h_rows_in_sub = sorted(
                                _h_subcat_groups[_h_sub_label],
                                key=lambda r: str(r.get("goal") or "").lower(),
                            )
                            if _h_sub_label:
                                with ui.row().classes(
                                    "items-center gap-2 mt-2 mb-0.5 px-3"
                                ):
                                    ui.label(_h_sub_label).classes(
                                        "text-[10px] font-semibold text-grey-5 "
                                        "uppercase tracking-wide"
                                    )

                            for _row in _h_rows_in_sub:
                                _h_left_num += 1
                                _row["goal_number"] = _h_left_num
                                _rid = str(_row.get("id") or "")
                                _data = _h_detail_data.get(_rid)

                                def _make_h_click(
                                    _r: dict = _row,
                                    _d: object = _data,
                                    _atk_str: str = attack_type_str,
                                ) -> None:
                                    if self.history_detail_area is None:
                                        return
                                    self.history_detail_area.clear()
                                    with self.history_detail_area:
                                        _ha = _atk_str.lower()
                                        if _ha == "baseline":
                                            self._render_baseline_goal_card(
                                                _r,
                                                _d,
                                                detail_mode=True,  # type: ignore[arg-type]
                                            )
                                        elif _ha == "bon":
                                            self._render_bon_goal_card(
                                                _r,
                                                _d,
                                                detail_mode=True,  # type: ignore[arg-type]
                                            )
                                        elif _ha == "pap":
                                            self._render_pap_goal_card(
                                                _r,
                                                _d,
                                                detail_mode=True,  # type: ignore[arg-type]
                                            )
                                        elif _ha == "pair":
                                            self._render_pair_goal_card(
                                                _r,
                                                _d,
                                                detail_mode=True,  # type: ignore[arg-type]
                                            )
                                        elif _ha == "tap":
                                            _nodes, _ds = _d  # type: ignore[misc]
                                            self._render_tap_goal_card(
                                                _r, _nodes, _ds, detail_mode=True
                                            )
                                        elif _ha == "advprefix":
                                            _pr, _gs = _d  # type: ignore[misc]
                                            self._render_advprefix_goal_card(
                                                _r, _pr, _gs, detail_mode=True
                                            )
                                        elif _ha == "autodanturbo":
                                            self._render_autodan_goal_card(
                                                _r,
                                                _d,
                                                detail_mode=True,  # type: ignore[arg-type]
                                            )
                                        else:
                                            _req, _resp = _d  # type: ignore[misc]
                                            self._render_generic_goal_card(
                                                _r, _req, _resp, detail_mode=True
                                            )

                                self._render_compact_card(_row, _make_h_click)
        except Exception as exc:
            if self.history_results_list_area is not None:
                self.history_results_list_area.clear()
            if self.history_results_empty_label is not None:
                self.history_results_empty_label.text = f"Failed to load results: {exc}"
                self.history_results_empty_label.set_visibility(True)
            ui.notify(f"Error loading results: {exc}", type="negative")

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
