# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DashboardPage — all NiceGUI UI layout and data-loading logic."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
import json
import math
import re
from typing import Any
from uuid import UUID

from nicegui import app as _fastapi_app
from nicegui import ui

from hackagent.attacks.evaluator.metrics import (
    calculate_fleiss_kappa,
    calculate_majority_vote_asr,
    calculate_per_judge_asr,
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
from .attack_cards import (
    AttackCardSharedMixin,
    BaselineCardMixin,
    BonCardMixin,
    PairCardMixin,
    AutodanCardMixin,
    AdvprefixCardMixin,
    PapCardMixin,
    TapCardMixin,
    GenericCardMixin,
    MmlCardMixin,
)

_VIEW_LABELS = {
    "dashboard": "Home",
    "agents": "Targets",
    "runs": "History",
}

_RESULTS_FETCH_LIMIT = 20
_DASHBOARD_RUN_SCAN_LIMIT = 10
_RUNS_VIEW_PAGE_SIZE = 15


class DashboardPage(
    AttackCardSharedMixin,
    BaselineCardMixin,
    BonCardMixin,
    PairCardMixin,
    AutodanCardMixin,
    AdvprefixCardMixin,
    PapCardMixin,
    TapCardMixin,
    GenericCardMixin,
    MmlCardMixin,
):
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
        self.runs_current_page: int = 1
        self.runs_total_pages: int = 1
        self._runs_all_rows: list[dict] = []
        self._runs_total_available: int = 0
        self._runs_filter_agent: str = ""
        self._runs_filter_attack: str = ""
        self._runs_filter_status: str = ""
        self._runs_filter_search: str = ""
        self._runs_load_more_btn: ui.button | None = None
        self._runs_agent_select: ui.select | None = None
        self._runs_attack_select: ui.select | None = None
        self._runs_status_select: ui.select | None = None
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
        self.history_charts_area: ui.column | None = None
        self.history_multi_judge_panel: ui.column | None = None
        self.history_results_list_area: ui.column | None = None
        self.history_results_empty_label: ui.label | None = None
        self.history_detail_area: ui.column | None = None
        self._history_dialog_attack_str: str = ""
        self._history_goal_filter: str = ""  # "" | "jailbreak" | "mitigated" | "error"
        self._history_goal_filter_category: str = ""  # "" or category label
        self._history_goal_filter_search: str = ""
        self._history_goal_rows: list[dict] = []
        self._history_goal_detail_data: dict[str, object] = {}
        self._history_goal_filter_area: ui.row | None = None

        # New side-by-side History layout
        self._history_runs_area: ui.column | None = None
        self._history_expanded_run_id: str | None = None
        self._history_expanded_goals_area: ui.column | None = None
        self._history_current_run: dict | None = None
        self._history_current_run_results: list[dict] = []
        self._history_visible_run_ids: list[str] = []

        # Bottom panel for run details (inline in runs panel)
        self._runs_bottom_panel: ui.column | None = None

        # Attack detail dialog
        self.attack_dialog: ui.dialog | None = None
        self.attack_dialog_title: ui.label | None = None
        self.attack_config_area: ui.column | None = None
        self.attack_runs_table: ui.table | None = None

        # Selection state for bulk operations
        self._selected_run_ids: list[str] = []
        self._selected_attack_ids: list[str] = []
        self._runs_delete_btn: ui.button | None = None
        self._runs_compare_btn: ui.button | None = None
        self._runs_export_btn: ui.button | None = None
        self._attacks_delete_btn: ui.button | None = None

        # Comparison dialog
        self._compare_dialog: ui.dialog | None = None
        self._compare_dialog_body: ui.column | None = None
        self._compare_bottom_panel: ui.card | None = None

    # ── Public entry point ────────────────────────────────────────────────────

    async def build(self) -> None:  # noqa: C901
        """Render the full page. Called from the ``@ui.page("/")`` handler."""
        self.dark = ui.dark_mode()
        if _fastapi_app.storage.browser.get("hackagent_dark"):
            self.dark.enable()

        # Inject a global copy-to-clipboard helper accessible from Vue template
        # slot expressions (where `navigator` is not in Vue 3's global whitelist).
        ui.add_head_html(
            """<script>
function hackAgentCopy(text) {
  if (window.navigator && window.navigator.clipboard) {
    window.navigator.clipboard.writeText(text).catch(function() {
      hackAgentCopyFallback(text);
    });
  } else {
    hackAgentCopyFallback(text);
  }
}
function hackAgentCopyFallback(text) {
  var el = document.createElement('textarea');
  el.value = text;
  el.style.cssText = 'position:fixed;top:-9999px;left:-9999px';
  document.body.appendChild(el);
  el.select();
  try { document.execCommand('copy'); } catch(e) {}
  document.body.removeChild(el);
}
</script>"""
        )

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
                ("dashboard", "Home", "dashboard"),
                ("agents", "Targets", "smart_toy"),
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
                self.page_title = ui.label("Home").classes(
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

            self.all_panels = {
                "dashboard": dashboard_panel,
                "agents": agents_panel,
                "runs": runs_panel,
            }
            for panel in self.all_panels.values():
                panel.set_visibility(False)
            dashboard_panel.set_visibility(True)

            self._build_dashboard_panel(dashboard_panel)
            self._build_agents_panel(agents_panel)
            self._build_runs_panel(runs_panel)

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
                            self.risk_chart = (
                                ui.echart(
                                    {
                                        "series": [
                                            {
                                                "type": "pie",
                                                "radius": ["58%", "80%"],
                                                "data": [
                                                    {
                                                        "value": 1,
                                                        "name": "No data",
                                                        "itemStyle": {
                                                            "color": "#94a3b8"
                                                        },
                                                    }
                                                ],
                                                "label": {"show": False},
                                            }
                                        ],
                                        "graphic": [],
                                        "tooltip": {"show": False},
                                    }
                                )
                                .classes("w-36 h-36 shrink-0")
                                .props("renderer=svg")
                            )
                            self.risk_legend = ui.column().classes("gap-2 flex-1")

                    with ui.column().classes("flex-1 min-w-72"):
                        ui.label("Result Distribution").classes("font-semibold text-sm")
                        ui.label(
                            "Evaluation outcomes for the latest tested target"
                        ).classes("text-xs text-grey-6 mb-4")
                        self.dist_chart = (
                            ui.echart(
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
                            )
                            .classes("w-full h-44")
                            .props("renderer=svg")
                        )

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
        with panel.classes("w-full h-[calc(100vh-160px)] min-h-0"):
            # ── Filter bar ────────────────────────────────────────────
            with ui.row().classes("items-center w-full gap-2 px-2 flex-wrap shrink-0"):
                ui.input(
                    placeholder="Search runs…",
                ).props(
                    "dense outlined clearable"
                ).classes("min-w-[100px] max-w-[180px] flex-1").on(
                    "update:model-value",
                    lambda e: self._on_runs_search_change(
                        e.args if isinstance(e.args, str) else (e.args or "")
                    ),
                )
                self._runs_agent_select = (
                    ui.select(
                        options={"": "All agents"},
                        value="",
                        on_change=lambda e: self._on_runs_filter_change(
                            "agent", e.value
                        ),
                    )
                    .props("dense outlined")
                    .classes("min-w-[140px]")
                )
                self._runs_attack_select = (
                    ui.select(
                        options={"": "All attacks"},
                        value="",
                        on_change=lambda e: self._on_runs_filter_change(
                            "attack", e.value
                        ),
                    )
                    .props("dense outlined")
                    .classes("min-w-[140px]")
                )
                ui.space()
                self._runs_compare_btn = (
                    ui.button(
                        "Compare",
                        icon="compare_arrows",
                        on_click=lambda: ui.timer(
                            0,
                            self._compare_selected_runs,
                            once=True,
                        ),
                    )
                    .props("flat dense no-caps color=primary")
                    .classes("opacity-30 pointer-events-none")
                )
                self._runs_export_btn = (
                    ui.button(
                        "Export",
                        icon="download",
                        on_click=lambda: ui.timer(
                            0,
                            self._export_selected_runs,
                            once=True,
                        ),
                    )
                    .props("flat dense no-caps color=secondary")
                    .classes("opacity-30 pointer-events-none")
                )
                self._runs_delete_btn = (
                    ui.button(
                        "Delete",
                        icon="delete",
                        on_click=lambda: ui.timer(
                            0,
                            self._delete_selected_runs,
                            once=True,
                        ),
                    )
                    .props("flat dense no-caps color=negative")
                    .classes("opacity-30 pointer-events-none")
                )
            # ── Scrollable run list ────────────────────────────────────
            with ui.scroll_area().classes("w-full flex-1 min-h-0"):
                self.runs_table = make_run_table(
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
                    pagination={"rowsPerPage": 15},
                    selection="multiple",
                    on_select=lambda e: self._on_runs_table_select(e),
                )
                # Move pagination bar to top via flex order
                self.runs_table.classes("runs-table-top-pagination")
                ui.add_css(
                    """
                    .runs-table-top-pagination .q-table__container {
                        display: flex;
                        flex-direction: column;
                    }
                    .runs-table-top-pagination .q-table__bottom {
                        order: -1;
                        border-bottom: 1px solid #e0e0e0;
                        border-top: none;
                    }
                """
                )
                self._runs_load_more_btn = (
                    ui.button(
                        "Load more",
                        icon="expand_more",
                        on_click=lambda: ui.timer(0, self._load_more_runs, once=True),
                    )
                    .props("flat no-caps color=primary")
                    .classes("self-center my-2 hidden")
                )

            # ── Bottom panel for run details (hidden by default) ───────
            # Built here but reparented to the active view on open so it can be
            # shown both from History and from the Home "Recent Runs" panel.
            self._runs_bottom_panel = (
                ui.card()
                .classes("w-full shrink-0 gap-0 hidden")
                .style("height: 70vh; min-height: 300px;")
            )

            # ── Bottom panel for compare (hidden by default) ──────────
            self._compare_bottom_panel = (
                ui.card()
                .classes("w-full shrink-0 gap-0 hidden")
                .style("height: 70%; min-height: 300px;")
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
        """Build run detail content inside the inline bottom panel."""
        if self._runs_bottom_panel is None:
            return
        with self._runs_bottom_panel:
            with ui.column().classes("w-full h-full gap-0"):
                with ui.row().classes(
                    "items-center justify-between w-full shrink-0 px-4 py-3 border-b"
                ):
                    self.history_run_dialog_title = ui.label("Run Results").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(
                        icon="close", on_click=self._close_runs_bottom_panel
                    ).props("flat round dense")
                # Two-panel body
                with ui.row().classes("w-full flex-1 gap-0 overflow-hidden min-h-0"):
                    # Left: config/metrics + charts + compact card list
                    with (
                        ui.scroll_area()
                        .classes("h-full border-r")
                        .style("flex:1 1 50%;min-width:0")
                    ):
                        with ui.column().classes("w-full gap-3 p-4"):
                            self.history_run_config_area = ui.column().classes(
                                "w-full gap-2"
                            )
                            ui.separator()
                            self.history_charts_area = ui.column().classes(
                                "w-full gap-3"
                            )
                            ui.separator()
                            # ── Multi-judge statistics panel ─────────
                            self.history_multi_judge_panel = ui.column().classes(
                                "w-full gap-0"
                            )
                            # ── Goal filter bar ──────────────────────
                            self._history_goal_filter_area = ui.row().classes(
                                "items-center gap-2 px-1 w-full"
                            )
                            with self._history_goal_filter_area:
                                self._build_goal_filter_bar()
                            self.history_results_empty_label = ui.label(
                                "Loading results..."
                            ).classes("text-sm text-grey-8 py-2")
                            self.history_results_list_area = ui.column().classes(
                                "w-full gap-1"
                            )
                    # Right: detail view
                    with (
                        ui.scroll_area()
                        .classes("h-full")
                        .style("flex:1 1 50%;min-width:0")
                    ):
                        self.history_detail_area = ui.column().classes(
                            "w-full gap-3 p-6"
                        )
                        with self.history_detail_area:
                            ui.label("← Select a goal to view details").classes(
                                "text-grey-4 text-sm italic mt-16 w-full text-center"
                            )
        # No dialog — panel is shown/hidden inline
        self.history_run_dialog = None

    def _build_goal_filter_bar(self) -> None:
        """Render the goal filter bar with search, status select, and category select."""
        rows = self._history_goal_rows
        # Status options
        status_options: dict[str, str] = {"": "All statuses"}
        n_jailbreak = sum(1 for r in rows if r.get("_bucket") == "jailbreak")
        n_mitigated = sum(1 for r in rows if r.get("_bucket") == "mitigated")
        n_error = sum(1 for r in rows if r.get("_bucket") == "error")
        if n_jailbreak:
            status_options["jailbreak"] = f"Jailbreaks ({n_jailbreak})"
        if n_mitigated:
            status_options["mitigated"] = f"Mitigated ({n_mitigated})"
        if n_error:
            status_options["error"] = f"Errors ({n_error})"

        # Category options
        cat_options: dict[str, str] = {"": "All categories"}
        cats: set[str] = set()
        for r in rows:
            cat = r.get("_goal_category") or ""
            if cat and cat != "N/A":
                cats.add(str(cat))
        for cat in sorted(cats):
            cat_options[cat] = cat

        ui.input(
            placeholder="Search goals...",
            value=self._history_goal_filter_search,
            on_change=lambda e: self._on_goal_search_change(e.value),
        ).props("dense outlined clearable").classes("flex-1 min-w-[120px]").style(
            "max-width:220px"
        )
        ui.select(
            options=status_options,
            value=self._history_goal_filter,
            on_change=lambda e: self._on_goal_status_change(e.value),
        ).props("dense outlined").classes("min-w-[130px]")
        ui.select(
            options=cat_options,
            value=self._history_goal_filter_category,
            on_change=lambda e: self._on_goal_category_change(e.value),
        ).props("dense outlined").classes("min-w-[140px]")

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
        if ha == "baseline":
            self._render_baseline_goal_card(row, data, detail_mode=True)  # type: ignore[arg-type]
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
        for src in (metadata, metrics):
            if isinstance(src, dict):
                for k, v in src.items():
                    if v not in (None, "", {}, []):
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

        # Guardrails section
        run_cfg = (
            run.get("run_config") if isinstance(run.get("run_config"), dict) else {}
        )
        before_gr = display_config.get("before_guardrail") or run_cfg.get(
            "before_guardrail"
        )
        after_gr = display_config.get("after_guardrail") or run_cfg.get(
            "after_guardrail"
        )
        if before_gr or after_gr:
            with ui.column().classes("w-full gap-1"):
                ui.label("GUARDRAILS").classes(
                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                )
                with ui.row().classes("flex-wrap gap-3"):
                    if before_gr:
                        gr_label = (
                            before_gr.get("identifier", "—")
                            if isinstance(before_gr, dict)
                            else str(before_gr)
                        )
                        with ui.card().tight().classes("min-w-24"):
                            with ui.column().classes("px-3 py-2 gap-0"):
                                ui.label("BEFORE MODEL").classes(
                                    "text-[10px] font-semibold text-grey-5"
                                )
                                ui.label(gr_label).classes("text-sm font-medium")
                    if after_gr:
                        gr_label = (
                            after_gr.get("identifier", "—")
                            if isinstance(after_gr, dict)
                            else str(after_gr)
                        )
                        with ui.card().tight().classes("min-w-24"):
                            with ui.column().classes("px-3 py-2 gap-0"):
                                ui.label("AFTER MODEL").classes(
                                    "text-[10px] font-semibold text-grey-5"
                                )
                                ui.label(gr_label).classes("text-sm font-medium")

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
        self.current_view["value"] = view
        for v, panel in self.all_panels.items():
            panel.set_visibility(v == view)
        self.page_title.text = _VIEW_LABELS.get(view, "Home")
        self._highlight_nav(view)
        if schedule_refresh:
            asyncio.create_task(self.refresh_view())

    def _on_runs_table_select(self, e) -> None:
        """Handle selection event from the runs ui.table."""
        self._on_runs_select()

    def _on_runs_select(self) -> None:
        if self.runs_table is not None:
            self._selected_run_ids = [
                row["id"] for row in (self.runs_table.selected or [])
            ]
        if self._runs_delete_btn is not None:
            if self._selected_run_ids:
                self._runs_delete_btn.classes(
                    remove="opacity-30 pointer-events-none",
                    add="opacity-100",
                )
            else:
                self._runs_delete_btn.classes(
                    remove="opacity-100",
                    add="opacity-30 pointer-events-none",
                )
        if self._runs_export_btn is not None:
            if self._selected_run_ids:
                self._runs_export_btn.classes(
                    remove="opacity-30 pointer-events-none",
                    add="opacity-100",
                )
            else:
                self._runs_export_btn.classes(
                    remove="opacity-100",
                    add="opacity-30 pointer-events-none",
                )
        if self._runs_compare_btn is not None:
            if len(self._selected_run_ids) >= 2:
                self._runs_compare_btn.classes(
                    remove="opacity-30 pointer-events-none",
                    add="opacity-100",
                )
            else:
                self._runs_compare_btn.classes(
                    remove="opacity-100",
                    add="opacity-30 pointer-events-none",
                )

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
            self._runs_delete_btn.classes(
                remove="opacity-100",
                add="opacity-30 pointer-events-none",
            )
        await self._load_runs()
        await self._load_history_reports()

    async def _export_selected_runs(self) -> None:
        """Export selected runs as summary JSON download."""
        ids = list(self._selected_run_ids)
        if not ids:
            ui.notify("No runs selected", type="warning")
            return
        try:
            export_data = await self._build_export_data(ids)
            short_ids = "_".join(rid[:8] for rid in ids)
            filename = f"hackagent_export_{short_ids}.json"
            content = json.dumps(export_data, indent=2, default=str)
            ui.download(
                content.encode("utf-8"),
                filename=filename,
                media_type="application/json",
            )
            ui.notify(f"Exported {len(ids)} run(s)", type="positive")
        except Exception as exc:
            ui.notify(f"Export failed: {exc}", type="negative")

    async def _build_export_data(self, run_ids: list[str]) -> dict:
        """Build export JSON payload for given run IDs."""
        from datetime import datetime, timezone

        export = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "runs": [],
        }

        for rid in run_ids:
            run_row = next(
                (r for r in self._runs_all_rows if str(r.get("id")) == rid), None
            )
            if not run_row:
                continue

            run_entry: dict = {
                "id": rid,
                "run_number": run_row.get("run_progress"),
                "agent_name": run_row.get("agent_name"),
                "attack_type": run_row.get("attack_type"),
                "status": run_row.get("status"),
                "created_at": run_row.get("created_at"),
                "total_results": run_row.get("total_results"),
                "successful_jailbreaks": run_row.get("successful_jailbreaks"),
                "mitigations": run_row.get("mitigations"),
                "errors": run_row.get("failed_attacks"),
                "overall_asr": run_row.get("overall_asr"),
                "latency_seconds": run_row.get("_latency_s"),
                "avg_goal_latency_seconds": run_row.get("_goal_latency_avg_s"),
                "run_config": run_row.get("run_config"),
            }

            # Per-category breakdown
            run_uuid = UUID(rid)
            cat_stats: dict[str, dict[str, int]] = defaultdict(
                lambda: {
                    "total": 0,
                    "vulnerable": 0,
                    "mitigated": 0,
                    "errors": 0,
                }
            )
            page = 1
            while True:
                rp = self.backend.list_results(
                    run_id=run_uuid, page=page, page_size=100
                )
                if not rp.items:
                    break
                for result in rp.items:
                    rd = _serialize(result)
                    cat = self._extract_goal_classifier_label(rd, "category")
                    if not cat or cat == "N/A":
                        cat = "Uncategorised"
                    es = str(rd.get("evaluation_status") or "")
                    en = rd.get("evaluation_notes")
                    bucket = _result_bucket(status=es, notes=en)
                    entry = cat_stats[cat]
                    entry["total"] += 1
                    if bucket == "jailbreak":
                        entry["vulnerable"] += 1
                    elif bucket == "mitigated":
                        entry["mitigated"] += 1
                    elif bucket == "error":
                        entry["errors"] += 1
                if int(rp.total or 0) <= page * 100:
                    break
                page += 1
            run_entry["categories"] = dict(cat_stats)

            export["runs"].append(run_entry)

        return export

    async def _compare_selected_runs(self) -> None:
        """Open a comparison dialog for 2-4 selected runs."""
        ids = list(self._selected_run_ids)
        if len(ids) < 2:
            ui.notify("Select at least 2 runs to compare", type="warning")
            return
        if len(ids) > 4:
            ui.notify("Select at most 4 runs to compare", type="warning")
            return

        # Gather run rows
        runs: list[dict] = []
        for rid in ids:
            row = next(
                (r for r in self._runs_all_rows if str(r.get("id")) == rid), None
            )
            if row:
                runs.append(row)
        if len(runs) < 2:
            return

        # Fetch per-category breakdown for each run
        per_run_cats: list[dict[str, dict[str, int]]] = []
        all_categories: set[str] = set()
        for run in runs:
            run_id = UUID(str(run["id"]))
            cat_stats: dict[str, dict[str, int]] = defaultdict(
                lambda: {"total": 0, "vulnerable": 0, "mitigated": 0, "errors": 0}
            )
            page = 1
            while True:
                rp = self.backend.list_results(run_id=run_id, page=page, page_size=100)
                if not rp.items:
                    break
                for result in rp.items:
                    rd = _serialize(result)
                    cat = self._extract_goal_classifier_label(rd, "category")
                    if not cat or cat == "N/A":
                        cat = "Uncategorised"
                    es = str(rd.get("evaluation_status") or "")
                    en = rd.get("evaluation_notes")
                    bucket = _result_bucket(status=es, notes=en)
                    entry = cat_stats[cat]
                    entry["total"] += 1
                    if bucket == "jailbreak":
                        entry["vulnerable"] += 1
                    elif bucket == "mitigated":
                        entry["mitigated"] += 1
                    elif bucket == "error":
                        entry["errors"] += 1
                if int(rp.total or 0) <= page * 100:
                    break
                page += 1
            per_run_cats.append(dict(cat_stats))
            all_categories.update(cat_stats.keys())

        sorted_cats = sorted(all_categories)

        # Populate the inline compare bottom panel
        if self._compare_bottom_panel is None:
            return
        # Hide run detail panel if open
        self._close_runs_bottom_panel()
        self._compare_bottom_panel.clear()
        with self._compare_bottom_panel.style(add="overflow-y: auto;"):
            # ── Categorical palette for run identity ──────────
            # Avoids red/green/orange reserved for status semantics
            colors = ["#4a2377", "#8cc5e3", "#f55f74", "#0d7d87"]

            # ── Build short + full labels ─────────────────────
            short_labels = [f"#{r.get('run_progress', '?')}" for r in runs]
            _runs_suffix = "_".join(short_labels).replace("#", "run")

            # ── Header ────────────────────────────────────────
            with (
                ui.row()
                .classes(
                    "items-center justify-between w-full shrink-0 px-4 py-3 border-b"
                )
                .style("position: sticky; top: 0; z-index: 1; background: inherit;")
            ):
                ui.label(f"Comparing {len(runs)} Runs").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=self._close_compare_panel).props(
                    "flat round dense"
                )

                # ── Build config chips per run & detect differences ──
                _attack_display_map: dict[str, str] = {
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

                def _compare_chips_for_run(run: dict) -> list[tuple[str, str, str]]:
                    """Return (icon, label, value) tuples for a run."""
                    chips: list[tuple[str, str, str]] = []
                    rc = (
                        run.get("run_config")
                        if isinstance(run.get("run_config"), dict)
                        else {}
                    )
                    # Get attack config from run_config or attack lookup
                    cfg: dict = {}
                    _atk_id = str(run.get("attack_id") or "")
                    if _atk_id:
                        with contextlib.suppress(Exception):
                            _acm = self._attack_config_map_for_ids({_atk_id})
                            _ac = _acm.get(_atk_id)
                            if isinstance(_ac, dict) and _ac:
                                cfg = _ac
                    if not cfg and isinstance(rc, dict):
                        cfg = {k: v for k, v in rc.items() if k != "evaluation_summary"}

                    atk_str = str(run.get("attack_type") or "—")
                    atk_lower = atk_str.lower()

                    # Attack type
                    chips.append(
                        (
                            "flash_on",
                            "Attack",
                            _attack_display_map.get(atk_lower, atk_str.capitalize()),
                        )
                    )

                    # Attack-specific params
                    if atk_lower == "flipattack":
                        _fa = cfg.get("flipattack_params") or {}
                        if isinstance(_fa, dict):
                            chips.append(
                                ("flip", "Mode", str(_fa.get("flip_mode", "FCS")))
                            )
                    elif atk_lower == "h4rm3l":
                        _h4 = cfg.get("h4rm3l_params") or {}
                        _prog = _h4.get("program", "") if isinstance(_h4, dict) else ""
                        if _prog:
                            chips.append(
                                (
                                    "layers",
                                    "Decorators",
                                    self._format_h4rm3l_program(_prog),
                                )
                            )
                    elif atk_lower == "cipherchat":
                        _cc = cfg.get("cipherchat_params") or {}
                        if isinstance(_cc, dict):
                            chips.append(
                                ("lock", "Cipher", str(_cc.get("encode_method", "—")))
                            )
                    elif atk_lower == "bon":
                        _bn = cfg.get("bon_params") or {}
                        if isinstance(_bn, dict):
                            chips.append(
                                ("auto_awesome", "Steps", str(_bn.get("n_steps", 4)))
                            )
                    elif atk_lower == "tap":
                        _tp = cfg.get("tap_params") or {}
                        if isinstance(_tp, dict):
                            chips.append(
                                ("account_tree", "Depth", str(_tp.get("depth", 3)))
                            )
                            chips.append(("width", "Width", str(_tp.get("width", 4))))

                    # Dataset
                    _ds_raw = cfg.get("dataset") or rc.get("dataset")
                    if isinstance(_ds_raw, dict):
                        _ds_p = _ds_raw.get("preset") or ""
                        _ds_label = (
                            _ds_p.replace("_", " ").title() if _ds_p else "Custom"
                        )
                        chips.append(("dataset", "Dataset", _ds_label))
                        _ds_lim = _ds_raw.get("limit")
                        if _ds_lim is not None:
                            chips.append(("filter_list", "Limit", str(_ds_lim)))
                    elif _ds_raw:
                        chips.append(("dataset", "Dataset", str(_ds_raw)))

                    # Target
                    _agent = str(run.get("agent_name") or "—")
                    chips.append(("smart_toy", "Target", _agent))

                    # Judge / Scorer
                    if atk_lower in ("pair", "autodanturbo"):
                        _sc = cfg.get("scorer") or {}
                        if isinstance(_sc, dict):
                            _sc_id = _sc.get("identifier") or _sc.get("model_id") or ""
                            if _sc_id:
                                chips.append(("analytics", "Scorer", str(_sc_id)))
                    else:
                        _judges = cfg.get("judges")
                        if isinstance(_judges, list) and _judges:
                            _j0 = _judges[0] if isinstance(_judges[0], dict) else {}
                            _jm = _j0.get("identifier") or _j0.get("model_id") or ""
                            _jt = _j0.get("type") or ""
                            _jlabel = (
                                f"{_jt}" + (f" · {_jm}" if _jm else "")
                                if _jt
                                else (_jm or "pattern")
                            )
                            chips.append(("gavel", "Judge", _jlabel))

                    # Attacker
                    _att = cfg.get("attacker") or {}
                    if isinstance(_att, dict):
                        _att_id = _att.get("identifier") or _att.get("model_id") or ""
                        if _att_id:
                            chips.append(("psychology", "Attacker", str(_att_id)))

                    # Generator (AdvPrefix)
                    if atk_lower == "advprefix":
                        _gen = cfg.get("generator") or {}
                        if isinstance(_gen, dict):
                            _gen_id = (
                                _gen.get("identifier") or _gen.get("model_id") or ""
                            )
                            if _gen_id:
                                chips.append(("build", "Generator", str(_gen_id)))

                    # Guardrails
                    _bg = rc.get("before_guardrail")
                    _ag = rc.get("after_guardrail")
                    if isinstance(_bg, dict):
                        chips.append(
                            ("shield", "Before Guardrail", _bg.get("identifier", "—"))
                        )
                    if isinstance(_ag, dict):
                        chips.append(
                            ("shield", "After Guardrail", _ag.get("identifier", "—"))
                        )

                    return chips

                # Collect chips per run and determine which labels differ
                _all_run_chips: list[list[tuple[str, str, str]]] = [
                    _compare_chips_for_run(r) for r in runs
                ]
                # Build label→set(values) to detect differences
                _label_values: dict[str, set[str]] = defaultdict(set)
                _all_labels: set[str] = set()
                for _chips_list in _all_run_chips:
                    for _, lbl, val in _chips_list:
                        _label_values[lbl].add(val)
                        _all_labels.add(lbl)
                # Labels absent from a run count as a distinct value
                for _chips_list in _all_run_chips:
                    _run_labels = {lbl for _, lbl, _ in _chips_list}
                    for lbl in _all_labels:
                        if lbl not in _run_labels:
                            _label_values[lbl].add("")
                _diff_labels: set[str] = {
                    lbl for lbl, vals in _label_values.items() if len(vals) > 1
                }

                # ── Summary Table ─────────────────────────────────
                with ui.card().classes("w-full"):
                    ui.label("Summary").classes("font-semibold text-sm mb-1")
                    # Shared config (common across all runs)
                    _shared_labels = _all_labels - _diff_labels
                    if _shared_labels and _all_run_chips:
                        _shared_chips = [
                            (ic, lbl, val)
                            for ic, lbl, val in _all_run_chips[0]
                            if lbl in _shared_labels
                        ]
                        if _shared_chips:
                            with ui.row().classes("items-center gap-1 mb-2 flex-wrap"):
                                ui.icon("settings", size="14px").classes("text-grey-5")
                                ui.label("Shared:").classes(
                                    "text-xs font-semibold text-grey-5"
                                )
                                for _cic, _clbl, _cval in _shared_chips:
                                    with ui.row().classes(
                                        "items-center gap-1 rounded px-1.5 py-0.5 bg-grey-1"
                                    ):
                                        ui.icon(_cic, size="10px").classes(
                                            "text-grey-5"
                                        )
                                        ui.label(f"{_clbl}: {_cval}").classes(
                                            "text-[10px] font-medium text-grey-7"
                                        )
                    columns = [
                        {
                            "name": "run",
                            "label": "Run",
                            "field": "run",
                            "align": "left",
                        },
                        {
                            "name": "attack",
                            "label": "Attack",
                            "field": "attack",
                            "align": "left",
                        },
                        {
                            "name": "asr",
                            "label": "ASR",
                            "field": "asr",
                            "align": "center",
                        },
                        {
                            "name": "latency",
                            "label": "Avg Latency",
                            "field": "latency",
                            "align": "center",
                        },
                        {
                            "name": "goals",
                            "label": "Goals",
                            "field": "goals",
                            "align": "center",
                        },
                        {
                            "name": "cats_passed",
                            "label": "Categories Passed",
                            "field": "cats_passed",
                            "align": "center",
                        },
                        {
                            "name": "worst_cat",
                            "label": "Worst Category",
                            "field": "worst_cat",
                            "align": "left",
                        },
                        {
                            "name": "differences",
                            "label": "Differences",
                            "field": "differences",
                            "align": "left",
                        },
                    ]
                    table_rows = []
                    for i, run in enumerate(runs):
                        cat_data = per_run_cats[i]
                        total_cats = len(cat_data)
                        passed = sum(
                            1
                            for entry in cat_data.values()
                            if entry["total"] > 0 and entry["vulnerable"] == 0
                        )
                        # Find worst category (highest ASR)
                        worst_cat = "—"
                        worst_asr = -1.0
                        for cat, entry in cat_data.items():
                            if entry["total"] > 0:
                                cat_asr = entry["vulnerable"] / entry["total"]
                                if cat_asr > worst_asr:
                                    worst_asr = cat_asr
                                    worst_cat = cat
                        if worst_asr <= 0:
                            worst_cat = "—"

                        # Build differences string from differing config
                        _run_chips = _all_run_chips[i]
                        _diff_chips = [
                            (ic, lbl, val)
                            for ic, lbl, val in _run_chips
                            if lbl in _diff_labels
                        ]
                        diff_str = (
                            ", ".join(f"{lbl}: {val}" for _, lbl, val in _diff_chips)
                            if _diff_chips
                            else "—"
                        )

                        table_rows.append(
                            {
                                "run": short_labels[i],
                                "attack": str(run.get("attack_type") or "—"),
                                "asr": str(run.get("overall_asr", "—")),
                                "latency": run.get("_latency") or "—",
                                "goals": str(run.get("total_results") or 0),
                                "cats_passed": f"{passed}/{total_cats}",
                                "worst_cat": worst_cat if worst_cat != "—" else "None",
                                "differences": diff_str,
                            }
                        )
                    ui.table(
                        columns=columns,
                        rows=table_rows,
                        row_key="run",
                    ).classes(
                        "w-full"
                    ).props("dense flat bordered")

                # ── Risk Distribution + Vulnerabilities per Category (side by side) ──
                with ui.row().classes("w-full mt-3 gap-3 items-stretch"):
                    # Left: Risk Distribution (stacked bar)
                    with ui.card().classes("flex-1 min-w-[280px]"):
                        _rd_chart_ref: list = []

                        async def _dl_risk_dist():
                            if _rd_chart_ref:
                                await self._download_echart_svg(
                                    _rd_chart_ref[0],
                                    f"risk_distribution_{_runs_suffix}",
                                )

                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label("Risk Distribution").classes(
                                "font-semibold text-sm"
                            )
                            ui.button(icon="download", on_click=_dl_risk_dist).props(
                                "flat dense size=xs color=grey-6"
                            )
                        metrics = ["Jailbreak", "Mitigated", "Errors", "Pending"]
                        metric_colors = ["#ef4444", "#22c55e", "#f97316", "#d1d5db"]
                        bar_series = []
                        for mi, (metric, mcolor) in enumerate(
                            zip(metrics, metric_colors)
                        ):
                            values = []
                            for run in runs:
                                jb = int(run.get("successful_jailbreaks") or 0)
                                mit = int(run.get("mitigations") or 0)
                                err = int(run.get("errors") or 0)
                                total = int(run.get("total_results") or 0)
                                pending = max(0, total - jb - mit - err)
                                values.append([jb, mit, err, pending][mi])
                            bar_series.append(
                                {
                                    "name": metric,
                                    "type": "bar",
                                    "stack": "total",
                                    "data": values,
                                    "itemStyle": {"color": mcolor},
                                    "barMaxWidth": 40,
                                }
                            )
                        _rd_chart_ref.append(
                            ui.echart(
                                {
                                    "tooltip": {
                                        "trigger": "axis",
                                        "axisPointer": {"type": "shadow"},
                                    },
                                    "legend": {
                                        "bottom": 0,
                                        "textStyle": {"fontSize": 11},
                                    },
                                    "grid": {
                                        "left": "3%",
                                        "right": "4%",
                                        "top": "8%",
                                        "bottom": "16%",
                                        "containLabel": True,
                                    },
                                    "xAxis": {
                                        "type": "category",
                                        "data": short_labels,
                                    },
                                    "yAxis": {
                                        "type": "value",
                                        "name": "Count",
                                    },
                                    "series": bar_series,
                                }
                            )
                            .classes("w-full h-56")
                            .props("renderer=svg")
                        )

                    # Right: Vulnerabilities per Category (grouped horizontal bar)
                    if sorted_cats:
                        with ui.card().classes("flex-1 min-w-[320px]"):
                            _vc_chart_ref: list = []

                            async def _dl_vuln_cat():
                                if _vc_chart_ref:
                                    await self._download_echart_svg(
                                        _vc_chart_ref[0],
                                        f"vulnerabilities_per_category_{_runs_suffix}",
                                    )

                            with ui.row().classes(
                                "items-center justify-between w-full mb-1"
                            ):
                                ui.label("Vulnerabilities per Category").classes(
                                    "font-semibold text-sm"
                                )
                                ui.button(icon="download", on_click=_dl_vuln_cat).props(
                                    "flat dense size=xs color=grey-6"
                                )

                            bar_cats = sorted(sorted_cats, reverse=True)

                            vuln_data: list[list[int]] = []
                            for _i, cat_data in enumerate(per_run_cats):
                                vuln_vals: list[int] = []
                                for cat in bar_cats:
                                    entry = cat_data.get(cat)
                                    vuln_vals.append(
                                        entry["vulnerable"] if entry else 0
                                    )
                                vuln_data.append(vuln_vals)

                            def _build_cat_series() -> list[dict]:
                                series = []
                                for idx, run in enumerate(runs):
                                    series.append(
                                        {
                                            "name": short_labels[idx],
                                            "type": "bar",
                                            "data": vuln_data[idx],
                                            "itemStyle": {
                                                "color": colors[idx % len(colors)]
                                            },
                                            "barMaxWidth": 18,
                                        }
                                    )
                                return series

                            chart_height = max(260, len(bar_cats) * 38)

                            _vc_chart_ref.append(
                                ui.echart(
                                    {
                                        "tooltip": {
                                            "trigger": "axis",
                                            "axisPointer": {"type": "shadow"},
                                        },
                                        "legend": {
                                            "bottom": 0,
                                            "textStyle": {"fontSize": 11},
                                        },
                                        "grid": {
                                            "left": "3%",
                                            "right": "4%",
                                            "top": "3%",
                                            "bottom": "10%",
                                            "containLabel": True,
                                        },
                                        "xAxis": {
                                            "type": "value",
                                            "minInterval": 1,
                                        },
                                        "yAxis": {
                                            "type": "category",
                                            "data": bar_cats,
                                            "axisLabel": {
                                                "width": 120,
                                                "overflow": "truncate",
                                                "fontSize": 11,
                                            },
                                        },
                                        "series": _build_cat_series(),
                                    }
                                )
                                .classes("w-full")
                                .style(f"height: {chart_height}px")
                                .props("renderer=svg")
                            )

                # ── Robustness radar + ASR vs Latency (side by side) ─────
                with ui.row().classes("w-full mt-3 gap-3 items-stretch"):
                    # Left: Robustness radar
                    if len(sorted_cats) >= 3:
                        with ui.card().classes("flex-1 min-w-[300px]"):
                            _rr_chart_ref: list = []

                            async def _dl_radar():
                                if _rr_chart_ref:
                                    await self._download_echart_svg(
                                        _rr_chart_ref[0],
                                        f"robustness_radar_{_runs_suffix}",
                                    )

                            with ui.row().classes(
                                "items-center justify-between w-full"
                            ):
                                ui.label("Robustness by Category").classes(
                                    "font-semibold text-sm"
                                )
                                ui.button(icon="download", on_click=_dl_radar).props(
                                    "flat dense size=xs color=grey-6"
                                )
                            ui.label(
                                "Higher = more robust (100% means no successful jailbreaks)"
                            ).classes("text-xs text-grey-6 mb-2")
                            radar_cats = sorted_cats[:9]

                            indicators = [{"name": c, "max": 100} for c in radar_cats]
                            series_data = []
                            legend_names = []
                            for i, (run, cat_data) in enumerate(
                                zip(runs, per_run_cats)
                            ):
                                legend_names.append(short_labels[i])
                                values = []
                                for cat in radar_cats:
                                    entry = cat_data.get(cat)
                                    if entry and entry["total"] > 0:
                                        robustness = round(
                                            100
                                            * (entry["total"] - entry["vulnerable"])
                                            / entry["total"],
                                            1,
                                        )
                                    else:
                                        robustness = 100.0
                                    values.append(robustness)
                                series_data.append(
                                    {
                                        "value": values,
                                        "name": short_labels[i],
                                        "lineStyle": {"width": 2},
                                        "areaStyle": {"opacity": 0.08},
                                        "itemStyle": {"color": colors[i % len(colors)]},
                                    }
                                )

                            _rr_chart_ref.append(
                                ui.echart(
                                    {
                                        "tooltip": {
                                            "trigger": "item",
                                            "confine": True,
                                        },
                                        "legend": {
                                            "data": legend_names,
                                            "bottom": 0,
                                            "textStyle": {"fontSize": 11},
                                        },
                                        "radar": {
                                            "shape": "polygon",
                                            "indicator": indicators,
                                            "splitNumber": 5,
                                            "center": ["50%", "48%"],
                                            "radius": "62%",
                                            "axisName": {
                                                "fontSize": 11,
                                                "color": "#374151",
                                            },
                                            "splitLine": {
                                                "lineStyle": {"color": "#e5e7eb"}
                                            },
                                            "splitArea": {
                                                "areaStyle": {"color": ["#ffffff"]}
                                            },
                                        },
                                        "series": [
                                            {
                                                "type": "radar",
                                                "symbol": "circle",
                                                "symbolSize": 7,
                                                "data": series_data,
                                            }
                                        ],
                                    }
                                )
                                .classes("w-full h-80")
                                .props("renderer=svg")
                            )

                    # Right: ASR vs Latency scatter
                    with ui.card().classes("flex-1 min-w-[300px]"):
                        _sl_chart_ref: list = []

                        async def _dl_scatter():
                            if _sl_chart_ref:
                                await self._download_echart_svg(
                                    _sl_chart_ref[0], f"asr_vs_latency_{_runs_suffix}"
                                )

                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label("ASR vs Latency").classes("font-semibold text-sm")
                            ui.button(icon="download", on_click=_dl_scatter).props(
                                "flat dense size=xs color=grey-6"
                            )
                        ui.label(
                            "Each point is a run — lower-left is best (low ASR, fast)"
                        ).classes("text-xs text-grey-6 mb-2")
                        scatter_series = []
                        for i, run in enumerate(runs):
                            asr_raw = run.get("overall_asr", "—")
                            latency_s = run.get("_goal_latency_avg_s")
                            asr_num = None
                            if isinstance(asr_raw, (int, float)):
                                asr_num = float(asr_raw)
                            elif isinstance(asr_raw, str):
                                asr_clean = asr_raw.replace("%", "").strip()
                                try:
                                    asr_num = float(asr_clean)
                                except (ValueError, TypeError):
                                    pass
                            lat_num = None
                            if isinstance(latency_s, (int, float)):
                                lat_num = round(float(latency_s), 1)
                            if asr_num is not None and lat_num is not None:
                                scatter_series.append(
                                    {
                                        "name": short_labels[i],
                                        "type": "scatter",
                                        "symbolSize": 16,
                                        "itemStyle": {"color": colors[i % len(colors)]},
                                        "data": [
                                            {
                                                "value": [lat_num, asr_num],
                                                "name": f"{short_labels[i]}\nLatency: {lat_num}s | ASR: {asr_num}%",
                                            }
                                        ],
                                        "tooltip": {
                                            "formatter": f"{short_labels[i]}<br/>Latency: {lat_num}s<br/>ASR: {asr_num}%",
                                        },
                                    }
                                )
                        if scatter_series:
                            _sl_chart_ref.append(
                                ui.echart(
                                    {
                                        "tooltip": {
                                            "trigger": "item",
                                            "extraCssText": "padding:6px 10px;",
                                        },
                                        "legend": {
                                            "top": 4,
                                            "right": 8,
                                            "textStyle": {"fontSize": 11},
                                        },
                                        "grid": {
                                            "left": "14%",
                                            "right": "8%",
                                            "top": "14%",
                                            "bottom": "14%",
                                        },
                                        "xAxis": {
                                            "type": "value",
                                            "name": "Avg Latency (s)",
                                            "nameLocation": "middle",
                                            "nameGap": 28,
                                            "min": 0,
                                        },
                                        "yAxis": {
                                            "type": "value",
                                            "name": "ASR (%)",
                                            "nameLocation": "middle",
                                            "nameGap": 40,
                                            "min": 0,
                                            "max": 100,
                                        },
                                        "series": scatter_series,
                                    }
                                )
                                .classes("w-full h-80")
                                .props("renderer=svg")
                            )
                        else:
                            ui.label(
                                "Insufficient data for ASR vs Latency plot"
                            ).classes("text-xs text-grey-5 italic")

        self._compare_bottom_panel.classes(remove="hidden")

    async def _download_echart_svg(self, chart, filename: str) -> None:
        """Download an EChart as SVG via run_chart_method."""
        import base64 as _b64
        from urllib.parse import unquote as _unquote

        try:
            data_url = await chart.run_chart_method("getDataURL", {"type": "svg"})
            if data_url and "," in data_url:
                header, payload = data_url.split(",", 1)
                if "base64" in header:
                    svg_bytes = _b64.b64decode(payload)
                else:
                    svg_bytes = _unquote(payload).encode("utf-8")
                ui.download(
                    svg_bytes,
                    filename=f"{filename}.svg",
                    media_type="image/svg+xml",
                )
            else:
                ui.notify("Failed to export chart", type="warning")
        except Exception as exc:
            ui.notify(f"Export failed: {exc}", type="negative")

    def _close_compare_panel(self) -> None:
        """Hide the compare bottom panel."""
        if self._compare_bottom_panel is not None:
            self._compare_bottom_panel.classes(add="hidden")

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

    @staticmethod
    def _judge_type_from_key(judge_key: str) -> str:
        """Infer judge type display string from eval key abbreviation."""
        _abbr_to_type = {
            "hb": "Harmbench",
            "hbv": "Harmbench Variant",
            "jb": "Jailbreakbench",
            "nj": "Nuanced",
            "on_topic": "On Topic",
        }
        stripped = judge_key[5:] if judge_key.startswith("eval_") else judge_key
        # Remove trailing _N suffix (e.g. hbv_1 -> hbv)
        base = (
            stripped.rsplit("_", 1)[0]
            if "_" in stripped and stripped.rsplit("_", 1)[1].isdigit()
            else stripped
        )
        return _abbr_to_type.get(base, "")

    @classmethod
    def _build_judge_metadata(
        cls, judges_cfg: object
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """Build eval-key metadata mapping from attack judge configuration."""
        if not isinstance(judges_cfg, list):
            return {}, []

        type_counts: dict[str, int] = {}
        for judge_cfg in judges_cfg:
            if not isinstance(judge_cfg, dict):
                continue
            judge_type = str(judge_cfg.get("type") or "unknown")
            type_counts[judge_type] = type_counts.get(judge_type, 0) + 1

        type_idx: dict[str, int] = {}
        type_abbr_map = {
            "harmbench": "hb",
            "harmbench_variant": "hbv",
            "jailbreakbench": "jb",
            "nuanced": "nj",
            "on_topic": "on_topic",
        }

        judge_meta: dict[str, dict[str, Any]] = {}
        declared_eval_keys: list[str] = []

        for judge_idx, judge_cfg in enumerate(judges_cfg):
            if not isinstance(judge_cfg, dict):
                continue

            judge_type = str(judge_cfg.get("type") or "unknown")
            judge_name = str(
                judge_cfg.get("identifier") or judge_cfg.get("agent_name") or judge_type
            )
            abbr = type_abbr_map.get(judge_type, judge_type)

            type_idx[judge_type] = type_idx.get(judge_type, 0) + 1
            if type_counts.get(judge_type, 0) > 1:
                eval_key = f"eval_{abbr}_{type_idx[judge_type]}"
            else:
                eval_key = f"eval_{abbr}"

            declared_eval_keys.append(eval_key)
            judge_meta[eval_key] = {
                "id": judge_idx,
                "name": judge_name,
                "type": judge_type.replace("_", " ").title(),
            }

        return judge_meta, declared_eval_keys

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
        overall_effective_asr = self._safe_float(
            evaluation_summary.get("overall_effective_asr")
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
        elif overall_effective_asr is not None:
            overall_asr_rate = overall_effective_asr
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

    def _ensure_evaluation_request_response(
        self, serialized_traces: list[dict], result: dict
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
                elif atk == "mml":
                    detail_data = self._parse_mml_traces(serialized_traces)
                    self._render_mml_goal_card(row, detail_data, detail_mode=True)
                else:
                    (
                        req_text,
                        resp_text,
                        _generic_guardrail,
                    ) = self._extract_prompt_response_from_traces(serialized_traces)
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
                    ).props(
                        "flat dense size=xs color=grey-6"
                    ).tooltip("Copy to clipboard").on(
                        "click",
                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(text)});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
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
                (
                    _,
                    _node_g_side,
                    _node_g_expl,
                    _node_g_cats,
                ) = DashboardPage._extract_guardrail_from_response(response_value)
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
                                {
                                    "side": _g_side,
                                    "explanation": _g_expl,
                                    "categories": _g_cats,
                                }
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
            self._render_mml_trace_image(metadata)

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
                            if key in {"prefix", "completion"}:
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

    async def _open_run_results(self, run: dict) -> None:  # noqa: C901
        """Open report details side-by-side for a single run."""
        run_id_raw = str(run.get("id") or "")
        _run_num = run.get("run_progress") or run.get("run_number")
        self._report_current_run = run

        report_area: ui.column | None = self.run_report_area
        if self.run_dialog_title is not None:
            _title_prefix = (
                f"Report — Run #{_run_num}"
                if _run_num
                else f"Report — Run {run_id_raw[:8]}…"
            )
            self.run_dialog_title.text = _title_prefix
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
            category_subcategory_stats: dict[
                str, dict[str, dict[str, int]]
            ] = defaultdict(lambda: defaultdict(lambda: {"total": 0, "vulnerable": 0}))
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
                    _rs_chart_ref: list = []

                    async def _dl_risk_score():
                        if _rs_chart_ref:
                            await self._download_echart_svg(
                                _rs_chart_ref[0], f"risk_score_run{run_id_raw[:8]}"
                            )

                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Risk Score").classes("font-semibold text-sm")
                        ui.button(icon="download", on_click=_dl_risk_score).props(
                            "flat dense size=xs color=grey-6"
                        )
                    ui.label(
                        "Attack Success Rate across all tests in this run"
                    ).classes("text-xs text-grey-6 mb-3")
                    with ui.row().classes("items-center gap-6 flex-wrap"):
                        no_data = total_tests == 0
                        _rs_chart_ref.append(
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
                                                        "itemStyle": {
                                                            "color": "#94a3b8"
                                                        },
                                                    }
                                                ]
                                                if no_data
                                                else [
                                                    {
                                                        "value": n_jailbreaks,
                                                        "name": "Jailbreaks",
                                                        "itemStyle": {
                                                            "color": "#ef4444"
                                                        },
                                                    },
                                                    {
                                                        "value": n_mitigated,
                                                        "name": "Mitigated",
                                                        "itemStyle": {
                                                            "color": "#22c55e"
                                                        },
                                                    },
                                                    {
                                                        "value": n_errors,
                                                        "name": "Errors",
                                                        "itemStyle": {
                                                            "color": "#f97316"
                                                        },
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
                                                        "itemStyle": {
                                                            "color": "#94a3b8"
                                                        },
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
                            )
                            .classes("w-36 h-36 shrink-0")
                            .props("renderer=svg")
                        )

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

                category_items.sort(key=lambda item: item["label"])
                top_items = category_items[:9]

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
                    _rob_chart_ref: list = []

                    async def _dl_robustness():
                        if _rob_chart_ref:
                            await self._download_echart_svg(
                                _rob_chart_ref[0],
                                f"robustness_by_category_run{run_id_raw[:8]}",
                            )

                    with ui.row().classes("w-full items-start justify-between mb-1"):
                        with ui.column().classes("gap-0"):
                            ui.label("OVERALL ROBUSTNESS").classes(
                                "text-[10px] tracking-[0.24em] text-grey-6 font-semibold"
                            )
                            ui.label(f"{robustness_pct:.0f}%").classes(
                                "text-[44px] leading-none font-bold text-green-7"
                            )
                        ui.button(icon="download", on_click=_dl_robustness).props(
                            "flat dense size=xs color=grey-6"
                        )

                    with ui.row().classes("w-full justify-center"):
                        _rob_chart_ref.append(
                            ui.echart(
                                {
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
                                        "textStyle": {
                                            "color": "#111827",
                                            "fontSize": 13,
                                        },
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
                                        "splitLine": {
                                            "lineStyle": {"color": "#d1d5db"}
                                        },
                                        "splitArea": {
                                            "areaStyle": {"color": ["#ffffff"]}
                                        },
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
                            )
                            .classes("w-[740px] h-[500px] max-w-full")
                            .props("renderer=svg")
                        )

                    ui.label(
                        "Robustness = 100 - vulnerability rate per category. Hover a point for details."
                    ).classes("text-xs text-grey-6 w-full text-center mt-2")

                with ui.card().classes("w-full"):
                    _cd_chart_ref: list = []

                    async def _dl_cat_dist():
                        if _cd_chart_ref:
                            await self._download_echart_svg(
                                _cd_chart_ref[0],
                                f"category_distribution_run{run_id_raw[:8]}",
                            )

                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Vulnerability by Category").classes(
                            "font-semibold text-sm"
                        )
                        ui.button(icon="download", on_click=_dl_cat_dist).props(
                            "flat dense size=xs color=grey-6"
                        )
                    ui.label(
                        "Stacked distribution of outcomes per harm category"
                    ).classes("text-xs text-grey-6 mb-3")

                    bar_items = sorted(
                        top_items, key=lambda item: item["label"], reverse=True
                    )
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

                    _cd_chart_ref.append(
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
                                        "lineStyle": {
                                            "type": "dashed",
                                            "color": "#e5e7eb",
                                        }
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
                        )
                        .classes("w-full h-[320px]")
                        .props("renderer=svg")
                    )

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

            # ── 4b) Multi-Judge Statistics ─────────────────────────
            _rp_eval_summary = self._extract_run_evaluation_summary(run)
            _rp_judge_count = int(_rp_eval_summary.get("judge_count") or 0)
            _rp_is_multi = bool(_rp_eval_summary.get("is_multi_judge")) or (
                _rp_judge_count > 1
            )
            _rp_vote_columns: set[str] = set()
            for _rp_row in new_rows:
                _rp_vote_columns.update(
                    self._extract_eval_votes_from_result(_rp_row).keys()
                )
            if len(_rp_vote_columns) > 1:
                _rp_is_multi = True
            # Fallback: check attack config judges array
            if not _rp_is_multi:
                _rp_atk_id = str(run.get("attack_id") or run.get("attack") or "")
                if _rp_atk_id:
                    _rp_atk_cfgs = self._attack_config_map_for_ids({_rp_atk_id})
                    _rp_atk_cfg = _rp_atk_cfgs.get(_rp_atk_id, {})
                    _rp_judges_list = (
                        _rp_atk_cfg.get("judges") or []
                        if isinstance(_rp_atk_cfg, dict)
                        else []
                    )
                    if isinstance(_rp_judges_list, list) and len(_rp_judges_list) > 1:
                        _rp_is_multi = True
                        _rp_judge_count = len(_rp_judges_list)
            # Fallback: check per_judge_asr has multiple keys
            if not _rp_is_multi and _rp_eval_summary:
                _rp_pja_check = _rp_eval_summary.get("per_judge_asr")
                if isinstance(_rp_pja_check, dict) and len(_rp_pja_check) > 1:
                    _rp_is_multi = True

            # Enrich rows with multi-judge metadata for goal detail rendering
            if _rp_is_multi:
                for _rp_d in new_rows:
                    _rp_d["_is_multi_judge"] = False
                    _rp_d["_goal_multi_metrics"] = {}
                    _rp_gm = self._compute_goal_multi_judge_metrics(_rp_d)
                    if not _rp_gm:
                        _rp_pgm = _rp_eval_summary.get("per_goal_metrics")
                        if isinstance(_rp_pgm, dict):
                            _rp_goal_text = str(_rp_d.get("goal") or "")
                            _rp_goal_pgm = _rp_pgm.get(_rp_goal_text)
                            if isinstance(_rp_goal_pgm, dict):
                                _rp_pja = _rp_goal_pgm.get("per_judge_asr")
                                if isinstance(_rp_pja, dict) and _rp_pja:
                                    _rp_votes_d = {
                                        k: int(float(v) >= 0.5)
                                        for k, v in _rp_pja.items()
                                    }
                                    _rp_javg = (
                                        sum(_rp_votes_d.values()) / len(_rp_votes_d)
                                        if _rp_votes_d
                                        else None
                                    )
                                    _rp_gm = {
                                        "judge_count": len(_rp_votes_d),
                                        "judge_votes": dict(
                                            sorted(_rp_votes_d.items())
                                        ),
                                        "judge_avg": _rp_javg,
                                        "majority_vote_asr": _rp_javg,
                                    }
                    if _rp_gm:
                        _rp_d["_is_multi_judge"] = True
                        _rp_d["_goal_multi_metrics"] = _rp_gm

            if _rp_is_multi:
                _rp_vote_rows: list[dict[str, int]] = []
                for _rp_row in new_rows:
                    _rp_votes = self._extract_eval_votes_from_result(_rp_row)
                    if not _rp_votes:
                        _rp_gm_row = _rp_row.get("_goal_multi_metrics")
                        if isinstance(_rp_gm_row, dict):
                            _rp_gv = _rp_gm_row.get("judge_votes")
                            if isinstance(_rp_gv, dict) and _rp_gv:
                                _rp_votes = {
                                    _k: self._coerce_binary_vote(_v)
                                    for _k, _v in _rp_gv.items()
                                    if self._is_canonical_eval_vote_key(_k)
                                }
                    if _rp_votes:
                        _rp_vote_rows.append(dict(_rp_votes))

                _rp_majority_asr = self._safe_float(
                    _rp_eval_summary.get("majority_vote_asr")
                ) or self._safe_float(_rp_eval_summary.get("overall_majority_vote_asr"))
                if _rp_majority_asr is None and _rp_vote_rows:
                    _rp_majority_asr = calculate_majority_vote_asr(_rp_vote_rows)

                _rp_fleiss = self._safe_float(
                    _rp_eval_summary.get("fleiss_kappa")
                ) or self._safe_float(_rp_eval_summary.get("overall_fleiss_kappa"))
                if _rp_fleiss is None and _rp_vote_rows:
                    _rp_fleiss = calculate_fleiss_kappa(_rp_vote_rows)

                _rp_per_judge_asr = _rp_eval_summary.get("per_judge_asr")
                if (
                    not isinstance(_rp_per_judge_asr, dict) or not _rp_per_judge_asr
                ) and _rp_vote_rows:
                    _rp_per_judge_asr = calculate_per_judge_asr(_rp_vote_rows)

                _rp_strictness = _rp_eval_summary.get("per_judge_strictness")
                if (
                    not isinstance(_rp_strictness, dict)
                    or not any(k != "bias_gap" for k in _rp_strictness.keys())
                ) and _rp_vote_rows:
                    _rp_strictness = calculate_per_judge_strictness(_rp_vote_rows)

                # Build judge metadata for report panel
                _rp_atk_id2 = str(run.get("attack_id") or run.get("attack") or "")
                if _rp_atk_id2:
                    _rp_atk_cfgs2 = self._attack_config_map_for_ids({_rp_atk_id2})
                    _rp_atk_cfg2 = _rp_atk_cfgs2.get(_rp_atk_id2, {})
                else:
                    _rp_atk_cfg2 = {}
                _rp_judges_cfg_list2 = (
                    _rp_atk_cfg2.get("judges") or []
                    if isinstance(_rp_atk_cfg2, dict)
                    else []
                )
                _rp_judge_meta, _rp_declared_eval_keys = self._build_judge_metadata(
                    _rp_judges_cfg_list2
                )

                with ui.card().classes("w-full"):
                    # Compute judge keys early for accurate count
                    _rp_judge_key_pool = set(
                        list((_rp_per_judge_asr or {}).keys())
                        + [k for k in (_rp_strictness or {}).keys() if k != "bias_gap"]
                        + list(_rp_judge_meta.keys())
                    )
                    _rp_all_judge_keys = [
                        key
                        for key in _rp_declared_eval_keys
                        if key in _rp_judge_key_pool
                    ]
                    _rp_all_judge_keys.extend(
                        sorted(
                            key
                            for key in _rp_judge_key_pool
                            if key not in _rp_all_judge_keys
                        )
                    )
                    _rp_display_count = (
                        len(_rp_all_judge_keys)
                        if _rp_all_judge_keys
                        else len(_rp_vote_columns)
                        if _rp_vote_columns
                        else _rp_judge_count or "?"
                    )
                    with ui.row().classes("items-center gap-2 mb-3 justify-center"):
                        ui.icon("groups", size="sm").classes("text-indigo-6")
                        ui.label("Multi-Judge Statistics").classes(
                            "font-semibold text-sm"
                        )
                        ui.badge(
                            f"{_rp_display_count} judges",
                            color="indigo",
                        ).classes("text-xs")

                    # ── Row 1: Aggregate metrics ──
                    with ui.row().classes(
                        "w-full flex-wrap gap-6 items-end mb-3 justify-center"
                    ):
                        if _rp_majority_asr is not None:
                            with ui.column().classes("items-center gap-0 min-w-[90px]"):
                                ui.label(f"{_rp_majority_asr * 100:.1f}%").classes(
                                    "text-xl font-bold text-primary"
                                )
                                ui.label("Majority ASR").classes(
                                    "text-[10px] text-grey-6"
                                )

                        if _rp_fleiss is not None:
                            _rp_fk_color = (
                                "text-green-7"
                                if _rp_fleiss >= 0.6
                                else "text-orange-7"
                                if _rp_fleiss >= 0.2
                                else "text-red-7"
                            )
                            with ui.column().classes("items-center gap-0 min-w-[90px]"):
                                ui.label(f"{_rp_fleiss:.4f}").classes(
                                    f"text-xl font-bold {_rp_fk_color}"
                                )
                                ui.label("Fleiss κ").classes("text-[10px] text-grey-6")

                        if isinstance(_rp_strictness, dict):
                            _rp_bg = self._safe_float(_rp_strictness.get("bias_gap"))
                            if _rp_bg is not None:
                                _rp_bg_color = (
                                    "text-green-7"
                                    if abs(_rp_bg) < 0.1
                                    else "text-orange-7"
                                    if abs(_rp_bg) < 0.3
                                    else "text-red-7"
                                )
                                with ui.column().classes(
                                    "items-center gap-0 min-w-[90px]"
                                ):
                                    ui.label(f"{_rp_bg:.4f}").classes(
                                        f"text-xl font-bold {_rp_bg_color}"
                                    )
                                    ui.label("Bias Gap").classes(
                                        "text-[10px] text-grey-6"
                                    )

                    # ── Row 2+: Per-judge table ──
                    if _rp_all_judge_keys:
                        ui.separator().classes("my-1")
                        with ui.row().classes("w-full gap-0 px-2 py-1"):
                            ui.label("ID").classes(
                                "text-[11px] font-semibold text-grey-7 w-[52px] text-center"
                            )
                            ui.label("Judge").classes(
                                "text-[11px] font-semibold text-grey-7 w-[160px]"
                            )
                            ui.label("Type").classes(
                                "text-[11px] font-semibold text-grey-7 w-[140px]"
                            )
                            ui.label("ASR").classes(
                                "text-[11px] font-semibold text-grey-7 w-[90px] text-center"
                            )
                            ui.label("Strictness").classes(
                                "text-[11px] font-semibold text-grey-7 w-[90px] text-center ml-4"
                            )

                        for _rp_row_idx, _rp_jk in enumerate(_rp_all_judge_keys):
                            _rp_j_meta = _rp_judge_meta.get(_rp_jk, {})
                            _rp_j_id = _rp_j_meta.get("id", _rp_row_idx)
                            _rp_j_name = _rp_j_meta.get(
                                "name",
                                self._judge_key_display_name(_rp_jk),
                            )
                            _rp_j_type = (
                                _rp_j_meta.get("type")
                                or self._judge_type_from_key(_rp_jk)
                                or "—"
                            )

                            _rp_j_asr = self._safe_float(
                                (_rp_per_judge_asr or {}).get(_rp_jk)
                            )
                            _rp_j_strict = self._safe_float(
                                (_rp_strictness or {}).get(_rp_jk)
                            )

                            _rp_asr_color = "text-grey-5"
                            if _rp_j_asr is not None:
                                _rp_asr_color = (
                                    "text-red-7"
                                    if _rp_j_asr >= 0.7
                                    else "text-orange-7"
                                    if _rp_j_asr >= 0.3
                                    else "text-green-7"
                                )

                            _rp_strict_color = "text-grey-5"
                            if _rp_j_strict is not None:
                                _rp_strict_color = (
                                    "text-green-7"
                                    if _rp_j_strict >= 0.7
                                    else "text-orange-7"
                                    if _rp_j_strict >= 0.3
                                    else "text-red-7"
                                )

                            with ui.row().classes(
                                "w-full gap-0 px-2 py-1 items-center "
                                "hover:bg-grey-1 rounded"
                            ):
                                ui.label(str(_rp_j_id)).classes(
                                    "text-xs text-grey-7 font-medium w-[52px] text-center"
                                )
                                ui.label(_rp_j_name).classes(
                                    "text-xs font-medium w-[160px] truncate"
                                )
                                ui.label(_rp_j_type).classes(
                                    "text-xs text-grey-6 w-[140px]"
                                )
                                ui.label(
                                    f"{_rp_j_asr * 100:.1f}%"
                                    if _rp_j_asr is not None
                                    else "—"
                                ).classes(
                                    f"text-xs font-bold {_rp_asr_color} w-[90px] text-center"
                                )
                                ui.label(
                                    f"{_rp_j_strict:.4f}"
                                    if _rp_j_strict is not None
                                    else "—"
                                ).classes(
                                    f"text-xs font-bold {_rp_strict_color} w-[90px] text-center ml-4"
                                )

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
        """Open the compact results list in a non-modal side dialog."""
        run_id_raw = str(run.get("id") or "")
        _run_num = run.get("run_progress") or run.get("run_number")

        if self.history_run_dialog_title is not None:
            _title_prefix = (
                f"Run Results — #{_run_num}"
                if _run_num
                else f"Run Results — {run_id_raw[:8]}…"
            )
            self.history_run_dialog_title.text = _title_prefix

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
        self._history_dialog_attack_str = attack_type_str

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
                    "mml": "MML",
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
                    elif _atk_lower == "mml":
                        _mml_params = _hcfg.get("mml_params") or {}
                        if isinstance(_mml_params, dict):
                            _mml_enc = _mml_params.get("encoding_mode", "")
                            if _mml_enc:
                                _chip("image", "Encoding", str(_mml_enc))

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

                # ── Line 4: Guardrails (if present) ───────────────────
                _h_bg = _hrc.get("before_guardrail")
                _h_ag = _hrc.get("after_guardrail")
                if _h_bg or _h_ag:
                    with ui.row().classes("flex-wrap gap-2 items-center mt-1"):
                        if _h_bg:
                            _h_bg_id = (
                                _h_bg.get("identifier", "—")
                                if isinstance(_h_bg, dict)
                                else str(_h_bg)
                            )
                            _chip("shield", "Before Guardrail", _h_bg_id)
                        if _h_ag:
                            _h_ag_id = (
                                _h_ag.get("identifier", "—")
                                if isinstance(_h_ag, dict)
                                else str(_h_ag)
                            )
                            _chip("shield", "After Guardrail", _h_ag_id)

        if self.history_results_list_area is not None:
            self.history_results_list_area.clear()
        if self.history_results_empty_label is not None:
            self.history_results_empty_label.text = "Loading results…"
            self.history_results_empty_label.set_visibility(True)

        self._history_current_run = run

        self._open_runs_bottom_panel()

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

            # ── Enrich rows with per-goal multi-judge verdicts ──────
            _hr_eval_summary: dict = {}
            if isinstance(run_config, dict):
                _es = run_config.get("evaluation_summary")
                if isinstance(_es, dict):
                    _hr_eval_summary = _es
            if not _hr_eval_summary:
                _hr_eval_summary = self._extract_run_evaluation_summary(run)
            _hr_is_multi = bool(_hr_eval_summary.get("is_multi_judge")) or (
                int(_hr_eval_summary.get("judge_count") or 0) > 1
            )
            if not _hr_is_multi:
                _hr_vc: set[str] = set()
                for _hr_r in new_rows:
                    _hr_vc.update(self._extract_eval_votes_from_result(_hr_r).keys())
                if len(_hr_vc) > 1:
                    _hr_is_multi = True
            if not _hr_is_multi:
                _hr_acfg = display_config if isinstance(display_config, dict) else {}
                _hr_jl = _hr_acfg.get("judges") or []
                if isinstance(_hr_jl, list) and len(_hr_jl) > 1:
                    _hr_is_multi = True
            if not _hr_is_multi and _hr_eval_summary:
                _hr_pja_check = _hr_eval_summary.get("per_judge_asr")
                if isinstance(_hr_pja_check, dict) and len(_hr_pja_check) > 1:
                    _hr_is_multi = True

            # Build judge metadata mapping: eval_key -> {id, name, type}
            _hr_judge_meta: dict[str, dict[str, Any]] = {}
            _hr_acfg2 = display_config if isinstance(display_config, dict) else {}
            _hr_jl2 = _hr_acfg2.get("judges") or []
            _hr_judge_meta, _ = self._build_judge_metadata(_hr_jl2)

            # Keep the latest judge metadata so the right panel can
            # reuse the exact same name/type mapping as the left panel
            # even when row-level metadata is missing in legacy runs.
            self._history_last_judge_meta = _hr_judge_meta

            for _hr_d in new_rows:
                _hr_d["_is_multi_judge"] = False
                _hr_d["_goal_multi_metrics"] = {}
                if _hr_is_multi:
                    _hr_gm = self._compute_goal_multi_judge_metrics(_hr_d)
                    if not _hr_gm:
                        _hr_pgm = _hr_eval_summary.get("per_goal_metrics")
                        if isinstance(_hr_pgm, dict):
                            _hr_gt = str(_hr_d.get("goal") or "")
                            _hr_gpgm = _hr_pgm.get(_hr_gt)
                            if isinstance(_hr_gpgm, dict):
                                _hr_pja = _hr_gpgm.get("per_judge_asr")
                                if isinstance(_hr_pja, dict) and _hr_pja:
                                    _hr_votes = {
                                        k: int(float(v) >= 0.5)
                                        for k, v in _hr_pja.items()
                                    }
                                    _hr_javg = (
                                        sum(_hr_votes.values()) / len(_hr_votes)
                                        if _hr_votes
                                        else None
                                    )
                                    _hr_gm = {
                                        "judge_count": len(_hr_votes),
                                        "judge_votes": dict(sorted(_hr_votes.items())),
                                        "judge_avg": _hr_javg,
                                        "majority_vote_asr": _hr_javg,
                                    }
                    if _hr_gm:
                        if _hr_judge_meta:
                            _hr_gm["judge_meta"] = _hr_judge_meta
                        _hr_d["_is_multi_judge"] = True
                        _hr_d["_goal_multi_metrics"] = _hr_gm

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

            # ── Populate charts area (before goals) ───────────────────
            if self.history_charts_area is not None and new_rows:
                self.history_charts_area.clear()
                _n_jailbreaks = sum(
                    1 for r in new_rows if r.get("_bucket") == "jailbreak"
                )
                _n_mitigated = sum(
                    1 for r in new_rows if r.get("_bucket") == "mitigated"
                )
                _n_errors = sum(1 for r in new_rows if r.get("_bucket") == "failed")
                _total = len(new_rows)
                _asr = (100.0 * _n_jailbreaks / _total) if _total > 0 else 0.0
                _robustness = 100.0 - _asr
                _risk_hex = (
                    "#ef4444"
                    if _asr >= 70
                    else "#f97316"
                    if _asr >= 40
                    else "#eab308"
                    if _asr >= 10
                    else "#22c55e"
                )
                _risk_label = (
                    "Critical"
                    if _asr >= 70
                    else "High"
                    if _asr >= 40
                    else "Medium"
                    if _asr >= 10
                    else "Low"
                )
                _no_data = _total == 0

                with self.history_charts_area:
                    # ── Risk donut + Robustness side by side ───────────
                    with ui.row().classes("w-full flex-wrap gap-4 items-stretch"):
                        # Risk donut
                        with ui.card().classes("flex-1 min-w-64"):
                            _hrs_chart_ref: list = []

                            async def _dl_hrs():
                                if _hrs_chart_ref:
                                    await self._download_echart_svg(
                                        _hrs_chart_ref[0],
                                        f"risk_score_run{run_id_raw[:8]}",
                                    )

                            with ui.row().classes(
                                "items-center justify-between w-full"
                            ):
                                ui.label("Risk Score").classes("font-semibold text-sm")
                                ui.button(icon="download", on_click=_dl_hrs).props(
                                    "flat dense size=xs color=grey-6"
                                )
                            ui.label("Attack Success Rate across all tests").classes(
                                "text-xs text-grey-6 mb-3"
                            )
                            with ui.row().classes("items-center gap-6 flex-wrap"):
                                _hrs_chart_ref.append(
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
                                                                "itemStyle": {
                                                                    "color": "#94a3b8"
                                                                },
                                                            }
                                                        ]
                                                        if _no_data
                                                        else [
                                                            {
                                                                "value": _n_jailbreaks,
                                                                "name": "Jailbreaks",
                                                                "itemStyle": {
                                                                    "color": "#ef4444"
                                                                },
                                                            },
                                                            {
                                                                "value": _n_mitigated,
                                                                "name": "Mitigated",
                                                                "itemStyle": {
                                                                    "color": "#22c55e"
                                                                },
                                                            },
                                                            {
                                                                "value": _n_errors,
                                                                "name": "Errors",
                                                                "itemStyle": {
                                                                    "color": "#f97316"
                                                                },
                                                            },
                                                            {
                                                                "value": max(
                                                                    0,
                                                                    _total
                                                                    - _n_jailbreaks
                                                                    - _n_mitigated
                                                                    - _n_errors,
                                                                ),
                                                                "name": "Pending",
                                                                "itemStyle": {
                                                                    "color": "#94a3b8"
                                                                },
                                                            },
                                                        ]
                                                    ),
                                                    "label": {"show": False},
                                                    "emphasis": {"scale": False},
                                                }
                                            ],
                                            "graphic": (
                                                []
                                                if _no_data
                                                else [
                                                    {
                                                        "type": "group",
                                                        "left": "center",
                                                        "top": "center",
                                                        "children": [
                                                            {
                                                                "type": "text",
                                                                "style": {
                                                                    "text": f"{_asr:.0f}%",
                                                                    "textAlign": "center",
                                                                    "fontSize": 22,
                                                                    "fontWeight": "bold",
                                                                    "fill": _risk_hex,
                                                                },
                                                                "top": -14,
                                                            },
                                                            {
                                                                "type": "text",
                                                                "style": {
                                                                    "text": _risk_label,
                                                                    "textAlign": "center",
                                                                    "fontSize": 11,
                                                                    "fill": _risk_hex,
                                                                },
                                                                "top": 12,
                                                            },
                                                        ],
                                                    }
                                                ]
                                            ),
                                            "tooltip": {
                                                "trigger": "item"
                                                if not _no_data
                                                else "none"
                                            },
                                        }
                                    )
                                    .classes("w-36 h-36 shrink-0")
                                    .props("renderer=svg")
                                )

                                # Legend
                                with ui.column().classes("gap-1"):
                                    for _leg_l, _leg_c, _leg_clr in [
                                        ("Jailbreaks", _n_jailbreaks, "#ef4444"),
                                        ("Mitigated", _n_mitigated, "#22c55e"),
                                        ("Errors", _n_errors, "#f97316"),
                                        (
                                            "Pending",
                                            max(
                                                0,
                                                _total
                                                - _n_jailbreaks
                                                - _n_mitigated
                                                - _n_errors,
                                            ),
                                            "#94a3b8",
                                        ),
                                    ]:
                                        if _leg_c > 0 or not _no_data:
                                            with ui.row().classes("items-center gap-2"):
                                                ui.element("div").classes(
                                                    "w-2.5 h-2.5 rounded-full shrink-0"
                                                ).style(f"background:{_leg_clr}")
                                                ui.label(f"{_leg_l}: {_leg_c}").classes(
                                                    "text-xs"
                                                )

                        # Robustness bar
                        with ui.card().classes("flex-1 min-w-64"):
                            ui.label("Robustness").classes("font-semibold text-sm mb-1")
                            ui.label("Percentage of tests the agent resisted").classes(
                                "text-xs text-grey-6 mb-3"
                            )
                            with ui.column().classes("gap-3 w-full"):
                                with ui.row().classes("items-end gap-2"):
                                    ui.label(f"{_robustness:.0f}%").classes(
                                        "text-4xl font-bold"
                                    )
                                    _rob_color = (
                                        "positive"
                                        if _robustness >= 80
                                        else "warning"
                                        if _robustness >= 50
                                        else "negative"
                                    )
                                    _rob_word = (
                                        "Strong"
                                        if _robustness >= 80
                                        else "Moderate"
                                        if _robustness >= 50
                                        else "Weak"
                                    )
                                    ui.badge(_rob_word, color=_rob_color).classes(
                                        "text-xs mb-1"
                                    )
                                ui.linear_progress(
                                    value=_robustness / 100.0,
                                    show_value=False,
                                    color=_rob_color,
                                ).classes("w-full").props("rounded size=12px")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label(f"{_n_mitigated} mitigated").classes(
                                        "text-xs text-grey-6"
                                    )
                                    ui.label(f"{_n_jailbreaks} vulnerable").classes(
                                        "text-xs text-grey-6"
                                    )

                    # ── Category radar (if categories exist) ──────────
                    _hc_cat_stats: dict[str, dict[str, int]] = defaultdict(
                        lambda: {
                            "total": 0,
                            "vulnerable": 0,
                            "mitigated": 0,
                            "errors": 0,
                        }
                    )
                    for _row in new_rows:
                        _cat = _row.get("_goal_category") or ""
                        if not _cat or _cat == "N/A":
                            continue
                        _bkt = _row.get("_bucket", "pending")
                        _entry = _hc_cat_stats[_cat]
                        _entry["total"] += 1
                        if _bkt == "jailbreak":
                            _entry["vulnerable"] += 1
                        elif _bkt == "mitigated":
                            _entry["mitigated"] += 1
                        elif _bkt == "failed":
                            _entry["errors"] += 1

                    if _hc_cat_stats:
                        _hc_items = []
                        for _lbl, _sts in _hc_cat_stats.items():
                            _t = int(_sts.get("total") or 0)
                            _v = int(_sts.get("vulnerable") or 0)
                            if _t <= 0:
                                continue
                            _hc_items.append(
                                {
                                    "label": _lbl,
                                    "total": _t,
                                    "vulnerable": _v,
                                    "mitigated": int(_sts.get("mitigated") or 0),
                                    "errors": int(_sts.get("errors") or 0),
                                    "robustness": 100.0 * (_t - _v) / _t,
                                }
                            )
                        _hc_items.sort(key=lambda x: x["label"], reverse=True)
                        if _hc_items:
                            with ui.column().classes("w-full gap-3"):
                                with ui.card().classes("w-full"):
                                    _hcb_chart_ref: list = []

                                    async def _dl_hcb():
                                        if _hcb_chart_ref:
                                            await self._download_echart_svg(
                                                _hcb_chart_ref[0],
                                                f"category_breakdown_run{run_id_raw[:8]}",
                                            )

                                    with ui.row().classes(
                                        "items-center justify-between w-full"
                                    ):
                                        ui.label("Vulnerability by Category").classes(
                                            "font-semibold text-sm"
                                        )
                                        ui.button(
                                            icon="download", on_click=_dl_hcb
                                        ).props("flat dense size=xs color=grey-6")
                                    _hc_labels = [x["label"] for x in _hc_items]
                                    _hc_vuln = [x["vulnerable"] for x in _hc_items]
                                    _hc_mit = [x["mitigated"] for x in _hc_items]
                                    _hc_err = [x["errors"] for x in _hc_items]
                                    _hcb_chart_ref.append(
                                        ui.echart(
                                            {
                                                "tooltip": {"trigger": "axis"},
                                                "legend": {
                                                    "data": [
                                                        "Vulnerable",
                                                        "Mitigated",
                                                        "Errors",
                                                    ],
                                                    "bottom": 0,
                                                },
                                                "grid": {
                                                    "left": "3%",
                                                    "right": "4%",
                                                    "top": "3%",
                                                    "bottom": "14%",
                                                    "containLabel": True,
                                                },
                                                "xAxis": {"type": "value"},
                                                "yAxis": {
                                                    "type": "category",
                                                    "data": _hc_labels,
                                                    "axisLabel": {
                                                        "width": 140,
                                                        "overflow": "truncate",
                                                    },
                                                },
                                                "series": [
                                                    {
                                                        "name": "Vulnerable",
                                                        "type": "bar",
                                                        "stack": "total",
                                                        "data": _hc_vuln,
                                                        "itemStyle": {
                                                            "color": "#ef4444"
                                                        },
                                                    },
                                                    {
                                                        "name": "Mitigated",
                                                        "type": "bar",
                                                        "stack": "total",
                                                        "data": _hc_mit,
                                                        "itemStyle": {
                                                            "color": "#22c55e"
                                                        },
                                                    },
                                                    {
                                                        "name": "Errors",
                                                        "type": "bar",
                                                        "stack": "total",
                                                        "data": _hc_err,
                                                        "itemStyle": {
                                                            "color": "#f97316"
                                                        },
                                                    },
                                                ],
                                            }
                                        )
                                        .classes("w-full h-72")
                                        .props("renderer=svg")
                                    )

                                # Radar chart (only when 3+ categories)
                                if len(_hc_items) >= 3:
                                    _hc_top = _hc_items[:9]
                                    _hc_top.sort(key=lambda x: x["label"])
                                    _hc_indicators = [
                                        {"name": x["label"], "max": 100}
                                        for x in _hc_top
                                    ]
                                    _hc_values = [
                                        round(x["robustness"], 1) for x in _hc_top
                                    ]

                                    with ui.card().classes("w-full"):
                                        _hcr_chart_ref: list = []

                                        async def _dl_hcr():
                                            if _hcr_chart_ref:
                                                await self._download_echart_svg(
                                                    _hcr_chart_ref[0],
                                                    f"robustness_radar_run{run_id_raw[:8]}",
                                                )

                                        with ui.row().classes(
                                            "items-center justify-between w-full"
                                        ):
                                            ui.label("Robustness by Category").classes(
                                                "font-semibold text-sm"
                                            )
                                            ui.button(
                                                icon="download", on_click=_dl_hcr
                                            ).props("flat dense size=xs color=grey-6")
                                        with ui.row().classes("w-full justify-center"):
                                            _hcr_chart_ref.append(
                                                ui.echart(
                                                    {
                                                        "radar": {
                                                            "shape": "polygon",
                                                            "indicator": _hc_indicators,
                                                            "splitNumber": 5,
                                                            "center": ["50%", "52%"],
                                                            "radius": "64%",
                                                            "axisName": {
                                                                "fontSize": 11,
                                                                "color": "#374151",
                                                            },
                                                            "splitLine": {
                                                                "lineStyle": {
                                                                    "color": "#d1d5db"
                                                                }
                                                            },
                                                            "splitArea": {
                                                                "areaStyle": {
                                                                    "color": ["#ffffff"]
                                                                }
                                                            },
                                                        },
                                                        "series": [
                                                            {
                                                                "type": "radar",
                                                                "symbol": "circle",
                                                                "symbolSize": 8,
                                                                "itemStyle": {
                                                                    "color": "#22c55e"
                                                                },
                                                                "lineStyle": {
                                                                    "color": "#22c55e",
                                                                    "width": 2,
                                                                },
                                                                "areaStyle": {
                                                                    "color": "rgba(34,197,94,0.15)"
                                                                },
                                                                "data": [
                                                                    {
                                                                        "value": _hc_values,
                                                                        "name": "Robustness",
                                                                    }
                                                                ],
                                                            }
                                                        ],
                                                        "tooltip": {"trigger": "item"},
                                                    }
                                                )
                                                .classes("w-full h-72")
                                                .props("renderer=svg")
                                            )

            # ── Populate multi-judge statistics panel ─────────────────
            if self.history_multi_judge_panel is not None:
                self.history_multi_judge_panel.clear()
                # Compute multi-judge data — use already-resolved run_config
                _mj_eval_summary: dict = {}
                if isinstance(run_config, dict):
                    _es = run_config.get("evaluation_summary")
                    if isinstance(_es, dict):
                        _mj_eval_summary = _es
                if not _mj_eval_summary:
                    _mj_eval_summary = self._extract_run_evaluation_summary(run)
                _mj_judge_count = int(_mj_eval_summary.get("judge_count") or 0)
                _mj_is_multi = bool(_mj_eval_summary.get("is_multi_judge")) or (
                    _mj_judge_count > 1
                )
                # Also check actual vote columns in results
                _mj_vote_columns: set[str] = set()
                for _mj_row in new_rows:
                    _mj_vote_columns.update(
                        self._extract_eval_votes_from_result(_mj_row).keys()
                    )
                if len(_mj_vote_columns) > 1:
                    _mj_is_multi = True
                # Fallback: check attack config judges array
                if not _mj_is_multi:
                    _mj_attack_cfg = (
                        display_config if isinstance(display_config, dict) else {}
                    )
                    _mj_judges_list = _mj_attack_cfg.get("judges") or []
                    if isinstance(_mj_judges_list, list) and len(_mj_judges_list) > 1:
                        _mj_is_multi = True
                        _mj_judge_count = len(_mj_judges_list)
                # Fallback: check per_judge_asr has multiple keys
                if not _mj_is_multi and _mj_eval_summary:
                    _mj_pja_check = _mj_eval_summary.get("per_judge_asr")
                    if isinstance(_mj_pja_check, dict) and len(_mj_pja_check) > 1:
                        _mj_is_multi = True

                if _mj_is_multi:
                    # Build vote rows for metric computation
                    _mj_vote_rows: list[dict[str, int]] = []
                    for _mj_row in new_rows:
                        _mj_votes = self._extract_eval_votes_from_result(_mj_row)
                        if not _mj_votes:
                            _mj_gm_row = _mj_row.get("_goal_multi_metrics")
                            if isinstance(_mj_gm_row, dict):
                                _mj_gv = _mj_gm_row.get("judge_votes")
                                if isinstance(_mj_gv, dict) and _mj_gv:
                                    _mj_votes = {
                                        _k: self._coerce_binary_vote(_v)
                                        for _k, _v in _mj_gv.items()
                                        if self._is_canonical_eval_vote_key(_k)
                                    }
                        if not _mj_votes:
                            _mj_rid = str(_mj_row.get("id") or "")
                            _mj_traces = generic_traces_map_hr.get(_mj_rid, [])
                            _mj_trace_votes: dict[str, int] = {}
                            for _mj_td in _mj_traces:
                                _mj_content = _mj_td.get("content")
                                if not isinstance(_mj_content, dict):
                                    continue
                                if (
                                    str(_mj_content.get("step_name") or "")
                                    != "Evaluation"
                                ):
                                    continue
                                for _mj_src in (
                                    _mj_content,
                                    _mj_content.get("result")
                                    if isinstance(_mj_content.get("result"), dict)
                                    else {},
                                ):
                                    if not isinstance(_mj_src, dict):
                                        continue
                                    for _mj_k, _mj_v in _mj_src.items():
                                        if not self._is_canonical_eval_vote_key(_mj_k):
                                            continue
                                        if _mj_v is None:
                                            continue
                                        _mj_trace_votes[
                                            _mj_k
                                        ] = self._coerce_binary_vote(_mj_v)
                            if _mj_trace_votes:
                                _mj_votes = dict(sorted(_mj_trace_votes.items()))
                        if _mj_votes:
                            _mj_vote_rows.append(dict(_mj_votes))

                    # Compute metrics
                    _mj_majority_asr = self._safe_float(
                        _mj_eval_summary.get("majority_vote_asr")
                    ) or self._safe_float(
                        _mj_eval_summary.get("overall_majority_vote_asr")
                    )
                    if _mj_majority_asr is None and _mj_vote_rows:
                        _mj_majority_asr = calculate_majority_vote_asr(_mj_vote_rows)

                    _mj_fleiss = self._safe_float(
                        _mj_eval_summary.get("fleiss_kappa")
                    ) or self._safe_float(_mj_eval_summary.get("overall_fleiss_kappa"))
                    if _mj_fleiss is None and _mj_vote_rows:
                        _mj_fleiss = calculate_fleiss_kappa(_mj_vote_rows)

                    _mj_per_judge_asr = _mj_eval_summary.get("per_judge_asr")
                    if (
                        not isinstance(_mj_per_judge_asr, dict) or not _mj_per_judge_asr
                    ) and _mj_vote_rows:
                        _mj_per_judge_asr = calculate_per_judge_asr(_mj_vote_rows)

                    _mj_strictness = _mj_eval_summary.get("per_judge_strictness")
                    if (
                        not isinstance(_mj_strictness, dict)
                        or not any(k != "bias_gap" for k in _mj_strictness.keys())
                    ) and _mj_vote_rows:
                        _mj_strictness = calculate_per_judge_strictness(_mj_vote_rows)

                    # Build judge metadata mapping: eval_key -> {name, type}
                    _mj_attack_cfg = (
                        display_config if isinstance(display_config, dict) else {}
                    )
                    _mj_judges_cfg_list = _mj_attack_cfg.get("judges") or []
                    _mj_judge_meta, _mj_declared_eval_keys = self._build_judge_metadata(
                        _mj_judges_cfg_list
                    )

                    with self.history_multi_judge_panel:
                        with ui.card().classes("w-full"):
                            # Compute judge keys early for accurate count
                            _mj_judge_key_pool = set(
                                list((_mj_per_judge_asr or {}).keys())
                                + [
                                    k
                                    for k in (_mj_strictness or {}).keys()
                                    if k != "bias_gap"
                                ]
                                + list(_mj_judge_meta.keys())
                            )
                            _mj_all_judge_keys = [
                                key
                                for key in _mj_declared_eval_keys
                                if key in _mj_judge_key_pool
                            ]
                            _mj_all_judge_keys.extend(
                                sorted(
                                    key
                                    for key in _mj_judge_key_pool
                                    if key not in _mj_all_judge_keys
                                )
                            )
                            _mj_display_count = (
                                len(_mj_all_judge_keys)
                                if _mj_all_judge_keys
                                else len(_mj_vote_columns)
                                if _mj_vote_columns
                                else _mj_judge_count or "?"
                            )
                            with ui.row().classes(
                                "items-center gap-2 mb-3 justify-center"
                            ):
                                ui.icon("groups", size="sm").classes("text-indigo-6")
                                ui.label("Multi-Judge Statistics").classes(
                                    "font-semibold text-sm"
                                )
                                ui.badge(
                                    f"{_mj_display_count} judges",
                                    color="indigo",
                                ).classes("text-xs")

                            # ── Row 1: Aggregate metrics ──
                            with ui.row().classes(
                                "w-full flex-wrap gap-6 items-end mb-3 justify-center"
                            ):
                                # Majority Vote ASR
                                if _mj_majority_asr is not None:
                                    with ui.column().classes(
                                        "items-center gap-0 min-w-[90px]"
                                    ):
                                        ui.label(
                                            f"{_mj_majority_asr * 100:.1f}%"
                                        ).classes("text-xl font-bold text-primary")
                                        ui.label("Majority ASR").classes(
                                            "text-[10px] text-grey-6"
                                        )

                                # Fleiss Kappa
                                if _mj_fleiss is not None:
                                    _fk_color = (
                                        "text-green-7"
                                        if _mj_fleiss >= 0.6
                                        else "text-orange-7"
                                        if _mj_fleiss >= 0.2
                                        else "text-red-7"
                                    )
                                    with ui.column().classes(
                                        "items-center gap-0 min-w-[90px]"
                                    ):
                                        ui.label(f"{_mj_fleiss:.4f}").classes(
                                            f"text-xl font-bold {_fk_color}"
                                        )
                                        ui.label("Fleiss κ").classes(
                                            "text-[10px] text-grey-6"
                                        )

                                # Bias gap
                                if isinstance(_mj_strictness, dict):
                                    _bg = self._safe_float(
                                        _mj_strictness.get("bias_gap")
                                    )
                                    if _bg is not None:
                                        _bg_color = (
                                            "text-green-7"
                                            if abs(_bg) < 0.1
                                            else "text-orange-7"
                                            if abs(_bg) < 0.3
                                            else "text-red-7"
                                        )
                                        with ui.column().classes(
                                            "items-center gap-0 min-w-[90px]"
                                        ):
                                            ui.label(f"{_bg:.4f}").classes(
                                                f"text-xl font-bold {_bg_color}"
                                            )
                                            ui.label("Bias Gap").classes(
                                                "text-[10px] text-grey-6"
                                            )

                            # ── Row 2+: Per-judge table ──
                            if _mj_all_judge_keys:
                                ui.separator().classes("my-1")
                                # Table header
                                with ui.row().classes("w-full gap-0 px-2 py-1"):
                                    ui.label("ID").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[52px] text-center"
                                    )
                                    ui.label("Judge").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[160px]"
                                    )
                                    ui.label("Type").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[140px]"
                                    )
                                    ui.label("ASR").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[90px] text-center"
                                    )
                                    ui.label("Strictness").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[90px] text-center ml-4"
                                    )

                                for _row_idx, _jk in enumerate(_mj_all_judge_keys):
                                    _j_meta = _mj_judge_meta.get(_jk, {})
                                    _j_id = _j_meta.get("id", _row_idx)
                                    _j_name = _j_meta.get(
                                        "name",
                                        self._judge_key_display_name(_jk),
                                    )
                                    _j_type = (
                                        _j_meta.get("type")
                                        or self._judge_type_from_key(_jk)
                                        or "—"
                                    )

                                    _j_asr = self._safe_float(
                                        (_mj_per_judge_asr or {}).get(_jk)
                                    )
                                    _j_strict = self._safe_float(
                                        (_mj_strictness or {}).get(_jk)
                                    )

                                    # ASR color
                                    _asr_color = "text-grey-5"
                                    if _j_asr is not None:
                                        _asr_color = (
                                            "text-red-7"
                                            if _j_asr >= 0.7
                                            else "text-orange-7"
                                            if _j_asr >= 0.3
                                            else "text-green-7"
                                        )

                                    # Strictness color
                                    _strict_color = "text-grey-5"
                                    if _j_strict is not None:
                                        _strict_color = (
                                            "text-green-7"
                                            if _j_strict >= 0.7
                                            else "text-orange-7"
                                            if _j_strict >= 0.3
                                            else "text-red-7"
                                        )

                                    with ui.row().classes(
                                        "w-full gap-0 px-2 py-1 items-center "
                                        "hover:bg-grey-1 rounded"
                                    ):
                                        ui.label(str(_j_id)).classes(
                                            "text-xs text-grey-7 font-medium w-[52px] text-center"
                                        )
                                        ui.label(_j_name).classes(
                                            "text-xs font-medium w-[160px] truncate"
                                        )
                                        ui.label(_j_type).classes(
                                            "text-xs text-grey-6 w-[140px]"
                                        )
                                        ui.label(
                                            f"{_j_asr * 100:.1f}%"
                                            if _j_asr is not None
                                            else "—"
                                        ).classes(
                                            f"text-xs font-bold {_asr_color} w-[90px] text-center"
                                        )
                                        ui.label(
                                            f"{_j_strict:.4f}"
                                            if _j_strict is not None
                                            else "—"
                                        ).classes(
                                            f"text-xs font-bold {_strict_color} w-[90px] text-center ml-4"
                                        )

            if all_items and self.history_results_list_area is not None:
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
                    elif _h_atk == "mml":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_mml_traces(_t)
                    else:
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[
                            _rid
                        ] = self._extract_prompt_response_from_traces(
                            _t
                        )  # returns (req, resp, guardrail_event)

                # Store for filter re-rendering
                self._history_goal_rows = new_rows
                self._history_goal_detail_data = _h_detail_data
                self._history_goal_filter = ""
                self._history_goal_filter_category = ""
                self._history_goal_filter_search = ""
                # Update filter bar
                if self._history_goal_filter_area is not None:
                    self._history_goal_filter_area.clear()
                    with self._history_goal_filter_area:
                        self._build_goal_filter_bar()
                # Render all goals
                self._render_filtered_history_goals()
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
