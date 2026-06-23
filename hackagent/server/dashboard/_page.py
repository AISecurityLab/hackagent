# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DashboardPage — composition root for the NiceGUI dashboard page.

This module defines ``DashboardPage``, the single class instantiated per
browser connection inside the ``@ui.page("/")`` handler. The class itself is
deliberately thin: it holds all per-request widget state in ``__init__`` and
the top-level ``build`` flow, while the actual behaviour is contributed by a
stack of focused mixins (split out of what used to be one ~9.8k-line file).

Mixin layers, roughly in dependency order:
    - attack_cards.* — per-attack card parsing/rendering.
    - DashboardLayoutMixin — page skeleton, panels, navigation, theme.
    - DashboardDataMixin — loading agents/attacks/runs/dashboard data.
    - DashboardReportsMixin — History/Reports views and goal rows.
    - DashboardResultDetailMixin — single-result detail tabs.
    - DashboardRunsMixin — run selection, compare, export, delete.
    - DashboardAnalysisDataMixin — widget-free aggregation and metrics.
    - DashboardTraceAnalysisMixin — trace classification/synthesis.
    - DashboardTraceRenderMixin / DashboardTapTraceMixin — trace rendering.
    - DashboardRunResultsMixin / DashboardRunHistoryResultsMixin — full
      per-run results analysis views.

All mixins operate on the same live instance and share the attributes created
here, so adding a method to any mixin makes it available as ``self.<method>``.
"""

from __future__ import annotations


from nicegui import app as _fastapi_app
from nicegui import ui


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
    FCCardMixin,
    tFCCardMixin,
)


from ._layout_mixin import DashboardLayoutMixin
from ._reports_mixin import DashboardReportsMixin
from ._result_detail_mixin import DashboardResultDetailMixin
from ._data_mixin import DashboardDataMixin
from ._runs_mixin import DashboardRunsMixin
from ._analysis_data_mixin import DashboardAnalysisDataMixin
from ._trace_analysis_mixin import DashboardTraceAnalysisMixin
from ._trace_render_mixin import DashboardTraceRenderMixin
from ._tap_trace_mixin import DashboardTapTraceMixin
from ._run_results_mixin import DashboardRunResultsMixin
from ._run_history_results_mixin import DashboardRunHistoryResultsMixin


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
    FCCardMixin,
    tFCCardMixin,
    DashboardLayoutMixin,
    DashboardReportsMixin,
    DashboardResultDetailMixin,
    DashboardDataMixin,
    DashboardRunsMixin,
    DashboardAnalysisDataMixin,
    DashboardTraceAnalysisMixin,
    DashboardTraceRenderMixin,
    DashboardTapTraceMixin,
    DashboardRunResultsMixin,
    DashboardRunHistoryResultsMixin,
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
