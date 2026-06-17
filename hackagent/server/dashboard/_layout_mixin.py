# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dashboard UI layout builders and navigation.

Provides ``DashboardLayoutMixin``, one of the mixins composed into
``DashboardPage``. It owns the *static skeleton* of the page: the drawers,
sidebar, header, the per-view panels (dashboard/agents/attacks/runs/reports)
and the modal dialogs. It also handles theme toggling and switching between
views.

These methods only build widgets and wire up callbacks; the actual data that
populates them is loaded by the data/reports/results mixins. Like all mixins
in this package, the methods run on a live ``DashboardPage`` instance and rely
on the attributes created in ``DashboardPage.__init__`` (e.g. ``self.backend``,
``self.all_panels``).

Key entry points:
    _build_sidebar / _build_header / _build_panels: assemble the chrome.
    _build_*_panel: build each view's content area.
    navigate / _highlight_nav / _toggle_dark: navigation and theme state.
"""

from __future__ import annotations

import asyncio

from nicegui import app as _fastapi_app
from nicegui import ui


from ._components import make_run_table
from ._constants import (
    _VIEW_LABELS,
)


class DashboardLayoutMixin:
    """Dashboard UI layout builders and navigation."""

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
                ).props("dense outlined clearable").classes(
                    "min-w-[100px] max-w-[180px] flex-1"
                ).on(
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
                ui.add_css("""
                    .runs-table-top-pagination .q-table__container {
                        display: flex;
                        flex-direction: column;
                    }
                    .runs-table-top-pagination .q-table__bottom {
                        order: -1;
                        border-bottom: 1px solid #e0e0e0;
                        border-top: none;
                    }
                """)
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
