# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""tFC-Attack (text-only flowchart) card mixin for the dashboard."""

from __future__ import annotations

import html as html_mod
import json

from nicegui import ui


class tFCCardMixin:
    """Renders tFC-Attack-specific goal card sections (graph text prompt, response)."""

    @staticmethod
    def _parse_tfc_traces(traces: list[dict]) -> dict:
        """Parse tFC-Attack traces into a summary dict.

        Returns a dict with keys:
          layout, num_steps, steps, text_format, graph_text, full_prompt,
          response, traces
        """
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        layout = "vertical"
        num_steps = 0
        steps: list[str] = []
        graph_text = ""
        full_prompt = ""
        text_format = "ascii"
        response = ""

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )
            request = (
                content.get("request")
                if isinstance(content.get("request"), dict)
                else {}
            )
            resp_obj = content.get("response")

            if metadata.get("layout"):
                layout = metadata["layout"]
            elif request.get("layout"):
                layout = request["layout"]

            if metadata.get("num_steps"):
                num_steps = metadata["num_steps"]

            if metadata.get("steps"):
                steps = metadata["steps"]
            elif request.get("steps"):
                steps = request["steps"]

            if metadata.get("full_prompt"):
                full_prompt = metadata["full_prompt"]
            if metadata.get("graph_text"):
                graph_text = metadata["graph_text"]
            if metadata.get("text_format"):
                text_format = metadata["text_format"]

            # Response
            resp_candidate = None
            if isinstance(resp_obj, dict):
                resp_candidate = (
                    resp_obj.get("generated_text")
                    or resp_obj.get("target_response")
                    or resp_obj.get("response")
                    or resp_obj.get("completion")
                )
            elif isinstance(resp_obj, str):
                resp_candidate = resp_obj

            if not resp_candidate:
                resp_candidate = metadata.get("jailbreak_response") or metadata.get(
                    "response"
                )

            if resp_candidate and isinstance(resp_candidate, str):
                response = resp_candidate

        return {
            "layout": layout,
            "num_steps": num_steps,
            "steps": steps,
            "graph_text": graph_text,
            "full_prompt": full_prompt,
            "text_format": text_format,
            "response": response,
            "traces": sorted_traces,
        }

    def _render_tfc_goal_card(
        self,
        row: dict,
        data: dict,
        detail_mode: bool = False,
    ) -> None:
        """Render a per-goal result card for tFC-Attack showing graph text prompt."""
        full_prompt = data.get("full_prompt", "")
        graph_text = data.get("graph_text", "")
        response = data.get("response", "")

        display_text = full_prompt or graph_text

        with self._goal_card_shell(row, detail_mode):  # type: ignore[attr-defined]
            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                # PROMPT SENT TO TARGET
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("PROMPT SENT TO TARGET").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    if display_text:
                        ui.button(icon="content_copy").props(
                            "flat dense size=xs color=grey-6"
                        ).tooltip("Copy text prompt").on(
                            "click",
                            js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(display_text)});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                        )

                ui.html(
                    '<pre style="font-size:11px;padding:8px;background:white;'
                    "border:1px solid #e0e0e0;border-radius:4px;margin-bottom:8px;"
                    'white-space:pre-wrap;word-break:break-word">'
                    + html_mod.escape(display_text or "\u2014")
                    + "</pre>"
                )

                # TARGET RESPONSE
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("TARGET RESPONSE").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    ui.button(icon="content_copy").props(
                        "flat dense size=xs color=grey-6"
                    ).tooltip("Copy to clipboard").on(
                        "click",
                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(response or '')});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                    )
                ui.html(
                    '<pre style="font-size:11px;padding:8px;background:white;'
                    "border:1px solid #e0e0e0;border-radius:4px;"
                    'white-space:pre-wrap;word-break:break-word">'
                    + html_mod.escape(response or "No response recorded.")
                    + "</pre>"
                )

            if not detail_mode:
                self._wire_expand_toggle(body_col)  # type: ignore[attr-defined]

    def _render_tfc_result_section(self, row: dict, metadata: dict) -> None:
        """Render tFC-Attack-specific result content: graph text prompt, response."""
        full_prompt = metadata.get("full_prompt", "")
        graph_text = metadata.get("graph_text", "")
        response = metadata.get("jailbreak_response") or metadata.get("response") or ""

        display_text = full_prompt or graph_text

        with ui.column().classes("w-full gap-2"):
            if display_text:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("PROMPT SENT TO TARGET").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    ui.button(icon="content_copy").props(
                        "flat dense size=xs color=grey-6"
                    ).tooltip("Copy text prompt").on(
                        "click",
                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(display_text)});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                    )
                ui.html(
                    '<pre style="font-size:11px;padding:8px;background:white;'
                    "border:1px solid #e0e0e0;border-radius:4px;"
                    'white-space:pre-wrap;word-break:break-word">'
                    + html_mod.escape(display_text)
                    + "</pre>"
                )

            # Target model response
            if response:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("TARGET RESPONSE").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    ui.button(icon="content_copy").props(
                        "flat dense size=xs color=grey-6"
                    ).tooltip("Copy to clipboard").on(
                        "click",
                        js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(response)});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                    )
                ui.html(
                    '<pre style="font-size:11px;padding:8px;background:white;'
                    "border:1px solid #e0e0e0;border-radius:4px;"
                    'white-space:pre-wrap;word-break:break-word">'
                    + html_mod.escape(response)
                    + "</pre>"
                )
