# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DashboardPage — all NiceGUI UI layout and data-loading logic."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import re
from uuid import UUID

from nicegui import app as _fastapi_app
from nicegui import ui

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
    "agents": "Agents",
    "attacks": "Attacks",
    "runs": "History",
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
        self.recent_runs_table: ui.table | None = None

        # Agents / Attacks / Runs panel widgets
        self.agents_table: ui.table | None = None
        self.attacks_table: ui.table | None = None
        self.runs_table: ui.table | None = None
        self.runs_count_label: ui.label | None = None
        self.runs_page_label: ui.label | None = None
        self.runs_current_page: int = 1
        self.runs_total_pages: int = 1

        # Run results dialog
        self.run_dialog: ui.dialog | None = None
        self.run_dialog_title: ui.label | None = None
        self.run_dialog_subtitle: ui.label | None = None
        self.results_list_area: ui.column | None = None
        self.results_empty_label: ui.label | None = None
        self.metrics_area: ui.column | None = None

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
                is_remote = self.backend.get_api_key() is not None
                dot_color = "text-info" if is_remote else "text-positive"
                mode_text = "remote mode" if is_remote else "local mode"
                ui.icon("circle", size="xs").classes(f"{dot_color} text-xs")
                ui.label(mode_text).classes("text-xs text-grey-6")
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
                                "data": [
                                    "Jailbreaks",
                                    "Failed attacks",
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
                        lambda r=run: asyncio.create_task(self._open_run_results(r)),
                        once=True,
                    ),
                    include_agent=True,
                    include_progressive_run=True,
                    include_results=True,
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
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center justify-between mb-1 px-2"):
                    self.runs_count_label = ui.label("").classes("text-sm text-grey-6")
                    with ui.row().classes("items-center gap-2"):
                        self._runs_delete_btn = (
                            ui.button(
                                "Delete selected",
                                icon="delete",
                                on_click=lambda: ui.timer(
                                    0, self._delete_selected_runs, once=True
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
                self.runs_table = make_run_table(
                    on_row_click=lambda run: ui.timer(
                        0,
                        lambda r=run: asyncio.create_task(self._open_run_results(r)),
                        once=True,
                    ),
                    pagination={"rowsPerPage": 0},
                    include_agent=True,
                    include_progressive_run=True,
                    include_results=False,
                    selection="multiple",
                    on_select=lambda e: self._on_runs_select(),
                )
                self.runs_table.props("hide-pagination")

    def _build_run_dialog(self) -> None:
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-5xl h-[80vh] flex flex-col gap-0"):
                with ui.row().classes("items-center justify-between w-full shrink-0 px-4 py-3 border-b"):
                    self.run_dialog_title = ui.label("Run Results").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                self.run_dialog_subtitle = ui.label("—").classes(
                    "text-xs text-grey-6 px-4 py-2"
                )

                # ── Tabbed interface ──────────────────────────────────────────
                with ui.tabs().classes("w-full") as tabs:
                    results_tab = ui.tab("Results", icon="list_alt")
                    metrics_tab = ui.tab("Metrics", icon="analytics")

                with ui.tab_panels(tabs, value=results_tab).classes("w-full flex-1 gap-0"):
                    with ui.tab_panel(results_tab).classes("w-full flex-1 flex flex-col"):
                        self.results_empty_label = ui.label("Loading results...").classes(
                            "text-sm text-grey-8 px-4 py-4"
                        )
                        with ui.scroll_area().classes("w-full flex-1"):
                            self.results_list_area = ui.column().classes("w-full gap-3 p-4")

                    with ui.tab_panel(metrics_tab).classes("w-full flex-1 overflow-auto"):
                        with ui.scroll_area().classes("w-full h-full"):
                            self.metrics_area = ui.column().classes("w-full gap-4 p-4")
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
                    ).classes("w-full text-xs max-h-60 overflow-auto")

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
                                        0, lambda: self._open_run_results(r), once=True
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

    def navigate(self, view: str) -> None:
        if view == "runs" and self.current_view.get("value") != "runs":
            self.runs_current_page = 1
        self.current_view["value"] = view
        for v, panel in self.all_panels.items():
            panel.set_visibility(v == view)
        self.page_title.text = _VIEW_LABELS.get(view, "Dashboard")
        self._highlight_nav(view)
        ui.timer(0, self.refresh_view, once=True)

    def _change_runs_page(self, delta: int) -> None:
        new_page = self.runs_current_page + delta
        if new_page < 1 or new_page > self.runs_total_pages:
            return
        self.runs_current_page = new_page
        ui.timer(0, self._load_runs, once=True)

    def _on_runs_select(self) -> None:
        self._selected_run_ids = [row["id"] for row in (self.runs_table.selected or [])]
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

    @staticmethod
    def _derive_run_status(
        result_statuses: list[tuple[str, str | None]],
        fallback: str = "",
    ) -> str:
        """Derive run status from associated goal evaluation statuses."""
        buckets = [_result_bucket(status=s, notes=n) for s, n in result_statuses]
        has_pending = any(b == "pending" for b in buckets)
        has_failed = any(b == "failed" for b in buckets)

        if has_pending:
            return "RUNNING"
        if has_failed:
            return "FAILED"
        if buckets:
            return "COMPLETED"
        return fallback or "PENDING"

    def _summarize_run_results(self, run_id: UUID) -> dict[str, object]:
        """Return per-run result counts and derived run status."""
        page = 1
        page_size = 100
        fetched = 0
        total = 0
        successful_jailbreaks = 0
        mitigations = 0
        statuses: list[tuple[str, str | None]] = []

        while True:
            rp = self.backend.list_results(
                run_id=run_id, page=page, page_size=page_size
            )
            if page == 1:
                total = int(rp.total or 0)
            if not rp.items:
                break

            for result in rp.items:
                bucket = _result_bucket(
                    result.evaluation_status, result.evaluation_notes
                )
                if bucket == "jailbreak":
                    successful_jailbreaks += 1
                elif bucket == "mitigated":
                    mitigations += 1
                statuses.append((result.evaluation_status, result.evaluation_notes))

            fetched += len(rp.items)
            if total > 0 and fetched >= total:
                break
            page += 1

        if total == 0:
            total = fetched

        return {
            "total_results": total,
            "successful_jailbreaks": successful_jailbreaks,
            "mitigations": mitigations,
            "failed_attacks": mitigations,
            "status": self._derive_run_status(statuses),
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
            display_type = str(metadata.get("display_type") or "").strip().lower()
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

        explanation = str(content.get("explanation") or "").lower()
        if not explanation and nested_result:
            explanation = str(nested_result.get("explanation") or "").lower()
        if "harmful" in explanation:
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
        if success is True:
            return True

        judge_score = content.get("judge_score")
        if judge_score is None:
            judge_score = content.get("score")
        if judge_score is None and nested_result:
            judge_score = nested_result.get("judge_score")
        if judge_score is None and nested_result:
            judge_score = nested_result.get("best_score")
        if judge_score is None and metadata:
            judge_score = metadata.get("judge_score")
        if judge_score is None and metadata:
            judge_score = metadata.get("best_score")
        if isinstance(judge_score, (int, float)) and judge_score > 0:
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
                    try:
                        if float(value) > 0:
                            return True
                    except (TypeError, ValueError):
                        continue

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
        fallback_request = None
        fallback_response = None

        # 1) Find request/response from any existing trace payload (goal/generation/tools/eval)
        for td in serialized_traces:
            req, resp = self._extract_request_response_candidates(td.get("content"))
            if fallback_request in (None, "") and req not in (None, ""):
                fallback_request = req
            if fallback_response in (None, "") and resp not in (None, ""):
                fallback_response = resp
            if fallback_request not in (None, "") and fallback_response not in (
                None,
                "",
            ):
                break

        # 2) Fall back to result-level metadata/payload
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

        # 3) Hard guarantee: keep blocks visible even when upstream payload is incomplete
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
            if content.get("request") in (None, ""):
                content["request"] = fallback_request
            if content.get("response") in (None, ""):
                content["response"] = fallback_response

        return serialized_traces

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
                ui.label(title).classes("text-xs text-grey-6")
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
        """Render trace content with a remote-dashboard-like schema."""
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

            # BoN and some remote evaluators place payloads under `result`.
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

            # Last fallback for remote records where request/response are inside metadata.
            if request_value in (None, ""):
                request_value = metadata.get("request") or metadata.get("prompt")
            if response_value in (None, ""):
                response_value = metadata.get("response") or metadata.get("answer")

            blocks = [
                ("Explanation", content.get("explanation")),
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

            for title, value in blocks:
                if value is None or value == "":
                    continue

                # For request payloads render only the prompt text (remote style).
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

            # Keep raw payload available but secondary, like remote details.
            with ui.expansion("View Raw JSON", icon="code").classes("w-full"):
                ui.code(json.dumps(content, indent=2), language="json").classes(
                    "w-full text-xs max-h-72 overflow-auto"
                )
            return

        if isinstance(content, list):
            ui.label(f"List content ({len(content)} items)").classes("text-sm")
            with ui.expansion("View Raw JSON", icon="code").classes("w-full"):
                ui.code(json.dumps(content, indent=2), language="json").classes(
                    "w-full text-xs max-h-72 overflow-auto"
                )
            return

        ui.label(str(content)).classes("text-sm whitespace-pre-wrap")

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
        agents_p = self.backend.list_agents(page=1, page_size=1)
        attacks_p = self.backend.list_attacks(page=1, page_size=1)
        runs_p = self.backend.list_runs(page=1, page_size=_DASHBOARD_RUN_SCAN_LIMIT)

        # ── Fast, accurate counts via backend aggregation ─────────────
        buckets = self.backend.count_result_buckets()
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
                                    "value": mitigated,
                                    "name": "Mitigated",
                                    "itemStyle": {"color": "#22c55e"},
                                },
                                {
                                    "value": failed,
                                    "name": "Failed",
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
                ("Failed", failed, "warning"),
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
            summary = self._summarize_run_results(run.id)
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
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
            d["_latency_s"] = self._compute_run_latency_seconds(d)
            d["_latency"] = _format_latency(d.get("_latency_s"))
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
            summary = self._summarize_run_results(run.id)
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
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
            d["_latency_s"] = self._compute_run_latency_seconds(d)
            d["_latency"] = _format_latency(d.get("_latency_s"))
            rows.append(d)
        self.runs_table.rows.clear()
        self.runs_table.rows.extend(rows)
        self.runs_table.update()
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

    async def _open_run_results(self, run: dict) -> None:
        run_id_raw = str(run.get("id") or "")
        self.run_dialog_title.text = f"Results — Run {run_id_raw[:8]}…"
        if self.run_dialog_subtitle is not None:
            status = str(run.get("status") or "—")
            agent = str(run.get("agent_name") or "—")
            attack = str(run.get("attack_type") or "—")
            created = str(run.get("_date") or run.get("created_at") or "—")
            run_latency_s = self._compute_run_latency_seconds(run)
            run_latency = _format_latency(run_latency_s)
            jailbreaks = int(run.get("successful_jailbreaks") or 0)
            failed_attacks = int(run.get("failed_attacks") or 0)
            self.run_dialog_subtitle.text = (
                f"Status: {status} | Agent: {agent} | Attack: {attack} | "
                f"Created: {created} | Total latency: {run_latency} | "
                f"Jailbreaks: {jailbreaks} | Failed attacks: {failed_attacks}"
            )
        if self.results_list_area is not None:
            self.results_list_area.clear()
        if self.results_empty_label is not None:
            self.results_empty_label.text = "Loading results…"
            self.results_empty_label.set_visibility(True)
        
        # ── Populate metrics tab ──────────────────────────────────────────
        if self.metrics_area is not None:
            self.metrics_area.clear()
            run_cfg = run.get("run_config") or {}
            eval_summary = run_cfg.get("evaluation_summary") if isinstance(run_cfg, dict) else None
            
            if isinstance(eval_summary, dict):
                with self.metrics_area:
                    ui.label("EVALUATION METRICS").classes(
                        "text-[10px] font-semibold tracking-widest text-grey-5 uppercase mt-1"
                    )
                    with ui.row().classes("flex-wrap gap-3 w-full"):
                        total = eval_summary.get("total_attacks", 0)
                        overall = eval_summary.get("overall_success_rate", 0.0)
                        mv_asr = eval_summary.get("majority_vote_asr", 0.0)
                        kappa = eval_summary.get("fleiss_kappa", None)
                        per_judge = eval_summary.get("per_judge_strictness") or {}

                        for label, value, color in [
                            ("Total Attacks", str(total), "grey-7"),
                            ("Overall ASR", f"{float(overall) * 100:.1f}%", "negative" if float(overall) > 0 else "positive"),
                            ("Majority-vote ASR", f"{float(mv_asr) * 100:.1f}%", "negative" if float(mv_asr) > 0 else "positive"),
                            *([("Fleiss' Kappa", f"{float(kappa):.3f}", "grey-7")] if kappa is not None else []),
                        ]:
                            with ui.card().classes("flex-none px-3 py-2"):
                                ui.label(label).classes("text-xs text-grey-6")
                                ui.badge(value, color=color).classes("text-sm font-semibold")

                        if per_judge:
                            with ui.column().classes("w-full gap-1 mt-1"):
                                ui.label("Per-Judge Strictness:").classes("text-xs text-grey-6")
                                with ui.row().classes("flex-wrap gap-2"):
                                    for judge_name, asr_val in per_judge.items():
                                        try:
                                            pct = f"{float(asr_val) * 100:.1f}%"
                                        except (TypeError, ValueError):
                                            pct = str(asr_val)
                                        ui.badge(
                                            f"{judge_name}: {pct}",
                                            color="grey-7",
                                        ).classes("text-xs")
            else:
                with self.metrics_area:
                    ui.label("No evaluation metrics available yet.").classes(
                        "text-sm text-grey-6 py-4"
                    )
        
        self.run_dialog.open()

        # Yield so NiceGUI flushes the dialog-open + "Loading…" state to the
        # browser before we start the (potentially slow) backend fetch.
        await asyncio.sleep(0)

        try:
            run_uuid = UUID(run_id_raw)

            # Fetch results in a thread so the event loop stays responsive
            # (RemoteBackend does synchronous HTTP calls).
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
                goal_index = d.get("goal_index")
                d["goal_number"] = (
                    int(goal_index) + 1 if isinstance(goal_index, int) else idx
                )
                d["evaluation_label"] = _eval_label(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["evaluation_notes"] = d.get("evaluation_notes") or "—"
                d["_goal_latency_s"] = self._extract_goal_latency_seconds(d)
                d["_goal_latency"] = _format_latency(d.get("_goal_latency_s"))
                new_rows.append(d)

            if self.results_list_area is not None:
                self.results_list_area.clear()

            if self.results_empty_label is not None:
                if all_items:
                    self.results_empty_label.set_visibility(False)
                else:
                    self.results_empty_label.text = "No results found for this run."
                    self.results_empty_label.set_visibility(True)

            if all_items and self.results_list_area is not None:
                with self.results_list_area:
                    for row in new_rows:
                        with ui.card().classes("w-full"):
                            with ui.row().classes(
                                "items-start justify-between w-full gap-2"
                            ):
                                ui.label(
                                    f"Goal #{row.get('goal_number', (row.get('goal_index', 0) or 0) + 1)}"
                                ).classes("font-semibold text-sm")
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge(
                                        row.get("evaluation_label") or "Pending",
                                        color=_eval_color(
                                            row.get("evaluation_status", ""),
                                            row.get("evaluation_notes"),
                                        ),
                                    ).classes("text-xs")
                                    ui.badge(
                                        f"Latency: {row.get('_goal_latency', '—')}",
                                        color="grey-7",
                                    ).classes("text-xs")

                            ui.label(str(row.get("goal") or "—")).classes(
                                "text-sm whitespace-pre-wrap"
                            )

                            notes = str(row.get("evaluation_notes") or "—")
                            ui.label(f"Notes: {notes}").classes(
                                "text-xs text-grey-6 whitespace-pre-wrap"
                            )

                            ui.button(
                                "Open details",
                                icon="open_in_new",
                                on_click=lambda r=row: ui.timer(
                                    0,
                                    lambda rr=r: asyncio.create_task(
                                        self.show_result_detail(rr, foreground=True)
                                    ),
                                    once=True,
                                ),
                            ).props("flat dense no-caps color=primary")
        except Exception as exc:
            if self.results_list_area is not None:
                self.results_list_area.clear()
            if self.results_empty_label is not None:
                self.results_empty_label.text = f"Failed to load results: {exc}"
                self.results_empty_label.set_visibility(True)
            ui.notify(f"Error loading results: {exc}", type="negative")
