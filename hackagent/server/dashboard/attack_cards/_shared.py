# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers used by multiple attack card mixins."""

from __future__ import annotations

import contextlib
import html
import re

from nicegui import ui


class AttackCardSharedMixin:
    """Mixin providing shared attack-card helpers."""

    @staticmethod
    def _border_color_for_bucket(bucket: str) -> str:
        if bucket == "jailbreak":
            return "border-red-400"
        if bucket == "mitigated":
            return "border-green-400"
        if bucket == "failed":
            return "border-orange-400"
        return "border-grey-300"

    def _render_compact_card(self, row: dict, on_click) -> None:
        """Render a compact clickable goal card for the left-panel list view."""
        goal_text = str(row.get("goal") or "—")
        goal_number = row.get("goal_number", "?")
        bucket = row.get("_bucket", "pending")
        border_color = self._border_color_for_bucket(bucket)
        with (
            ui.card()
            .tight()
            .classes(
                f"w-full border-l-4 {border_color} cursor-pointer"
                " hover:shadow-sm transition-shadow"
            )
            .on("click", on_click)
        ):
            with ui.row().classes("items-start gap-2 px-3 py-2 w-full"):
                ui.label(f"#{goal_number}").classes(
                    "font-bold text-xs text-grey-5 shrink-0 w-6 pt-0.5 text-right"
                )
                ui.label(goal_text).classes(
                    "text-xs text-grey-8 flex-1 leading-snug whitespace-pre-wrap"
                )

    @contextlib.contextmanager
    def _goal_card_shell(self, row: dict, detail_mode: bool = False):
        goal_text = str(row.get("goal") or "—")
        goal_number = row.get("goal_number", "?")
        bucket = row.get("_bucket", "pending")
        border_color = self._border_color_for_bucket(bucket)
        if detail_mode:
            _cat = row.get("_goal_category") or ""
            _subcat = row.get("_goal_subcategory") or ""
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    ui.label(f"Goal #{goal_number}").classes(
                        "font-bold text-base shrink-0"
                    )
                    if bucket == "jailbreak":
                        ui.badge("Jailbreak", color="negative").classes("text-xs")
                    elif bucket == "mitigated":
                        ui.badge("Mitigated", color="positive").classes("text-xs")
                    elif bucket == "failed":
                        ui.badge("Error", color="warning").classes("text-xs")
                    lat = row.get("_goal_latency")
                    if lat and lat != "—":
                        ui.badge(f"Latency: {lat}", color="grey-7").classes("text-xs")
                if _cat:
                    _cat_str = _cat
                    if _subcat and _subcat not in ("", "N/A"):
                        _cat_str += f" › {_subcat}"
                    ui.label(_cat_str).classes("text-xs text-grey-5 tracking-wide")
                ui.label(goal_text).classes(
                    "text-sm text-grey-8 whitespace-pre-wrap leading-relaxed"
                )
            ui.separator().classes("my-2")
            yield
        else:
            with ui.card().tight().classes(f"w-full border-l-4 {border_color}"):
                with ui.column().classes("w-full gap-2 p-3") as col:
                    ui.label(f"Goal #{goal_number}").classes(
                        "font-bold text-sm shrink-0"
                    )
                    ui.label(goal_text).classes(
                        "text-sm text-grey-8 whitespace-pre-wrap"
                    )
                    yield col

    @staticmethod
    def _wire_expand_toggle(body_col) -> None:
        toggle_btn = (
            ui.button("Expand", icon="expand_more")
            .props("flat no-caps size=sm color=grey-7")
            .classes("w-full")
        )
        _state: dict = {"open": False}

        def _toggle(_b=body_col, _btn=toggle_btn, _s=_state) -> None:
            _s["open"] = not _s["open"]
            _b.set_visibility(_s["open"])
            _btn.props(
                f"label={'Collapse' if _s['open'] else 'Expand'} icon={'expand_less' if _s['open'] else 'expand_more'} flat no-caps size=sm color=grey-7"
            )

        toggle_btn.on_click(_toggle)

    @staticmethod
    def _format_h4rm3l_program(program: str) -> str:
        """Convert an h4rm3l program string to a human-readable arrow chain."""
        if not program or not isinstance(program, str):
            return program or ""
        p = program.strip()

        # Match function/class calls in the chain
        names = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)(?:\s*\()", p)
        if names:
            # Skip generic wrappers and chain methods
            skip = {"Apply", "Compose", "Pipeline", "then"}
            filtered = [n for n in names if n not in skip]
            if filtered:

                def _camel_to_words(n: str) -> str:
                    # Handle acronyms followed by words: DANDecorator → DAN Decorator
                    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", n)
                    # Handle lowercase/digit followed by uppercase: refusalSuppression → refusal Suppression
                    s = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", s)
                    return s

                return " → ".join(_camel_to_words(n) for n in filtered)
        # Fallback: title-case snake_case names
        if "_" in p and " " not in p:
            return p.replace("_", " ").title()
        return p

    @staticmethod
    def _extract_guardrail_from_response(response_value) -> tuple:
        """Detect a guardrail event embedded in a response value.

        Returns (actual_response, guardrail_side, guardrail_explanation, guardrail_categories).
        """
        if isinstance(response_value, str):
            _m = re.match(r"^\[GUARDRAIL:(\w+)\]\s*(.*)", response_value, re.DOTALL)
            if _m:
                side = _m.group(1)
                explanation = _m.group(2).strip() or "Blocked by guardrail"
                return None, side, explanation, []
            return response_value, "", "", []

        if not isinstance(response_value, dict):
            return response_value, "", "", []

        # New format: adapter_type == "guardrail" with agent_specific_data
        if response_value.get("adapter_type") == "guardrail":
            info = response_value.get("agent_specific_data") or {}
            side = info.get("side", "unknown")
            explanation = str(
                info.get("reasoning")
                or info.get("message")
                or info.get("explanation")
                or "Blocked by guardrail"
            )
            categories = info.get("categories") or []
            if side == "after":
                actual = info.get("target_response") or None
            else:
                actual = None
            return actual, side, explanation, categories

        # Legacy format: dict with side key directly (from tracker extraction)
        if response_value.get("side") in ("before", "after", "unknown"):
            side = response_value.get("side", "unknown")
            explanation = str(
                response_value.get("reasoning")
                or response_value.get("message")
                or response_value.get("explanation")
                or "Blocked by guardrail"
            )
            categories = response_value.get("categories") or []
            if side == "after":
                actual = response_value.get("target_response") or None
            else:
                actual = None
            return actual, side, explanation, categories

        return response_value, "", "", []

    @staticmethod
    def _render_guardrail_event_block(event: dict) -> None:
        """Render a visual banner for a guardrail-blocked trace step."""
        side = event.get("side", "unknown")
        explanation = str(
            event.get("explanation")
            or event.get("reasoning")
            or event.get("message")
            or "Blocked by guardrail"
        )
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
            heading = "\u26a0 BEFORE GUARDRAIL \u2014 BLOCKED"
            border_color = "#f97316"
            bg_color = "#fff7ed"
            heading_color = "#c2410c"
            expl_label = (
                '<span style="font-weight:700;color:#c2410c">Explanation: </span>'
            )
        elif side == "after":
            heading = "\U0001f6ab AFTER GUARDRAIL \u2014 CENSORED"
            border_color = "#ef4444"
            bg_color = "#fef2f2"
            heading_color = "#dc2626"
            expl_label = (
                '<span style="font-weight:700;color:#dc2626">Explanation: </span>'
            )
        else:
            heading = "\U0001f6e1 GUARDRAIL \u2014 BLOCKED"
            border_color = "#9e9e9e"
            bg_color = "#f5f5f5"
            heading_color = "#616161"
            expl_label = (
                '<span style="font-weight:700;color:#616161">Explanation: </span>'
            )

        ui.html(
            f'<div style="margin-bottom:8px">'
            f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:4px;color:{heading_color}">{heading}</div>'
            f'<pre style="font-size:11px;padding:10px;background:{bg_color};border:2px solid {border_color};border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0">'
            f"{cat_html}"
            f"{expl_label}"
            f'<span style="color:#6b7280">{html.escape(explanation)}</span>'
            f"</pre></div>"
        )
