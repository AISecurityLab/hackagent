# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR attack card rendering."""

from __future__ import annotations

import html
import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class PairCardMixin:
    """Mixin providing PAIR attack card parse + render."""

    @staticmethod
    def _parse_pair_traces(traces: list[dict]) -> list[dict]:
        """Parse PAIR traces into per-iteration rows."""
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))
        rows: list[dict] = []

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            step_name = str(content.get("step_name") or "")
            if "Iteration" not in step_name and "iteration" not in step_name:
                continue
            metadata = content.get("metadata") or {}
            iteration = int(metadata.get("iteration") or len(rows) + 1)
            req = content.get("request") or {}
            prompt = req.get("prompt") or "" if isinstance(req, dict) else str(req)
            if isinstance(prompt, list):
                user_msgs = [
                    m.get("content", "") for m in prompt if m.get("role") == "user"
                ]
                prompt = user_msgs[-1] if user_msgs else ""
            resp = content.get("response")
            resp, _pair_g_side, _pair_g_expl, _pair_g_cats = (
                AttackCardSharedMixin._extract_guardrail_from_response(resp)
            )
            # Fallback: guardrail info in metadata (older traces)
            if not _pair_g_side:
                _gi = metadata.get("guardrail_info") or {}
                if not _gi:
                    _tc = metadata.get("target_call") or {}
                    _gi = _tc.get("guardrail_info") or {}
                if _gi.get("side"):
                    _pair_g_side = _gi["side"]
                    _pair_g_expl = str(
                        _gi.get("reasoning")
                        or _gi.get("message")
                        or _gi.get("explanation")
                        or "Blocked by guardrail"
                    )
                    _pair_g_cats = _gi.get("categories") or []
            if isinstance(resp, dict):
                response = (
                    resp.get("generated_text") or resp.get("completion") or str(resp)
                )
            elif resp is not None:
                response = str(resp)
            else:
                response = ""
            score_raw = (
                metadata.get("score")
                or metadata.get("judge_score")
                or content.get("score")
            )
            try:
                score = int(float(score_raw)) if score_raw is not None else None
            except (TypeError, ValueError):
                score = None
            rows.append(
                {
                    "iteration": iteration,
                    "prompt": str(prompt),
                    "response": response,
                    "score": score,
                    "is_best": False,
                    "_guardrail_side": _pair_g_side,
                    "_guardrail_explanation": _pair_g_expl,
                    "_guardrail_categories": _pair_g_cats,
                }
            )

        if rows:
            scored = [r for r in rows if r["score"] is not None]
            if scored:
                best = max(scored, key=lambda r: r["score"])  # type: ignore[arg-type]
                best["is_best"] = True

        return rows

    def _render_pair_goal_card(
        self, row: dict, steps: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a PAIR goal card as a conversation with per-iteration steps."""
        with self._goal_card_shell(row, detail_mode):
            if not steps:
                ui.label("No PAIR iteration data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-0 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    for step in steps:
                        iteration = step["iteration"]
                        score = step["score"]
                        is_best = step["is_best"]
                        prompt = step["prompt"]
                        response = step["response"]
                        _guardrail_side = step.get("_guardrail_side") or ""
                        _guardrail_explanation = (
                            step.get("_guardrail_explanation") or ""
                        )
                        _guardrail_categories = step.get("_guardrail_categories") or []

                        with ui.row().classes("items-center gap-2 mt-3 mb-1 px-1"):
                            _iter_label = f"Iteration {iteration}"
                            if score is not None:
                                _iter_label += f" — Score {score}/10"
                            if is_best:
                                _iter_label += " — Best"
                            ui.label(_iter_label).classes(
                                "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                            )

                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label("PROMPT SENT TO TARGET").classes(
                                "text-[10px] text-grey-6 font-semibold uppercase tracking-wide px-1"
                            )
                            ui.button(icon="content_copy").props(
                                "flat dense size=xs color=grey-6"
                            ).tooltip("Copy to clipboard").on(
                                "click",
                                js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(prompt or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                            )
                        ui.html(
                            '<pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;'
                            'border-radius:4px;margin-bottom:6px;white-space:pre-wrap;word-break:break-word">'
                            + html.escape(prompt or "\u2014")
                            + "</pre>"
                        )

                        if _guardrail_side == "before":
                            self._render_guardrail_event_block(
                                {
                                    "side": "before",
                                    "explanation": _guardrail_explanation,
                                    "categories": _guardrail_categories,
                                }
                            )
                        else:
                            with ui.row().classes(
                                "w-full items-center justify-between"
                            ):
                                ui.label("TARGET RESPONSE").classes(
                                    "text-[10px] text-grey-6 font-semibold uppercase tracking-wide px-1"
                                )
                                ui.button(icon="content_copy").props(
                                    "flat dense size=xs color=grey-6"
                                ).tooltip("Copy to clipboard").on(
                                    "click",
                                    js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(response or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                                )
                            ui.html(
                                '<pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;'
                                'border-radius:4px;white-space:pre-wrap;word-break:break-word">'
                                + html.escape(response or "No response recorded.")
                                + "</pre>"
                            )
                            if _guardrail_side:
                                self._render_guardrail_event_block(
                                    {
                                        "side": _guardrail_side,
                                        "explanation": _guardrail_explanation,
                                        "categories": _guardrail_categories,
                                    }
                                )

                        if iteration < steps[-1]["iteration"]:
                            ui.separator().classes("mt-2 mb-0")

                if not detail_mode:
                    self._wire_expand_toggle(body_col)
