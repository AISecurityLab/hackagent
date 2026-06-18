# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Result detail dialog rendering (result/config/MML tabs).

Provides ``DashboardResultDetailMixin`` for ``DashboardPage``. It renders the
detail view for a single result (the right drawer / modal opened from a goal
row), splitting it into tabs:

    - Result tab: prompt/response, evaluation verdict and metadata.
    - Config tab: the attack/run configuration that produced the result.
    - MML section: extra rendering specific to the MML attack family.

It also resolves a run's ASR for display and lazily loads the trace records
for a goal. Trace *rendering* itself is delegated to the trace-render and
TAP mixins.
"""

from __future__ import annotations

import contextlib
import json
from uuid import UUID

from nicegui import ui


from ._helpers import (
    _eval_color,
    _eval_label,
    _result_bucket,
    _serialize,
)


class DashboardResultDetailMixin:
    """Result detail dialog rendering (result/config/MML tabs)."""

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

                if self._is_indirect_injection_trace_set(serialized_traces):
                    self._render_indirect_injection_view(row, serialized_traces)
                else:
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
                    elif self._is_indirect_injection_trace_set(serialized_traces):
                        self._render_indirect_injection_view(result, serialized_traces)
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
