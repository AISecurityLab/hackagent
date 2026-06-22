# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Generic and AutoDAN trace rendering.

Provides ``DashboardTraceRenderMixin`` for ``DashboardPage``. It turns the
classified traces from ``DashboardTraceAnalysisMixin`` into NiceGUI widgets.

Responsibilities:
    - The generic trace viewer: tab section, per-step value blocks, standard
      sections and guardrail-event blocks (``_render_trace_content``).
    - AutoDAN-specific rendering: role sections, per-step/epoch cards and the
      phase timeline.

The TAP attack has its own dedicated renderer in ``DashboardTapTraceMixin``.
"""

from __future__ import annotations

import contextlib
import html
import json
import re

from nicegui import ui


from ._helpers import (
    _rel_time,
)


class DashboardTraceRenderMixin:
    """Generic and AutoDAN trace rendering."""

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
            # FC-Attack: render flowchart image inline if present in metadata
            self._render_fc_trace_image(metadata)
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

    # ------------------------------------------------------------------
    # Indirect prompt injection (RAG) trace rendering
    # ------------------------------------------------------------------

    def _render_indirect_injection_poisoning_trace(self, content: dict) -> None:
        """Render poisoning preview as context-before + bold payload + context-after."""
        doc_id = str(content.get("document_id") or "unknown")
        insert_idx = content.get("insertion_paragraph_index", "?")
        context_before = str(
            content.get("preview_before_tail") or content.get("context_before") or ""
        )
        payload = str(content.get("injected_payload") or "").strip()
        context_after = str(
            content.get("preview_after_head") or content.get("context_after") or ""
        )

        has_before = bool(content.get("preview_has_before")) or bool(context_before)
        has_after = bool(content.get("preview_has_after")) or bool(context_after)

        preview_html = ""
        if has_before:
            preview_html += "[...]"
        preview_html += html.escape(context_before)
        preview_html += f" <strong>{html.escape(payload)}</strong> "
        preview_html += html.escape(context_after)
        if has_after:
            preview_html += "[...]"

        with (
            ui.card()
            .tight()
            .classes(
                "w-full border border-orange-200 bg-orange-50/40 "
                "dark:border-orange-700 dark:bg-orange-900/10"
            )
        ):
            with ui.column().classes("p-4 gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"Document: {doc_id}").classes("text-sm font-semibold")
                    ui.badge(f"Paragraph #{insert_idx}", color="warning").classes(
                        "text-xs"
                    )
                    ui.badge("Insertion Only", color="grey-7").classes("text-xs")
                ui.html(
                    "<div style='white-space: pre-wrap; line-height: 1.55'>"
                    f"{preview_html}"
                    "</div>"
                ).classes("text-sm")
                ui.label(
                    "The payload is inserted between text snippets. Original text is preserved."
                ).classes("text-xs text-grey-6")

    @staticmethod
    def _is_indirect_injection_trace_set(traces: list[dict]) -> bool:
        """Return True when traces belong to indirect prompt injection flow."""
        for trace_data in traces:
            content = trace_data.get("content")
            if not isinstance(content, dict):
                continue

            step_name = str(content.get("step_name") or "").strip().lower()
            if step_name == "document poisoning" or step_name.startswith("rag query"):
                return True

            attack_type = str(content.get("attack_type") or "").strip().lower()
            if attack_type == "rag":
                return True

            evaluator = str(content.get("evaluator") or "").strip().lower()
            if evaluator == "rag_judge":
                return True

        return False

    @staticmethod
    def _collect_indirect_injection_trace_data(
        traces: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Extract poisoning previews and query/evaluation panels from traces."""

        def _to_int(value: object, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        poisoning_traces: list[dict] = []
        query_map: dict[int, dict] = {}
        next_index = 1

        ordered = sorted(
            traces,
            key=lambda item: _to_int(item.get("sequence"), 0),
        )

        for trace_data in ordered:
            content = trace_data.get("content")
            if not isinstance(content, dict):
                continue

            step_name = str(content.get("step_name") or "").strip()
            step_lower = step_name.lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )

            if step_lower == "document poisoning" and content.get("injected_payload"):
                poisoning_traces.append(content)
                continue

            if step_lower.startswith("rag query"):
                query_index = _to_int(metadata.get("query_index"), 0)
                if query_index <= 0:
                    match = re.search(r"#(\d+)", step_name)
                    query_index = _to_int(match.group(1), 0) if match else 0
                if query_index <= 0:
                    query_index = next_index

                entry = query_map.setdefault(
                    query_index,
                    {
                        "query_index": query_index,
                        "query": "",
                        "response": "",
                        "classification": "INCONCLUSIVE",
                        "rationale": "",
                        "poisonings": [],
                    },
                )

                request_data = content.get("request")
                if isinstance(request_data, dict):
                    entry["query"] = str(
                        request_data.get("prompt")
                        or request_data.get("query")
                        or entry["query"]
                    )
                elif isinstance(request_data, str) and request_data.strip():
                    entry["query"] = request_data

                response_data = content.get("response")
                if isinstance(response_data, dict):
                    entry["response"] = str(
                        response_data.get("content")
                        or response_data.get("response")
                        or response_data.get("target_response")
                        or entry["response"]
                    )
                elif isinstance(response_data, str) and response_data.strip():
                    entry["response"] = response_data

                next_index = max(next_index, query_index + 1)
                continue

            if step_lower.startswith("evaluation") or step_lower == "evaluation":
                result_data = (
                    content.get("result")
                    if isinstance(content.get("result"), dict)
                    else {}
                )

                query_index = _to_int(metadata.get("query_index"), 0)
                if query_index <= 0:
                    query_index = _to_int(result_data.get("query_index"), 0)
                if query_index <= 0:
                    query_index = next_index

                entry = query_map.setdefault(
                    query_index,
                    {
                        "query_index": query_index,
                        "query": "",
                        "response": "",
                        "classification": "INCONCLUSIVE",
                        "rationale": "",
                        "poisonings": [],
                    },
                )

                metadata_query = metadata.get("query")
                if (
                    isinstance(metadata_query, str)
                    and metadata_query.strip()
                    and not entry["query"]
                ):
                    entry["query"] = metadata_query

                classification = (
                    metadata.get("classification")
                    or result_data.get("classification")
                    or content.get("classification")
                    or entry["classification"]
                )
                entry["classification"] = str(classification or "INCONCLUSIVE").upper()

                rationale = (
                    result_data.get("rationale")
                    or content.get("explanation")
                    or content.get("rationale")
                    or entry["rationale"]
                )
                entry["rationale"] = str(rationale or "").strip()

                next_index = max(next_index, query_index + 1)

        query_panels = [query_map[idx] for idx in sorted(query_map.keys())]

        query_lookup: dict[str, list[dict]] = {}
        for panel in query_panels:
            normalized_query = str(panel.get("query") or "").strip().lower()
            if not normalized_query:
                continue
            query_lookup.setdefault(normalized_query, []).append(panel)

        for poisoning in poisoning_traces:
            query_anchor = str(poisoning.get("query_anchor") or "").strip().lower()
            if query_anchor and query_anchor in query_lookup:
                for panel in query_lookup[query_anchor]:
                    panel.setdefault("poisonings", []).append(poisoning)
                continue

            # Fallback for older traces where query_anchor is not available.
            if len(query_panels) == 1:
                query_panels[0].setdefault("poisonings", []).append(poisoning)

        return poisoning_traces, query_panels

    @staticmethod
    def _indirect_query_verdict_style(
        classification: str,
    ) -> tuple[str, str, str]:
        """Map judge classification to UI label and response card style."""
        cls = str(classification or "INCONCLUSIVE").upper()
        if cls == "SUCCESS":
            return (
                "HARMFUL",
                "negative",
                "w-full border border-red-200 border-l-4 border-l-red-500 "
                "bg-red-50 dark:border-red-700 dark:bg-red-900/20 rounded-lg shadow-sm",
            )
        if cls == "FAILURE":
            return (
                "SAFE",
                "positive",
                "w-full border border-green-200 border-l-4 border-l-green-500 "
                "bg-green-50 dark:border-green-700 dark:bg-green-900/20 rounded-lg shadow-sm",
            )
        return (
            "INCONCLUSIVE",
            "warning",
            "w-full border border-yellow-200 border-l-4 border-l-yellow-500 "
            "bg-yellow-50 dark:border-yellow-700 dark:bg-yellow-900/20 rounded-lg shadow-sm",
        )

    def _render_indirect_injection_query_panel(self, panel: dict) -> None:
        """Render a single expandable query panel with query/response/judge blocks."""
        query_index = panel.get("query_index", "?")
        query_text = str(panel.get("query") or "(query not available)")
        response_text = str(panel.get("response") or "(response not available)")
        classification = str(panel.get("classification") or "INCONCLUSIVE").upper()
        rationale = str(panel.get("rationale") or "No rationale available")
        poisonings = (
            panel.get("poisonings") if isinstance(panel.get("poisonings"), list) else []
        )

        verdict_label, verdict_color, response_card_classes = (
            self._indirect_query_verdict_style(classification)
        )

        header_preview = (
            query_text if len(query_text) <= 80 else f"{query_text[:80]}..."
        )

        with (
            ui.card()
            .tight()
            .classes("w-full border border-grey-3 rounded-xl shadow-sm overflow-hidden")
        ):
            with ui.expansion(f"Query {query_index}", icon="quiz").classes("w-full"):
                with ui.column().classes("w-full gap-3 p-3"):
                    ui.label(header_preview).classes("text-sm text-grey-7 -mt-1")

                    with ui.expansion(
                        f"Poisoned Paragraphs ({len(poisonings)})",
                        icon="splitscreen",
                    ).classes("w-full"):
                        with ui.column().classes("w-full gap-2 p-2"):
                            if poisonings:
                                for idx, poisoning in enumerate(poisonings, start=1):
                                    paragraph_idx = poisoning.get(
                                        "insertion_paragraph_index", "?"
                                    )
                                    with ui.expansion(
                                        f"Poisoning #{idx} - Paragraph #{paragraph_idx}",
                                        icon="expand_more",
                                    ).classes("w-full"):
                                        with ui.column().classes("w-full gap-2 p-2"):
                                            self._render_indirect_injection_poisoning_trace(
                                                poisoning
                                            )
                            else:
                                ui.label(
                                    "No poisoning panel mapped to this query."
                                ).classes("text-sm text-grey-6")

                    with (
                        ui.card()
                        .tight()
                        .classes(
                            "w-full border border-grey-3 rounded-lg bg-grey-1/40 dark:bg-grey-9/20"
                        )
                    ):
                        with ui.column().classes("p-3 gap-1"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("manage_search", size="xs", color="grey-7")
                                ui.label("Generated Query").classes(
                                    "text-xs font-semibold text-grey-6 uppercase"
                                )
                            ui.label(query_text).classes("text-sm whitespace-pre-wrap")

                    with ui.card().tight().classes(response_card_classes):
                        with ui.column().classes("p-3 gap-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("smart_toy", size="xs", color="grey-7")
                                ui.label("Target Response").classes(
                                    "text-xs font-semibold uppercase"
                                )
                                ui.badge(verdict_label, color=verdict_color).classes(
                                    "text-xs"
                                )
                            ui.label(response_text).classes(
                                "text-sm whitespace-pre-wrap"
                            )

                    with (
                        ui.card()
                        .tight()
                        .classes(
                            "w-full border border-grey-3 rounded-lg bg-white dark:bg-grey-10 shadow-sm"
                        )
                    ):
                        with ui.column().classes("p-3 gap-1"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("gavel", size="xs", color="grey-7")
                                ui.label("Judge Assessment").classes(
                                    "text-xs font-semibold text-grey-6 uppercase"
                                )
                            ui.label(
                                f"Verdict: {verdict_label} ({classification})"
                            ).classes("text-sm font-medium")
                            ui.label(rationale).classes("text-sm whitespace-pre-wrap")

    def _render_indirect_injection_view(self, row: dict, traces: list[dict]) -> None:
        """Render only goal, poisoning preview, and query panels for indirect injection."""
        _, query_panels = self._collect_indirect_injection_trace_data(traces)

        goal_text = str(row.get("goal") or "Goal not available")

        with ui.column().classes("w-full gap-5"):
            with ui.card().tight().classes("w-full border border-grey-3"):
                with ui.column().classes("p-4 gap-1"):
                    ui.label("Goal").classes(
                        "text-xs font-semibold text-grey-6 uppercase"
                    )
                    ui.label(goal_text).classes("text-sm whitespace-pre-wrap")

            with ui.column().classes("w-full gap-2"):
                ui.label("Generated Queries").classes(
                    "text-xs font-semibold text-grey-6 uppercase"
                )
                if query_panels:
                    for panel in query_panels:
                        self._render_indirect_injection_query_panel(panel)
                else:
                    with ui.card().tight().classes("w-full border border-grey-3"):
                        ui.label("No queries available.").classes(
                            "text-sm text-grey-6 p-3"
                        )
