# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAP attack card rendering."""

from __future__ import annotations

import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class PapCardMixin:
    """Mixin providing PAP attack card parse + render."""

    @staticmethod
    def _parse_pap_traces(traces: list[dict]) -> list[dict]:
        """Parse PAP traces into per-technique rows for the result table."""
        candidates: dict[int, dict] = {}
        evaluations: dict[int, dict] = {}

        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            meta = content.get("metadata") or {}
            display_type = meta.get("display_type") or ""
            tech_idx = meta.get("technique_index")
            if tech_idx is None:
                continue
            if display_type == "pap_candidate":
                req = content.get("request") or {}
                prompt = req.get("prompt") or "" if isinstance(req, dict) else ""
                if not prompt and isinstance(req, dict):
                    msgs = req.get("messages") or []
                    for m in reversed(msgs):
                        if isinstance(m, dict) and m.get("role") == "user":
                            prompt = str(m.get("content") or "")
                            break
                _cand_resp = content.get("response")
                _cand_resp_actual, _cand_g_side, _cand_g_expl, _cand_g_cats = (
                    AttackCardSharedMixin._extract_guardrail_from_response(_cand_resp)
                )
                candidates[tech_idx] = {
                    "technique": meta.get("technique") or "",
                    "prompt": prompt,
                    "response": str(_cand_resp_actual) if _cand_resp_actual else "",
                    "_guardrail_side": _cand_g_side,
                    "_guardrail_explanation": _cand_g_expl,
                    "_guardrail_categories": _cand_g_cats,
                }
            elif display_type == "pap_evaluation":
                _pap_raw_resp = content.get("response")
                _pap_raw_resp, _pap_g_side, _pap_g_expl, _pap_g_cats = (
                    AttackCardSharedMixin._extract_guardrail_from_response(
                        _pap_raw_resp
                    )
                )
                _pap_response = (
                    _pap_raw_resp.get("target_response")
                    if isinstance(_pap_raw_resp, dict)
                    else None
                )
                evaluations[tech_idx] = {
                    "is_jailbreak": bool(meta.get("is_jailbreak")),
                    "judge_score": meta.get("judge_score"),
                    "response": _pap_response or "",
                    "_guardrail_side": _pap_g_side,
                    "_guardrail_explanation": _pap_g_expl,
                    "_judge_columns": meta.get("judge_columns") or {},
                }

        rows = []
        for idx in sorted(candidates):
            cand = candidates[idx]
            ev = evaluations.get(idx, {})
            technique = cand["technique"]
            prompt = cand["prompt"]
            is_jailbreak = ev.get("is_jailbreak", False)
            response = ev.get("response") or cand.get("response") or ""
            _guardrail_side = (
                ev.get("_guardrail_side") or cand.get("_guardrail_side") or ""
            )
            _guardrail_explanation = (
                ev.get("_guardrail_explanation")
                or cand.get("_guardrail_explanation")
                or ""
            )
            if _guardrail_side:
                bucket = "mitigated"
            elif is_jailbreak:
                bucket = "jailbreak"
            elif ev:
                bucket = "mitigated"
            else:
                bucket = "error"
            rows.append(
                {
                    "num": idx + 1,
                    "technique": technique,
                    "prompt_short": (prompt[:80] + "\u2026")
                    if len(prompt) > 80
                    else prompt,
                    "result": "Jailbreak"
                    if bucket == "jailbreak"
                    else "Mitigated"
                    if bucket == "mitigated"
                    else "Error",
                    "_bucket": bucket,
                    "_full_prompt": prompt,
                    "_response": response,
                    "_guardrail_side": _guardrail_side,
                    "_guardrail_explanation": _guardrail_explanation,
                    "_judge_columns": ev.get("_judge_columns", {}),
                }
            )
        return rows

    def _render_pap_goal_card(
        self, row: dict, technique_rows: list[dict], detail_mode: bool = False
    ) -> None:
        """Render a per-goal PAP result card with a per-technique table."""
        # Enrich technique_rows with pre-computed judge verdicts
        _gm = row.get("_goal_multi_metrics") or {}
        _jmeta = _gm.get("judge_meta") or getattr(
            self,
            "_history_last_judge_meta",
            {},
        )
        for tr in technique_rows:
            jc = tr.get("_judge_columns")
            if jc:
                tr["_judge_verdicts"] = self._build_judge_verdicts(jc, _jmeta)
            else:
                tr["_judge_verdicts"] = []

        with self._goal_card_shell(row, detail_mode):
            if not technique_rows:
                ui.label("No PAP technique results recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-2 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    pap_cols = [
                        {
                            "name": "technique",
                            "label": "Technique",
                            "field": "technique",
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

                    pap_tbl = (
                        ui.table(columns=pap_cols, rows=technique_rows, row_key="num")
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        pap_tbl.props(
                            f":expanded-rows='{json.dumps([r['num'] for r in technique_rows])}'"
                        )

                    pap_tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="technique" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:360px">
    {{ props.row.technique }}
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
        <span v-if="props.row._full_prompt" :data-cliptext="props.row._full_prompt||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
      </div>
      <pre v-if="props.row._full_prompt" style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                  border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prompt }}</pre>
      <div v-else class="text-caption text-italic text-grey-5 q-mb-sm">Attacker failed to generate a persuasive prompt for this technique.</div>
      <template v-if="props.row._full_prompt && props.row._guardrail_side !== 'before'">
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

                if not detail_mode:
                    self._wire_expand_toggle(body_col)
