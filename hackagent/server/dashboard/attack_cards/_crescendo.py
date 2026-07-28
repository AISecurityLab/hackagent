# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Crescendo attack card rendering."""

from __future__ import annotations

import html
import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class CrescendoCardMixin:
    """Mixin providing Crescendo attack card parse + render."""

    @staticmethod
    def _format_crescendo_score(score: float | int | None) -> str:
        """Format scores without losing decimal precision in the UI."""
        if score is None:
            return "—"
        numeric_score = float(score)
        return (
            str(int(numeric_score))
            if numeric_score.is_integer()
            else f"{numeric_score:g}"
        )

    @staticmethod
    def _parse_crescendo_traces(traces: list[dict]) -> list[dict]:
        """Parse Crescendo traces into the single, ordered conversation timeline.

        Unlike PAIR (independent parallel streams), Crescendo keeps one
        growing conversation per goal, so every trace is shown in the order
        it happened -- including the discarded/backtracked turns, which are
        clearly marked so the escalation strategy is easy to follow.
        """
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))
        rows: list[dict] = []

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            step_name = str(content.get("step_name") or "")
            if "Turn" not in step_name:
                continue
            metadata = content.get("metadata") or {}
            try:
                turn = int(metadata.get("turn") or len(rows) + 1)
            except (TypeError, ValueError):
                turn = len(rows) + 1

            req = content.get("request") or {}
            prompt = req.get("prompt") or "" if isinstance(req, dict) else str(req)

            resp = content.get("response")
            (
                resp,
                _guardrail_side,
                _guardrail_expl,
                _guardrail_cats,
            ) = AttackCardSharedMixin._extract_guardrail_from_response(resp)
            if isinstance(resp, dict):
                response = (
                    resp.get("generated_text") or resp.get("completion") or str(resp)
                )
            elif resp is not None:
                response = str(resp)
            else:
                response = ""

            score_raw = metadata.get("score")
            try:
                score = float(score_raw) if score_raw is not None else None
            except (TypeError, ValueError):
                score = None

            backtrack_raw = metadata.get("backtrack")
            try:
                backtrack = int(backtrack_raw) if backtrack_raw is not None else 0
            except (TypeError, ValueError):
                backtrack = 0

            is_discarded = "backtrack" in step_name.lower()
            refused_flag = bool(metadata.get("refused"))
            rows.append(
                {
                    "turn": turn,
                    "backtrack": backtrack,
                    "is_backtracked": is_discarded,
                    "is_error": "Failed" in step_name,
                    # Accepted despite being flagged as a refusal by the
                    # judge -- this happens once the backtrack budget is
                    # exhausted, so the turn is kept in the conversation but
                    # never counted toward the best score / success.
                    "is_refused_accepted": refused_flag and not is_discarded,
                    "prompt": str(prompt),
                    "response": response,
                    "score": score,
                    "is_best": bool(metadata.get("is_best")),
                    "_guardrail_side": _guardrail_side,
                    "_guardrail_explanation": _guardrail_expl,
                    "_guardrail_categories": _guardrail_cats,
                }
            )

        return rows

    def _render_crescendo_goal_card(
        self, row: dict, steps: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a Crescendo goal card as a single ordered conversation timeline."""
        with self._goal_card_shell(row, detail_mode):
            if not steps:
                ui.label("No Crescendo turn data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-0 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    scores = [s["score"] for s in steps if s["score"] is not None]
                    best_score = max(scores) if scores else None
                    backtrack_count = sum(1 for s in steps if s["is_backtracked"])
                    accepted_count = sum(
                        1 for s in steps if not s["is_backtracked"] and not s["is_error"]
                    )
                    with ui.row().classes("items-center gap-2 flex-wrap mb-1"):
                        ui.badge(
                            f"{accepted_count} turns", color="grey-7"
                        ).classes("text-xs")
                        if backtrack_count:
                            ui.badge(
                                f"{backtrack_count} backtracks", color="orange-6"
                            ).classes("text-xs")
                        if best_score is not None:
                            ui.badge(
                                f"Best {self._format_crescendo_score(best_score)}/10",
                                color="grey-7",
                            ).classes("text-xs")

                    self._render_crescendo_turns(steps)

                if not detail_mode:
                    self._wire_expand_toggle(body_col)

    def _render_crescendo_turns(self, steps: list[dict]) -> None:
        """Render the prompt/response cards for every turn, in conversation order."""
        for index, step in enumerate(steps):
            turn = step["turn"]
            backtrack = step["backtrack"]
            is_backtracked = step["is_backtracked"]
            is_error = step["is_error"]
            is_refused_accepted = step.get("is_refused_accepted", False)
            score = step["score"]
            is_best = step["is_best"]
            prompt = step["prompt"]
            response = step["response"]
            _guardrail_side = step.get("_guardrail_side") or ""
            _guardrail_explanation = step.get("_guardrail_explanation") or ""
            _guardrail_categories = step.get("_guardrail_categories") or []

            with ui.row().classes("items-center gap-2 mt-3 mb-1 px-1"):
                iter_label = f"Turn {turn}"
                if is_backtracked:
                    iter_label += f" — Backtrack {backtrack}"
                if score is not None:
                    iter_label += f" — Score {self._format_crescendo_score(score)}/10"
                if is_best:
                    iter_label += " — Best"
                ui.label(iter_label).classes(
                    "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                )
                if is_backtracked:
                    ui.badge("DISCARDED — REPHRASED", color="orange-6").classes(
                        "text-[10px]"
                    )
                elif is_refused_accepted:
                    ui.badge(
                        "REFUSED — BACKTRACK BUDGET EXHAUSTED", color="red-6"
                    ).classes("text-[10px]")
                elif is_error:
                    ui.badge("NO RESPONSE", color="warning").classes("text-[10px]")

            with ui.row().classes("w-full items-center justify-between"):
                ui.label("QUESTION SENT TO TARGET").classes(
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
                with ui.row().classes("w-full items-center justify-between"):
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

            if index < len(steps) - 1:
                ui.separator().classes("mt-2 mb-0")
