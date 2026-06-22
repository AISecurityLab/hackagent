# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run results analysis view (_open_run_results).

Provides ``DashboardRunResultsMixin`` for ``DashboardPage``. It builds the full
analysis view shown when a user opens a single (current) run from the runs
table.

The mixin is intentionally just the one large ``_open_run_results`` coroutine
plus its inner helpers (risk-score, robustness and category-distribution
charts). It is kept in its own module because the method is sizable and
closure-heavy; the inner builders capture local view state and are not reused
elsewhere.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
import json
from uuid import UUID

from nicegui import ui

from hackagent.attacks.evaluator.metrics import (
    calculate_fleiss_kappa,
    calculate_majority_vote_asr,
    calculate_per_judge_asr,
    calculate_per_judge_strictness,
)

from ._helpers import (
    _eval_color,
    _eval_label,
    _format_latency,
    _rel_time,
    _result_bucket,
    _serialize,
    _short_date,
)


class DashboardRunResultsMixin:
    """Run results analysis view (_open_run_results)."""

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
