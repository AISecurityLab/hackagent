# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Best-of-N (BoN) attack card rendering."""

from __future__ import annotations

import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class BonCardMixin:
    """Mixin providing BoN attack card parse + render."""

    @staticmethod
    def _parse_bon_traces(traces: list[dict]) -> list[dict]:
        """Parse BoN traces into per-step groups.

        Returns a list of step dicts, each containing:
          step          – 0-based step index
          step_label    – human label "Step N / M"
          is_jailbreak  – True if the judge confirmed jailbreak for this step
          candidates    – list of candidate dicts
        """
        candidate_traces: list[dict] = []
        eval_traces: list[dict] = []

        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            dtype = str(meta.get("display_type") or "").lower()
            if dtype == "bon_candidate":
                candidate_traces.append(td)
            elif dtype == "bon_evaluation":
                eval_traces.append(td)

        step_jailbreak: dict[int, bool] = {}
        for td in eval_traces:
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            s = meta.get("step")
            if s is not None:
                step_jailbreak[int(s)] = bool(meta.get("is_jailbreak", False))

        by_step: dict[int, list[dict]] = {}
        for td in candidate_traces:
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            s = int(meta.get("step", 0))
            by_step.setdefault(s, []).append(td)

        if not by_step:
            return []

        n_steps_seen = 1
        for td in candidate_traces:
            content = td.get("content") or {}
            meta = content.get("metadata") or {}
            n_steps_seen = max(n_steps_seen, int(meta.get("n_steps", 1)))

        steps: list[dict] = []
        for s in sorted(by_step.keys()):
            cands = []
            for td in sorted(
                by_step[s],
                key=lambda x: int(
                    (x.get("content") or {})
                    .get("metadata", {})
                    .get("candidate_index", 0)
                ),
            ):
                content = td.get("content") or {}
                meta = content.get("metadata") or {}
                request = content.get("request") or {}
                response_obj = content.get("response")

                augmented_prompt = (
                    request.get("prompt")
                    or (request.get("messages") or [{}])[0].get("content", "")
                    if isinstance(request, dict)
                    else ""
                )

                response_obj, _g_side, _g_expl, _g_cats = (
                    AttackCardSharedMixin._extract_guardrail_from_response(response_obj)
                )

                if isinstance(response_obj, dict):
                    response_text = (
                        response_obj.get("generated_text")
                        or response_obj.get("completion")
                        or ""
                    )
                    error_text = response_obj.get("error_message")
                elif response_obj is not None:
                    response_text = str(response_obj)
                    error_text = None
                else:
                    response_text = ""
                    error_text = None

                resp_len = int(meta.get("response_length", len(response_text or "")))
                cands.append(
                    {
                        "k": int(meta.get("candidate_index", 0)),
                        "augmented_prompt": augmented_prompt,
                        "response": response_text,
                        "response_length": resp_len,
                        "is_best": bool(meta.get("is_best", False)),
                        "error": error_text,
                        "_guardrail_side": _g_side,
                        "_guardrail_explanation": _g_expl,
                        "_guardrail_categories": _g_cats,
                    }
                )

            steps.append(
                {
                    "step": s,
                    "step_label": f"Step {s + 1} / {n_steps_seen}",
                    "is_jailbreak": step_jailbreak.get(s, False),
                    "candidates": cands,
                }
            )

        return steps

    def _render_bon_goal_card(
        self, row: dict, step_groups: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a BoN goal card with per-step candidate tables."""
        with self._goal_card_shell(row, detail_mode):
            if not step_groups:
                ui.label("No BoN step results recorded.").classes("text-sm text-grey-6")
                return

            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                for sg in step_groups:
                    step_label = sg["step_label"]
                    is_jailbreak_step = sg["is_jailbreak"]
                    candidates = sg["candidates"]

                    with ui.row().classes("items-center gap-2 mt-3 mb-0.5 px-1"):
                        ui.label(step_label).classes(
                            "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                        )
                        if is_jailbreak_step:
                            ui.badge("Jailbreak", color="negative").classes("text-xs")

                    columns = [
                        {
                            "name": "k",
                            "label": "K",
                            "field": "k",
                            "align": "center",
                            "style": "width:48px",
                        },
                        {
                            "name": "augmented_prompt",
                            "label": "Augmented prompt",
                            "field": "augmented_prompt",
                            "align": "left",
                        },
                        {
                            "name": "response_length",
                            "label": "Response length",
                            "field": "response_length",
                            "align": "center",
                            "style": "width:140px",
                        },
                        {
                            "name": "result",
                            "label": "Result",
                            "field": "result",
                            "align": "center",
                            "style": "width:100px",
                        },
                    ]

                    rows_data = []
                    for c in candidates:
                        if c.get("_guardrail_side"):
                            result_label = "Mitigated"
                        elif c["error"]:
                            result_label = "Error"
                        elif c["is_best"] and is_jailbreak_step:
                            result_label = "Jailbreak"
                        elif c["is_best"] and not is_jailbreak_step:
                            result_label = "Mitigated"
                        else:
                            result_label = "—"
                        aug = c.get("augmented_prompt") or ""
                        rows_data.append(
                            {
                                "k": c["k"],
                                "augmented_prompt": (aug[:80] + "\u2026")
                                if len(aug) > 80
                                else aug or "—",
                                "response_length": c["response_length"],
                                "result": result_label,
                                "_is_best": c["is_best"],
                                "_full_prompt": aug,
                                "_response": c.get("response") or "",
                                "_guardrail_side": c.get("_guardrail_side") or "",
                                "_guardrail_explanation": c.get(
                                    "_guardrail_explanation"
                                )
                                or "",
                            }
                        )

                    tbl = (
                        ui.table(columns=columns, rows=rows_data, row_key="k")
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        tbl.props(
                            f":expanded-rows='{json.dumps([r['k'] for r in rows_data])}'"
                        )

                    tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand"
      :class="props.row._is_best ? 'bg-grey-2' : ''"
      style="cursor:pointer">
  <q-td key="k" :props="props">{{ props.row.k }}</q-td>
  <q-td key="augmented_prompt" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:320px">
    {{ props.row.augmented_prompt }}
  </q-td>
  <q-td key="response_length" :props="props">{{ props.row.response_length }}</q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row.result === 'Jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row.result === 'Mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else-if="props.row.result === 'Error'" color="warning" class="text-xs">Error</q-badge>
    <span v-else class="text-grey-5">&#8212;</span>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <div class="row items-center justify-between q-mb-xs">
        <span class="text-caption text-weight-bold text-uppercase text-grey-6">PROMPT SENT TO TARGET</span>
        <span :data-cliptext="props.row._full_prompt||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
      </div>
      <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                  border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prompt || '\u2014' }}</pre>
      <template v-if="props.row._guardrail_side !== 'before'">
        <div class="row items-center justify-between q-mb-xs">
          <span class="text-caption text-weight-bold text-uppercase text-grey-6">TARGET RESPONSE</span>
          <span :data-cliptext="props.row._response||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
        </div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._response || 'No response recorded.' }}</pre>
      </template>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">&#x26a0; BEFORE GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">&#x1f6ab; AFTER GUARDRAIL &#x2014; CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">&#x1f6e1; GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                    )

            if not detail_mode:
                self._wire_expand_toggle(body_col)
