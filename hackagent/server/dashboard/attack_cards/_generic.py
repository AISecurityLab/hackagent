# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Generic / fallback attack card rendering."""

from __future__ import annotations

import html
import json

from nicegui import ui


class GenericCardMixin:
    """Mixin providing generic (fallback) attack card parse + render."""

    @staticmethod
    def _extract_request_response_candidates(content: object) -> tuple[object, object]:
        """Best-effort extraction of request/response payloads from trace content."""
        if not isinstance(content, dict):
            return None, None

        metadata = (
            content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
        )
        nested_result = (
            content.get("result") if isinstance(content.get("result"), dict) else {}
        )

        request_value = (
            content.get("request")
            or content.get("prefix")
            or content.get("prompt")
            or nested_result.get("request")
            or nested_result.get("prefix")
            or nested_result.get("prompt")
            or metadata.get("request")
            or metadata.get("prefix")
            or metadata.get("prompt")
        )
        response_value = (
            content.get("response")
            or content.get("completion")
            or content.get("answer")
            or nested_result.get("response")
            or nested_result.get("completion")
            or nested_result.get("answer")
            or metadata.get("response")
            or metadata.get("completion")
            or metadata.get("answer")
            or metadata.get("raw_response_body")
        )

        if isinstance(request_value, dict):
            request_value = (
                request_value.get("prompt")
                or request_value.get("request")
                or request_value
            )

        if isinstance(response_value, dict):
            response_value = (
                response_value.get("target_response")
                or response_value.get("response")
                or response_value.get("completion")
                or response_value.get("generated_text")
                or response_value
            )

        return request_value, response_value

    @staticmethod
    def _extract_prompt_response_from_traces(
        traces: list[dict],
    ) -> tuple[str, str, "dict | None"]:
        """Extract the best (prompt, response, guardrail_event) from generic attack traces."""
        best_req = ""
        best_resp = ""
        fallback_req = ""
        guardrail_event: dict | None = None
        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            req, resp = GenericCardMixin._extract_request_response_candidates(content)
            # Detect guardrail event dict before stringifying
            if isinstance(resp, dict) and resp.get("side") in (
                "before",
                "after",
                "unknown",
            ):
                guardrail_event = resp
                resp = None
            req_str = (
                json.dumps(req, indent=2)
                if isinstance(req, (dict, list))
                else str(req)
                if req not in (None, "")
                else ""
            )
            resp_str = (
                json.dumps(resp, indent=2)
                if isinstance(resp, (dict, list))
                else str(resp)
                if resp not in (None, "")
                else ""
            )
            if req_str and resp_str:
                best_req = req_str
                best_resp = resp_str
            elif req_str:
                fallback_req = req_str
        if best_req:
            return best_req, best_resp, guardrail_event
        if fallback_req:
            return fallback_req, "(no response recorded)", guardrail_event
        return "(not available)", "(not available)", guardrail_event

    def _render_generic_goal_card(
        self,
        row: dict,
        request_text: str,
        response_text: str,
        detail_mode: bool = False,
        guardrail_event: dict | None = None,
    ) -> None:
        """Render a per-goal result card for non-specific attacks."""
        with self._goal_card_shell(row, detail_mode):
            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("PROMPT SENT TO TARGET").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    ui.button(icon="content_copy").props(
                        "flat dense size=xs color=grey-6"
                    ).tooltip("Copy to clipboard").on(
                        "click",
                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(request_text or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                    )
                ui.html(
                    '<pre style="font-size:11px;padding:8px;background:white;'
                    "border:1px solid #e0e0e0;border-radius:4px;margin-bottom:8px;"
                    'white-space:pre-wrap;word-break:break-word">'
                    + html.escape(request_text or "\u2014")
                    + "</pre>"
                )

                _g_side = (guardrail_event or {}).get("side") or ""
                if _g_side == "before":
                    self._render_guardrail_event_block(guardrail_event)  # type: ignore[arg-type]
                else:
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("TARGET RESPONSE").classes(
                            "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                        )
                        ui.button(icon="content_copy").props(
                            "flat dense size=xs color=grey-6"
                        ).tooltip("Copy to clipboard").on(
                            "click",
                            js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(response_text or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                        )
                    ui.html(
                        '<pre style="font-size:11px;padding:8px;background:white;'
                        "border:1px solid #e0e0e0;border-radius:4px;"
                        'white-space:pre-wrap;word-break:break-word">'
                        + html.escape(response_text or "No response recorded.")
                        + "</pre>"
                    )
                    if _g_side:
                        self._render_guardrail_event_block(guardrail_event)  # type: ignore[arg-type]

                # ── Judge Verdicts ──
                if detail_mode and row.get("_is_multi_judge"):
                    _gm = row.get("_goal_multi_metrics")
                    if isinstance(_gm, dict):
                        _jv = _gm.get("judge_votes")
                        _jmeta = _gm.get("judge_meta") or getattr(
                            self,
                            "_history_last_judge_meta",
                            {},
                        )
                        if isinstance(_jv, dict) and _jv:
                            ui.separator().classes("my-2")
                            ui.label("JUDGE VERDICTS").classes(
                                "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                            )
                            with ui.column().classes("w-full gap-1 mt-1"):
                                for _jk in sorted(_jv.keys()):
                                    _vote = int(_jv[_jk])
                                    _meta = _jmeta.get(_jk, {})
                                    _jname = _meta.get("name") or (
                                        _jk[5:] if _jk.startswith("eval_") else _jk
                                    )
                                    _jtype = (
                                        _meta.get("type")
                                        or self._judge_type_from_key(_jk)
                                        or "—"
                                    )
                                    _verdict_text = (
                                        "JAILBREAK" if _vote > 0 else "MITIGATED"
                                    )
                                    _verdict_color = "red-4" if _vote > 0 else "green-4"
                                    _icon = (
                                        "dangerous" if _vote > 0 else "verified_user"
                                    )
                                    with (
                                        ui.row()
                                        .classes("items-center gap-2 px-2 py-1 rounded")
                                        .style(
                                            "background:#fef2f2"
                                            if _vote > 0
                                            else "background:#f0fdf4"
                                        )
                                    ):
                                        ui.icon(_icon, size="sm").classes(
                                            "text-red-5"
                                            if _vote > 0
                                            else "text-green-6"
                                        )
                                        ui.label(_jname).classes(
                                            "text-xs font-medium w-[140px]"
                                        )
                                        ui.label(_jtype).classes(
                                            "text-[10px] text-grey-5 w-[120px]"
                                        )
                                        ui.badge(
                                            _verdict_text, color=_verdict_color
                                        ).classes("text-xs")

            if not detail_mode:
                self._wire_expand_toggle(body_col)
