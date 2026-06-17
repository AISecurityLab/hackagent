# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static template attack card rendering."""

from __future__ import annotations

import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class StaticTemplateCardMixin:
    """Mixin providing Static Template attack card parse + render."""

    @staticmethod
    def _parse_static_template_traces(traces: list[dict], goal: str = "") -> list[dict]:
        """Parse StaticTemplate attack traces into per-template rows.

        Each row dict:
          num           – 1-based row number
          template      – attack_prompt with goal text replaced by {goal}
          prompt        – raw attack prompt sent to target
          response      – target model response
          result        – "Jailbreak" | "Mitigated" | "Error"
          _bucket       – "jailbreak" | "mitigated" | "error"
        """
        from collections import deque  # noqa: PLC0415

        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        interaction_traces: list[tuple[str, dict]] = []
        eval_trace_result: dict = {}

        for td in sorted_traces:
            content = td.get("content") or {}
            step_name = str(content.get("step_name") or td.get("step_name") or "")
            if step_name.startswith("Template:"):
                interaction_traces.append((step_name, content))
            elif str(content.get("evaluator") or "").startswith("baseline_"):
                eval_trace_result = content.get("result") or {}

        interaction_traces.sort(
            key=lambda x: (
                x[0],
                (x[1].get("request") or {}).get("messages", [{}])[0].get("content", "")
                if (x[1].get("request") or {}).get("messages")
                else "",
            )
        )

        eval_by_key: dict[tuple, deque] = {}
        eval_by_cat_sample: dict[tuple, deque] = {}
        eval_by_cat_len: dict[tuple, deque] = {}
        for ev in eval_trace_result.get("evaluations") or []:
            _cat = ev.get("template_category") or ""
            _sidx = int(ev.get("sample_index") or 0)
            _rlen = int(ev.get("response_length") or 0)
            key = (_cat, _sidx, _rlen)
            if key not in eval_by_key:
                eval_by_key[key] = deque()
            eval_by_key[key].append(ev)

            _k2 = (_cat, _sidx)
            if _k2 not in eval_by_cat_sample:
                eval_by_cat_sample[_k2] = deque()
            eval_by_cat_sample[_k2].append(ev)

            _k3 = (_cat, _rlen)
            if _k3 not in eval_by_cat_len:
                eval_by_cat_len[_k3] = deque()
            eval_by_cat_len[_k3].append(ev)

        rows: list[dict] = []
        for idx, (_, content) in enumerate(interaction_traces, start=1):
            request = content.get("request") or {}
            messages = request.get("messages") or []
            attack_prompt = messages[0].get("content", "") if messages else ""
            if not attack_prompt:
                attack_prompt = str(request.get("prompt") or "")

            _raw_resp = content.get("response")
            _actual_resp, _g_side, _g_expl, _g_cats = (
                AttackCardSharedMixin._extract_guardrail_from_response(_raw_resp)
            )
            response_text = str(_actual_resp or "")

            metadata = content.get("metadata") or {}
            template_category = str(metadata.get("template_category") or "")
            sample_index = int(metadata.get("sample_index") or 0)
            response_length = int(metadata.get("response_length") or len(response_text))

            if goal and goal in attack_prompt:
                template_display = attack_prompt.replace(goal, "{goal}", 1)
            else:
                template_display = attack_prompt

            key = (template_category, sample_index, response_length)
            success: bool | None = None
            _jcols: dict = {}
            q = eval_by_key.get(key)
            if not q:
                q = eval_by_cat_sample.get((template_category, sample_index))
            if not q:
                q = eval_by_cat_len.get((template_category, response_length))
            if q:
                ev = q.popleft()
                success = bool(ev.get("success", False))
                # Extract eval_* and explanation_* judge columns
                _jcols = {
                    k: v
                    for k, v in ev.items()
                    if k.startswith("eval_") or k.startswith("explanation_")
                }

            if _g_side:
                bucket = "mitigated"
            elif success is True:
                bucket = "jailbreak"
            elif success is False:
                bucket = "mitigated"
            elif response_text:
                bucket = "mitigated"
            else:
                bucket = "error"

            rows.append(
                {
                    "num": idx,
                    "template": template_display,
                    "template_category": template_category,
                    "prompt": attack_prompt,
                    "response": response_text,
                    "result": (
                        "Jailbreak"
                        if bucket == "jailbreak"
                        else "Error"
                        if bucket == "error"
                        else "Mitigated"
                    ),
                    "_bucket": bucket,
                    "_guardrail_side": _g_side,
                    "_guardrail_explanation": _g_expl,
                    "_guardrail_categories": _g_cats,
                    "_judge_columns": _jcols,
                }
            )

        return rows

    def _render_static_template_goal_card(
        self, row: dict, template_rows: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a StaticTemplate goal card grouped by template category."""
        # Pre-compute judge verdicts for each template row
        _gm = row.get("_goal_multi_metrics") or {}
        _jmeta = _gm.get("judge_meta") or getattr(
            self,
            "_history_last_judge_meta",
            {},
        )
        _goal_jvotes = _gm.get("judge_votes") or {}
        for tr in template_rows:
            jc = tr.get("_judge_columns")
            if jc or _goal_jvotes:
                # Fallback to goal-level votes for legacy traces that did not
                # persist per-template evaluation rows.
                tr["_judge_verdicts"] = self._build_judge_verdicts(
                    jc or _goal_jvotes,
                    _jmeta,
                )
            else:
                tr["_judge_verdicts"] = []

        def _fmt_cat(cat: str) -> str:
            return cat.replace("_", " ").title() if cat else "Uncategorised"

        groups: dict[str, list[dict]] = {}
        for tr in template_rows:
            cat = tr.get("template_category") or ""
            groups.setdefault(cat, []).append(tr)

        n_jailbreaks = sum(1 for r in template_rows if r["_bucket"] == "jailbreak")
        n_mitigated = sum(1 for r in template_rows if r["_bucket"] == "mitigated")
        n_errors = sum(1 for r in template_rows if r["_bucket"] == "error")

        bl_cols = [
            {
                "name": "template_short",
                "label": "Template",
                "field": "template_short",
                "align": "left",
            },
            {
                "name": "result",
                "label": "Result",
                "field": "result",
                "align": "center",
                "style": "width:100px",
            },
        ]

        with self._goal_card_shell(row, detail_mode):
            if not template_rows:
                ui.label("No StaticTemplate template data recorded.").classes(
                    "text-sm text-grey-6"
                )
                return

            with ui.column().classes("w-full gap-2 mt-1") as body_col:
                if not detail_mode:
                    body_col.set_visibility(False)

                for cat, rows_in_cat in groups.items():
                    cat_label = _fmt_cat(cat)
                    cat_n_jailbreaks = sum(
                        1 for r in rows_in_cat if r["_bucket"] == "jailbreak"
                    )

                    with ui.row().classes("items-center gap-2 mt-3 mb-0.5 px-1"):
                        ui.label(cat_label).classes(
                            "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                        )
                        ui.badge(
                            f"{len(rows_in_cat)} prompt{'s' if len(rows_in_cat) != 1 else ''}",
                            color="grey-5",
                        ).classes("text-xs")
                        if cat_n_jailbreaks:
                            ui.badge(
                                f"{cat_n_jailbreaks} jailbreak{'s' if cat_n_jailbreaks != 1 else ''}",
                                color="negative",
                            ).classes("text-xs")

                    tbl_rows = [
                        {
                            "_num": tr["num"],
                            "template_short": (
                                (
                                    tr["template"].replace("{goal}", "", 1)[:80]
                                    + "\u2026"
                                )
                                if len(tr["template"].replace("{goal}", "", 1)) > 80
                                else tr["template"].replace("{goal}", "", 1)
                            )
                            or "—",
                            "result": tr["result"],
                            "_bucket": tr["_bucket"],
                            "_full_prompt": tr.get("prompt") or "",
                            "_response": tr.get("response") or "",
                            "_guardrail_side": tr.get("_guardrail_side") or "",
                            "_guardrail_explanation": tr.get("_guardrail_explanation")
                            or "",
                            "_guardrail_categories": tr.get("_guardrail_categories")
                            or [],
                            "_judge_verdicts": tr.get("_judge_verdicts") or [],
                        }
                        for tr in rows_in_cat
                    ]

                    tbl = (
                        ui.table(
                            columns=bl_cols,
                            rows=tbl_rows,
                            row_key="_num",
                        )
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        tbl.props(
                            f":expanded-rows='{json.dumps([r['_num'] for r in tbl_rows])}'"
                        )

                    tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="template_short" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:360px">
    {{ props.row.template_short }}
  </q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row._bucket === 'jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row._bucket === 'mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else color="warning" class="text-xs">Error</q-badge>
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
      <div v-if="props.row._judge_verdicts && props.row._judge_verdicts.length > 0" style="margin-top:10px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs text-grey-6">JUDGE VERDICTS</div>
        <div style="display:flex;flex-direction:column;gap:4px">
          <div v-for="jv in props.row._judge_verdicts" style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:4px" :style="jv.vote > 0 ? 'background:#fef2f2' : 'background:#f0fdf4'">
            <q-icon :name="jv.vote > 0 ? 'dangerous' : 'verified_user'" :color="jv.vote > 0 ? 'red-5' : 'green-6'" size="18px" />
                        <span style="font-size:11px;color:#616161;width:28px;text-align:center">{{ jv.id }}</span>
                        <span style="font-size:12px;font-weight:600;width:180px">{{ jv.name }}</span>
            <span style="font-size:10px;color:#9e9e9e;width:120px">{{ jv.type }}</span>
            <q-badge :color="jv.vote > 0 ? 'negative' : 'positive'" class="text-xs">{{ jv.vote > 0 ? 'JAILBREAK' : 'MITIGATED' }}</q-badge>
          </div>
        </div>
      </div>
    </div>
  </q-td>
</q-tr>
""",
                    )

                # ── Summary row ───────────────────────────────────────
                ui.separator().classes("mt-2")
                with ui.row().classes("items-center gap-2 mt-2 flex-wrap"):
                    ui.label("Summary:").classes("text-xs font-semibold text-grey-6")
                    if n_jailbreaks:
                        ui.badge(
                            f"{n_jailbreaks} Jailbreak{'s' if n_jailbreaks != 1 else ''}",
                            color="negative",
                        ).classes("text-xs")
                    ui.badge(f"{n_mitigated} Mitigated", color="positive").classes(
                        "text-xs"
                    )
                    if n_errors:
                        ui.badge(
                            f"{n_errors} Error{'s' if n_errors != 1 else ''}",
                            color="warning",
                        ).classes("text-xs")

            if not detail_mode:
                self._wire_expand_toggle(body_col)
