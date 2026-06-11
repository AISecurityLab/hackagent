# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AutoDAN-Turbo attack card rendering."""

from __future__ import annotations

import html
import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class AutodanCardMixin:
    """Mixin providing AutoDAN-Turbo attack card parse + render."""

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
            metadata = content.get("metadata") or {}

            phase_raw = str(content.get("phase") or "").upper()
            subphase_raw = str(content.get("subphase") or "").upper()
            if not phase_raw:
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

            if subphase_raw in ("PHASE_START", "PHASE_END", "SKIP_FINALIZED"):
                continue

            phase = phase_raw if phase_raw in ("WARMUP", "LIFELONG") else "LIFELONG"
            iteration = int(content.get("iteration") or metadata.get("iteration") or 0)
            epoch = int(content.get("epoch") or metadata.get("epoch") or 0)
            stream = int(content.get("stream") or metadata.get("stream") or 0)
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

            if content.get("generated_prompt"):
                step["generated_prompt"] = str(content["generated_prompt"])
            else:
                req = content.get("request") or {}
                if isinstance(req, dict) and req.get("prompt"):
                    step["generated_prompt"] = req["prompt"]

            raw_resp = content.get("target_response") or content.get("response")
            if raw_resp:
                (
                    raw_resp,
                    _adan_g_side,
                    _adan_g_expl,
                    _adan_g_cats,
                ) = AttackCardSharedMixin._extract_guardrail_from_response(raw_resp)
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
                            _summary_steps = [
                                s for s in phase_steps if s["phase"] == "WARMUP_SUMMARY"
                            ]
                            _iter_steps = [
                                s for s in phase_steps if s["phase"] != "WARMUP_SUMMARY"
                            ]

                            _iter_groups: list[tuple[int, list[dict]]] = []
                            for _step in _iter_steps:
                                _it = _step.get("iteration", 0)
                                if not _iter_groups or _iter_groups[-1][0] != _it:
                                    _iter_groups.append((_it, []))
                                _iter_groups[-1][1].append(_step)

                            for _iter_num, _epoch_steps in _iter_groups:
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
                                            with ui.row().classes(
                                                "w-full items-center justify-between"
                                            ):
                                                ui.label("Attacker").classes(
                                                    "text-[10px] font-semibold text-grey-5 uppercase tracking-wide"
                                                )
                                                ui.button(icon="content_copy").props(
                                                    "flat dense size=xs color=grey-6"
                                                ).tooltip("Copy to clipboard").on(
                                                    "click",
                                                    js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(generated_prompt or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                                                )
                                            ui.html(
                                                '<pre style="font-size:11px;padding:8px;background:white;'
                                                "border:1px solid #e0e0e0;border-radius:4px;margin:0;"
                                                'white-space:pre-wrap;word-break:break-word">'
                                                + html.escape(
                                                    generated_prompt or "\u2014"
                                                )
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
                                                with ui.row().classes(
                                                    "w-full items-center justify-between"
                                                ):
                                                    ui.label("Target response").classes(
                                                        "text-[10px] font-semibold text-grey-5 uppercase tracking-wide"
                                                    )
                                                    ui.button(
                                                        icon="content_copy"
                                                    ).props(
                                                        "flat dense size=xs color=grey-6"
                                                    ).tooltip(
                                                        "Copy to clipboard"
                                                    ).on(
                                                        "click",
                                                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(target_response or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
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
                                                with ui.row().classes(
                                                    "w-full items-center justify-between"
                                                ):
                                                    ui.label(
                                                        "Scorer assessment"
                                                    ).classes(
                                                        "text-[10px] font-semibold text-grey-5 uppercase tracking-wide"
                                                    )
                                                    ui.button(
                                                        icon="content_copy"
                                                    ).props(
                                                        "flat dense size=xs color=grey-6"
                                                    ).tooltip(
                                                        "Copy to clipboard"
                                                    ).on(
                                                        "click",
                                                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(assessment or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
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
                                                    _strat_text = ""
                                                    if s_name:
                                                        _strat_text += (
                                                            f"Strategy: {s_name}\n"
                                                        )
                                                    if s_defn:
                                                        _strat_text += (
                                                            f"Definition: {s_defn}"
                                                        )
                                                    with ui.row().classes(
                                                        "w-full items-center justify-between"
                                                    ):
                                                        ui.label(
                                                            f"New strategy{_delta_str}"
                                                        ).classes(
                                                            "text-[10px] font-semibold text-indigo-6 uppercase tracking-wide"
                                                        )
                                                        ui.button(
                                                            icon="content_copy"
                                                        ).props(
                                                            "flat dense size=xs color=grey-6"
                                                        ).tooltip(
                                                            "Copy to clipboard"
                                                        ).on(
                                                            "click",
                                                            js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(_strat_text.strip())});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
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

                            # Render WARMUP_SUMMARY cards
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
                                                "Summarizer \u2014 Strategy Extracted"
                                            ).classes(
                                                "text-xs font-bold text-indigo-8 uppercase tracking-widest"
                                            )
                                        with ui.column().classes("p-3 gap-1"):
                                            _strat_text = ""
                                            if _ws_name:
                                                _strat_text += f"Strategy: {_ws_name}\n"
                                            if _ws_defn:
                                                _strat_text += f"Definition: {_ws_defn}"
                                            with ui.row().classes(
                                                "w-full items-center justify-between"
                                            ):
                                                ui.label("Extracted strategy").classes(
                                                    "text-[10px] font-semibold text-indigo-6 uppercase tracking-wide"
                                                )
                                                ui.button(icon="content_copy").props(
                                                    "flat dense size=xs color=grey-6"
                                                ).tooltip("Copy to clipboard").on(
                                                    "click",
                                                    js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(_strat_text.strip())});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                                                )
                                            ui.html(
                                                '<pre style="font-size:11px;padding:8px;background:white;'
                                                "border:1px solid #c5cae9;border-radius:4px;margin:0;"
                                                'white-space:pre-wrap;word-break:break-word">'
                                                + html.escape(_strat_text.strip())
                                                + "</pre>"
                                            )

            if not detail_mode:
                self._wire_expand_toggle(body_col)
