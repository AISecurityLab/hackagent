# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DashboardPage — all NiceGUI UI layout and data-loading logic."""

from __future__ import annotations

import contextlib
import json
import math
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
        self.runs_selected_label: ui.label | None = None
        self.runs_current_page: int = 1
        self.runs_total_pages: int = 1
        self.runs_selected_ids: set[str] = set()

        self.attacks_selected_label: ui.label | None = None
        self.attacks_selected_ids: set[str] = set()

        # Run results dialog
        self.run_dialog: ui.dialog | None = None
        self.run_dialog_title: ui.label | None = None
        self.results_table: ui.table | None = None
        self.results_empty_label: ui.label | None = None

        # Attack detail dialog
        self.attack_dialog: ui.dialog | None = None
        self.attack_dialog_title: ui.label | None = None
        self.attack_config_area: ui.column | None = None
        self.attack_runs_table: ui.table | None = None

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
        with ui.left_drawer(top_corner=True, bottom_corner=True).props(
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
                    ),
                    include_agent=False,
                    include_progressive_run=False,
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
                    self.attacks_selected_label = ui.label("0 selected").classes(
                        "text-sm text-grey-6"
                    )
                    ui.button(
                        "Delete selected",
                        on_click=lambda: ui.timer(0, self._delete_selected_attacks, once=True),
                    ).props("unelevated color=negative no-caps dense")

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
                    selection="multiple",
                    on_select=self._on_attacks_select,
                    pagination={"rowsPerPage": 25},
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

    def _build_runs_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center justify-between mb-1 px-2"):
                    self.runs_count_label = ui.label("").classes("text-sm text-grey-6")
                    with ui.row().classes("items-center gap-2"):
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
                        0, lambda r=run: self._open_run_results(r), once=True
                    ),
                    pagination={"rowsPerPage": 25},
                    include_agent=True,
                    include_progressive_run=True,
                    include_results=False,
                    selection="multiple",
                    on_select=self._on_runs_select,
                )
                self.runs_table.props("hide-pagination")
                with ui.row().classes("items-center justify-between mt-2 px-2"):
                    self.runs_selected_label = ui.label("0 selected").classes(
                        "text-sm text-grey-6"
                    )
                    ui.button(
                        "Delete selected",
                        on_click=lambda: ui.timer(0, self._delete_selected_runs, once=True),
                    ).props("unelevated color=negative no-caps dense")

    def _build_run_dialog(self) -> None:
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-5xl h-[80vh] flex flex-col gap-4"):
                with ui.row().classes("items-center justify-between w-full shrink-0"):
                    self.run_dialog_title = ui.label("Run Results").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                self.results_empty_label = ui.label("Loading results...").classes(
                    "text-sm text-grey-6 px-1"
                )

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
                                                {{ props.row.goal_number ?? ((props.row.goal_index ?? 0) + 1) }}
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

                def _on_result_row_click(e) -> None:
                    row = self._extract_row(e.args)
                    if row is not None:
                        ui.timer(
                            0,
                            lambda r=row: self.show_result_detail(
                                r, foreground=True
                            ),
                            once=True,
                        )

                self.results_table.on("rowClick", _on_result_row_click)
        self.run_dialog = dialog

    def _build_attack_dialog(self) -> None:
        with ui.dialog() as dialog:
            with ui.card().classes("w-full max-w-4xl h-[80vh] flex flex-col gap-4"):
                with ui.row().classes("items-center justify-between w-full shrink-0"):
                    self.attack_dialog_title = ui.label("Attack Detail").classes(
                        "font-semibold text-lg"
                    )
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                self.attack_config_area = ui.column().classes("w-full gap-4 flex-1 overflow-auto")

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
                            ui.label(lbl).classes("text-xs text-grey-6 uppercase font-semibold")
                        ui.label(str(val)).classes("text-sm font-mono select-all break-all")

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
                        rp = self.backend.list_results(
                            run_id=run.id, page=1, page_size=_RESULTS_FETCH_LIMIT
                        )
                        d["total_results"] = rp.total
                        d["successful_jailbreaks"] = sum(
                            1
                            for r in rp.items
                            if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
                        )
                        d["status"] = self._derive_run_status(
                            [(r.evaluation_status, r.evaluation_notes) for r in rp.items],
                            fallback=str(d.get("status", "")),
                        )
                        status = d.get("status", "")
                        status_color = (
                            "positive" if status == "COMPLETED"
                            else "info" if status == "RUNNING"
                            else "negative" if status == "FAILED"
                            else "warning"
                        )
                        with ui.card().classes(
                            "w-full cursor-pointer hover:shadow-md"
                        ).on(
                            "click",
                            lambda _e, r=d: (
                                self.attack_dialog.close(),
                                ui.timer(0, lambda: self._open_run_results(r), once=True),
                            ),
                        ):
                            with ui.row().classes("items-center justify-between w-full"):
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(str(d["id"])[:8] + "…").classes(
                                        "font-mono text-xs font-medium"
                                    )
                                    ui.badge(status, color=status_color).classes("text-xs")
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(
                                        f"{d['total_results']} results"
                                    ).classes("text-xs text-grey-6")
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
        self.runs_selected_ids.clear()
        ui.timer(0, self._load_runs, once=True)

    def _on_runs_select(self, e) -> None:
        self.runs_selected_ids = {
            str(item.get("id"))
            for item in (e.selection or [])
            if isinstance(item, dict) and item.get("id")
        }
        if self.runs_selected_label is not None:
            n = len(self.runs_selected_ids)
            self.runs_selected_label.text = f"{n} selected"

    def _on_attacks_select(self, e) -> None:
        self.attacks_selected_ids = {
            str(item.get("id"))
            for item in (e.selection or [])
            if isinstance(item, dict) and item.get("id")
        }
        if self.attacks_selected_label is not None:
            n = len(self.attacks_selected_ids)
            self.attacks_selected_label.text = f"{n} selected"

    async def _delete_selected_runs(self) -> None:
        ids = list(self.runs_selected_ids)
        if not ids:
            ui.notify("No runs selected.", type="warning")
            return

        self.loading_spinner.set_visibility(True)
        deleted = 0
        failed = 0
        try:
            for raw in ids:
                try:
                    self.backend.delete_run(UUID(str(raw)))
                    deleted += 1
                except Exception:
                    failed += 1

            self.runs_selected_ids.clear()
            if self.runs_selected_label is not None:
                self.runs_selected_label.text = "0 selected"
            await self._load_runs()
            await self._load_dashboard()
            if failed:
                ui.notify(f"Deleted {deleted} runs, failed {failed}.", type="warning")
            else:
                ui.notify(f"Deleted {deleted} runs.", type="positive")
        finally:
            self.loading_spinner.set_visibility(False)

    async def _delete_selected_attacks(self) -> None:
        ids = list(self.attacks_selected_ids)
        if not ids:
            ui.notify("No attacks selected.", type="warning")
            return

        self.loading_spinner.set_visibility(True)
        deleted = 0
        failed = 0
        try:
            for raw in ids:
                try:
                    self.backend.delete_attack(UUID(str(raw)))
                    deleted += 1
                except Exception:
                    failed += 1

            self.attacks_selected_ids.clear()
            if self.attacks_selected_label is not None:
                self.attacks_selected_label.text = "0 selected"
            await self._load_attacks()
            await self._load_runs()
            await self._load_dashboard()
            if failed:
                ui.notify(
                    f"Deleted {deleted} attacks, failed {failed}.",
                    type="warning",
                )
            else:
                ui.notify(f"Deleted {deleted} attacks.", type="positive")
        finally:
            self.loading_spinner.set_visibility(False)

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
            if "goal" in content and "request" not in content and "response" not in content:
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

        explanation = str(content.get("explanation") or "").lower()
        if "harmful" in explanation:
            return True

        success = content.get("success")
        if success is True:
            return True

        judge_score = content.get("judge_score")
        if isinstance(judge_score, (int, float)) and judge_score > 0:
            return True

        return False

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
            with ui.tabs().props("dense align=left no-caps inline-label").classes(
                "w-full"
            ) as tabs:
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
                                    self._render_trace_content(step.get("step_type"), content)

    def _render_trace_content(self, step_type: str | None, content: object) -> None:
        """Render trace content with a remote-dashboard-like schema."""
        st = (step_type or "").upper()

        if isinstance(content, dict):
            # -----------------------------------------------------------------
            # TAP Goals block
            # -----------------------------------------------------------------
            goal = content.get("goal")
            if isinstance(goal, str) and goal.strip():
                with ui.card().tight().classes("w-full border border-red-200 bg-red-50"):
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
            metadata = content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
            request_value = content.get("request")
            response_value = content.get("response")

            # In many evaluation traces, prompt/completion are stored as
            # prefix/completion (sometimes inside metadata). Surface them
            # directly so they are visible without expanding metadata.
            if request_value in (None, ""):
                request_value = content.get("prefix")
            if response_value in (None, ""):
                response_value = content.get("completion")
            if request_value in (None, ""):
                request_value = metadata.get("prefix")
            if response_value in (None, ""):
                response_value = metadata.get("completion")

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
                        branch_idx = metadata.get("branch_index", content.get("branch_index"))
                        stream_idx = metadata.get("stream_index", content.get("stream_index"))
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
                detail_title.text = (
                    f"Result · #{result_num}"
                )

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
                    ui.label(f"Goal #{result_num}").classes(
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

        self.result_modal_dialog.open()

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
                    grouped: dict[str, list[dict]] = {
                        "goal": [],
                        "evaluation": [],
                        "generation": [],
                        "tools": [],
                        "other": [],
                    }

                    for trace in traces_raw:
                        td = _serialize(trace)
                        group, label = self._classify_trace_step(td)
                        td["_display_label"] = label
                        grouped[group].append(td)

                    self._render_trace_tabs_section(
                        "Goal", grouped["goal"], "goal"
                    )
                    self._render_trace_tabs_section(
                        "Evaluation", grouped["evaluation"], "evaluation"
                    )
                    self._render_trace_tabs_section(
                        "Attack / Generation",
                        grouped["generation"],
                        "generation",
                    )
                    self._render_trace_tabs_section(
                        "Tools", grouped["tools"], "tools"
                    )
                    self._render_trace_tabs_section(
                        "Other", grouped["other"], "other"
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
        runs_p = self.backend.list_runs(page=1, page_size=_DASHBOARD_RUN_SCAN_LIMIT)
        run_attack_ids = {str(run.attack_id) for run in runs_p.items}
        run_agent_ids = {str(run.agent_id) for run in runs_p.items}
        attack_type_by_id = self._attack_type_map_for_ids(run_attack_ids)
        agent_name_by_id = self._agent_name_map_for_ids(run_agent_ids)
        total_results = jailbreaks = mitigated = failed = pending = 0
        for run in runs_p.items:
            rp = self.backend.list_results(
                run_id=run.id, page=1, page_size=_RESULTS_FETCH_LIMIT
            )
            total_results += rp.total
            for r in rp.items:
                bucket = _result_bucket(r.evaluation_status, r.evaluation_notes)
                if bucket == "jailbreak":
                    jailbreaks += 1
                elif bucket == "mitigated":
                    mitigated += 1
                elif bucket == "failed":
                    failed += 1
                elif bucket == "pending":
                    pending += 1

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
        rows = []
        for run in recent_p.items:
            d = _serialize(run)
            rp = self.backend.list_results(
                run_id=run.id, page=1, page_size=_RESULTS_FETCH_LIMIT
            )
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if _result_bucket(r.evaluation_status, r.evaluation_notes) == "jailbreak"
            )
            d["status"] = self._derive_run_status(
                [(r.evaluation_status, r.evaluation_notes) for r in rp.items],
                fallback=str(d.get("status", "")),
            )
            d["attack_type"] = attack_type_by_id.get(str(d.get("attack_id")), "—")
            d["agent_name"] = agent_name_by_id.get(str(d.get("agent_id")), "—")
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
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
        agent_ids = {str(a.agent_id) for a in result.items}
        agent_name_by_id = self._agent_name_map_for_ids(agent_ids)
        rows = []
        for a in result.items:
            d = _serialize(a)
            agent_id = str(d.get("agent_id") or "")
            d["agent_name"] = agent_name_by_id.get(
                agent_id,
                f"{agent_id[:8]}…" if agent_id else "—",
            )
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
            rows.append(d)
        self.attacks_table.rows.clear()
        self.attacks_table.rows.extend(rows)
        self.attacks_table.update()
        self.attacks_table.set_selection([])

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
            # Keep History lightweight: status and metadata come from RunRecord;
            # detailed goal/result aggregates are loaded only when opening a run.
            d["status"] = str(d.get("status", "") or "PENDING")
            attack_id = str(d.get("attack_id") or "")
            agent_id = str(d.get("agent_id") or "")
            run_cfg = d.get("run_config") if isinstance(d.get("run_config"), dict) else {}
            d["attack_type"] = attack_type_by_id.get(
                attack_id,
                str(run_cfg.get("attack_type") or (f"{attack_id[:8]}…" if attack_id else "—")),
            )
            d["agent_name"] = agent_name_by_id.get(
                agent_id,
                str(run_cfg.get("_agent_name") or (f"{agent_id[:8]}…" if agent_id else "—")),
            )
            d["run_progress"] = max(
                1,
                result.total
                - ((self.runs_current_page - 1) * _RUNS_VIEW_PAGE_SIZE + idx),
            )
            d["_rel"] = _rel_time(d.get("created_at"))
            d["_date"] = _short_date(d.get("created_at"))
            rows.append(d)
        self.runs_table.rows.clear()
        self.runs_table.rows.extend(rows)
        self.runs_table.update()
        self.runs_table.set_selection([])
        start = (self.runs_current_page - 1) * _RUNS_VIEW_PAGE_SIZE + 1 if result.total else 0
        end = start + len(rows) - 1 if rows else 0
        self.runs_count_label.text = (
            f"Showing {start}-{end} of {result.total} run{'s' if result.total != 1 else ''}"
        )
        if self.runs_page_label is not None:
            self.runs_page_label.text = (
                f"Page {self.runs_current_page} / {self.runs_total_pages}"
            )

    async def _open_run_results(self, run: dict) -> None:
        self.run_dialog_title.text = f"Results — Run {run['id'][:8]}…"
        self.results_table.rows.clear()
        self.results_table.update()
        if self.results_empty_label is not None:
            self.results_empty_label.text = "Loading results..."
        self.run_dialog.open()
        try:
            run_id_raw = str(run.get("id") or "")
            run_uuid = UUID(run_id_raw)
            page = 1
            page_size = 200
            all_items = []
            while True:
                rp = self.backend.list_results(run_id=run_uuid, page=page, page_size=page_size)
                if not rp.items:
                    break
                all_items.extend(rp.items)
                if len(all_items) >= rp.total:
                    break
                if len(rp.items) < page_size:
                    break
                page += 1

            for idx, r in enumerate(all_items, start=1):
                d = _serialize(r)
                d["_rel"] = _rel_time(d.get("created_at"))
                d["goal_number"] = idx
                self.results_table.rows.append(d)
            self.results_table.update()
            if self.results_empty_label is not None:
                if all_items:
                    self.results_empty_label.text = ""
                else:
                    self.results_empty_label.text = "No results found for this run."
        except Exception as exc:
            if self.results_empty_label is not None:
                self.results_empty_label.text = "Failed to load results for this run."
            ui.notify(f"Error loading results: {exc}", type="negative")
