# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Runs selection, comparison, export and deletion.

Provides ``DashboardRunsMixin`` for ``DashboardPage``. It handles the actions a
user can take on the History runs table once one or more runs are selected.

Responsibilities:
    - Track table selection (``_on_runs_table_select`` / ``_on_runs_select``).
    - Delete and export the selected runs (``_build_export_data`` serialises
      runs + results for download).
    - Build the side-by-side comparison panel (``_compare_selected_runs``)
      including its charts, and export an ECharts figure to SVG.

The comparison view reuses summary/metrics helpers from
``DashboardAnalysisDataMixin``.
"""

from __future__ import annotations

from collections import defaultdict
import contextlib
import json
from uuid import UUID

from nicegui import ui


from ._helpers import (
    _result_bucket,
    _serialize,
)


class DashboardRunsMixin:
    """Runs selection, comparison, export and deletion."""

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
                    "fc": "FC-Attack",
                    "tfc": "tFC-Attack",
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
                    ).classes("w-full").props("dense flat bordered")

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
