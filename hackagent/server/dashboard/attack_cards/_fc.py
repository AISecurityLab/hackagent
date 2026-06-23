# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FC-Attack (multimodal image-based) card mixin for the dashboard."""

from __future__ import annotations

import html as html_mod
import json

from nicegui import ui


class FCCardMixin:
    """Renders FC-Attack-specific goal card sections (flowchart image, prompt, response)."""

    @staticmethod
    def _parse_fc_traces(traces: list[dict]) -> dict:
        """Parse FC-Attack traces into a summary dict.

        Returns a dict with keys:
          layout, num_steps, steps, image_data_url, text_prompt, response, traces
        """
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        layout = "vertical"
        num_steps = 0
        steps: list[str] = []
        image_data_url = ""
        text_prompt = ""
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

            if metadata.get("image_data_url"):
                image_data_url = metadata["image_data_url"]

            # Text prompt: metadata > request["prompt"]
            prompt_candidate = (
                metadata.get("text_prompt")
                or metadata.get("jailbreak_prompt")
                or request.get("prompt")
                or content.get("text_prompt")
                or content.get("attack_prompt")
            )
            if prompt_candidate:
                text_prompt = prompt_candidate

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
            "image_data_url": image_data_url,
            "text_prompt": text_prompt,
            "response": response,
            "traces": sorted_traces,
        }

    def _render_fc_goal_card(
        self,
        row: dict,
        data: dict,
        detail_mode: bool = False,
    ) -> None:
        """Render a per-goal result card for FC-Attack showing the flowchart image."""
        image_data_url = data.get("image_data_url", "")
        text_prompt = data.get("text_prompt", "")
        response = data.get("response", "")

        with self._goal_card_shell(row, detail_mode):  # type: ignore[attr-defined]
            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                # PROMPT SENT TO TARGET (flowchart image + text in one box)
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("PROMPT SENT TO TARGET").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    with ui.row().classes("items-center gap-1"):
                        if image_data_url:
                            ui.button(icon="download").props(
                                "flat dense size=xs color=grey-6"
                            ).tooltip("Download flowchart").on(
                                "click",
                                js_handler=f"() => {{var a=document.createElement('a');a.href={json.dumps(image_data_url)};a.download='fc_attack.png';document.body.appendChild(a);a.click();document.body.removeChild(a);}}",
                            )
                        if text_prompt:
                            ui.button(icon="content_copy").props(
                                "flat dense size=xs color=grey-6"
                            ).tooltip("Copy text prompt").on(
                                "click",
                                js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(text_prompt)});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                            )

                # Build prompt display
                prompt_parts = ""
                if image_data_url:
                    prompt_parts += (
                        f'<img src="{image_data_url}" '
                        f'alt="FC-Attack flowchart" '
                        f'style="display:block;max-width:100%;width:100%;height:auto;border-radius:4px;'
                        f'border:1px solid #e0e0e0;margin-bottom:8px;box-sizing:border-box;" />'
                    )
                prompt_parts += (
                    '<pre style="font-size:11px;margin:0;padding:0;'
                    'white-space:pre-wrap;word-break:break-word">'
                    + html_mod.escape(text_prompt or "\u2014")
                    + "</pre>"
                )
                ui.html(
                    f'<div style="padding:8px;background:white;border:1px solid #e0e0e0;'
                    f'border-radius:4px;margin-bottom:8px;overflow:visible;box-sizing:border-box;">{prompt_parts}</div>'
                ).classes("w-full").style("overflow:visible;width:100%;")

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

    def _render_fc_result_section(self, row: dict, metadata: dict) -> None:
        """Render FC-Attack-specific result content: flowchart image, prompt, response."""
        image_data_url = metadata.get("image_data_url", "")
        text_prompt = (
            metadata.get("text_prompt") or metadata.get("jailbreak_prompt") or ""
        )
        response = metadata.get("jailbreak_response") or metadata.get("response") or ""

        with ui.column().classes("w-full gap-2"):
            if image_data_url or text_prompt:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("PROMPT SENT TO TARGET").classes(
                        "text-[10px] text-grey-6 font-semibold uppercase tracking-wide"
                    )
                    with ui.row().classes("items-center gap-1"):
                        if image_data_url:
                            ui.button(icon="download").props(
                                "flat dense size=xs color=grey-6"
                            ).tooltip("Download flowchart").on(
                                "click",
                                js_handler=f"() => {{var a=document.createElement('a');a.href={json.dumps(image_data_url)};a.download='fc_attack.png';document.body.appendChild(a);a.click();document.body.removeChild(a);}}",
                            )
                        if text_prompt:
                            ui.button(icon="content_copy").props(
                                "flat dense size=xs color=grey-6"
                            ).tooltip("Copy text prompt").on(
                                "click",
                                js_handler=f"(event) => {{var b=event.currentTarget,ic=b.querySelector('.q-icon');if(navigator.clipboard)navigator.clipboard.writeText({json.dumps(text_prompt)});if(ic){{ic.textContent='check';setTimeout(function(){{ic.textContent='content_copy';}},2000);}}}}",
                            )

                prompt_parts = ""
                if image_data_url:
                    prompt_parts += (
                        f'<img src="{image_data_url}" '
                        f'alt="FC-Attack flowchart" '
                        f'style="display:block;max-width:100%;width:100%;height:auto;border-radius:4px;'
                        f'border:1px solid #e0e0e0;margin-bottom:8px;box-sizing:border-box;" />'
                    )
                if text_prompt:
                    prompt_parts += (
                        '<pre style="font-size:11px;margin:0;padding:0;'
                        'white-space:pre-wrap;word-break:break-word">'
                        + html_mod.escape(text_prompt)
                        + "</pre>"
                    )
                if prompt_parts:
                    ui.html(
                        f'<div style="padding:8px;background:white;border:1px solid #e0e0e0;'
                        f'border-radius:4px;overflow:visible;box-sizing:border-box;">{prompt_parts}</div>'
                    ).classes("w-full").style("overflow:visible;width:100%;")

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

    def _render_fc_trace_image(self, metadata: dict) -> None:
        """Render FC-Attack flowchart image inline within trace content."""
        fc_image_url = metadata.get("image_data_url", "")
        if fc_image_url:
            ui.html(
                f'<div style="padding:8px;background:white;border:1px solid #e0e0e0;'
                f'border-radius:4px;margin-bottom:8px;overflow:visible;box-sizing:border-box;">'
                f'<img src="{fc_image_url}" '
                f'alt="FC-Attack flowchart" '
                f'style="display:block;max-width:100%;width:100%;height:auto;border-radius:4px;'
                f'border:1px solid #e0e0e0;box-sizing:border-box;" />'
                f"</div>"
            ).classes("w-full").style("overflow:visible;width:100%;")
