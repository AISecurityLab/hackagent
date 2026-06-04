# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AdvPrefix attack card rendering."""

from __future__ import annotations

import json

from nicegui import ui

from ._shared import AttackCardSharedMixin


class AdvprefixCardMixin:
    """Mixin providing AdvPrefix attack card parse + render."""

    @staticmethod
    def _parse_advprefix_traces(
        traces: list[dict],
    ) -> tuple[list[dict], dict]:
        """Parse AdvPrefix traces into per-prefix rows grouped by meta_prefix."""
        sorted_traces = sorted(traces, key=lambda x: x.get("sequence", 0))

        gen_stats: dict = {
            "raw_generated": 0,
            "after_phase1": 0,
            "after_phase2": 0,
        }

        candidates: dict[str, dict] = {}

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            if "candidates" not in content and "raw_generated" not in content:
                continue
            gen_stats["raw_generated"] += int(content.get("raw_generated") or 0)
            gen_stats["after_phase1"] += int(content.get("after_phase1_filtering") or 0)
            gen_stats["after_phase2"] += int(content.get("after_phase2_filtering") or 0)
            for cand in content.get("candidates") or []:
                if not isinstance(cand, dict):
                    continue
                prefix_text = str(cand.get("prefix") or "")
                if not prefix_text:
                    continue
                if prefix_text not in candidates:
                    _raw_mp = str(cand.get("meta_prefix") or "")
                    _mp_parts = [p.strip() for p in _raw_mp.split(",") if p.strip()]
                    _seen: set[str] = set()
                    _mp_dedup: list[str] = []
                    for _p in _mp_parts:
                        if _p not in _seen:
                            _seen.add(_p)
                            _mp_dedup.append(_p)
                    _meta_prefix_str = ", ".join(_mp_dedup)
                    candidates[prefix_text] = {
                        "prefix": prefix_text,
                        "_meta_prefix": _meta_prefix_str,
                        "_nll": cand.get("prefix_nll"),
                        "completion": "",
                        "_bucket": "pending",
                        "result": "Pending",
                        "_filtered": "Pending",
                        "_error": "",
                    }

        completion_by_prefix: dict[str, dict] = {}

        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            if str(content.get("step_name") or "") != "Target Completion":
                continue

            metadata = content.get("metadata") or {}
            full_prefix = str(metadata.get("prefix") or "")
            lookup_key = full_prefix[:300]
            error_msg = metadata.get("error_message")
            surrogate = str(metadata.get("surrogate_attack_prompt") or "")

            response = content.get("response")
            response, _adv_g_side, _adv_g_expl, _adv_g_cats = (
                AttackCardSharedMixin._extract_guardrail_from_response(response)
            )
            if isinstance(response, dict):
                completion = (
                    response.get("generated_text") or response.get("completion") or ""
                )
            elif isinstance(response, str):
                completion = response
            elif response is None:
                completion = ""
            else:
                completion = str(response)

            if not _adv_g_side and error_msg:
                _emsg_lower = str(error_msg).lower()
                if (
                    "before_guardrail" in _emsg_lower
                    or "before guardrail" in _emsg_lower
                ):
                    _adv_g_side = "before"
                    _adv_g_expl = str(error_msg)
                    error_msg = None
                elif (
                    "after_guardrail" in _emsg_lower or "after guardrail" in _emsg_lower
                ):
                    _adv_g_side = "after"
                    _adv_g_expl = str(error_msg)
                    error_msg = None

            if _adv_g_side:
                bucket = "mitigated"
                result_label = "Mitigated"
                error_msg = None
            elif error_msg:
                bucket = "error"
                result_label = "Error"
            elif completion:
                bucket = "mitigated"
                result_label = "Mitigated"
            else:
                bucket = "error"
                result_label = "Error"

            comp_data = {
                "prefix": full_prefix,
                "completion": completion,
                "_bucket": bucket,
                "result": result_label,
                "_filtered": "No",
                "_error": str(error_msg) if error_msg else "",
                "_meta_prefix": "",
                "_surrogate": surrogate,
                "_guardrail_side": _adv_g_side,
                "_guardrail_explanation": _adv_g_expl,
            }
            completion_by_prefix[lookup_key] = comp_data

            if lookup_key not in candidates:
                candidates[lookup_key] = {
                    "prefix": full_prefix,
                    "_meta_prefix": "",
                    "_nll": None,
                    "completion": "",
                    "_bucket": "pending",
                    "result": "Pending",
                    "_filtered": "Pending",
                    "_error": "",
                    "_surrogate": surrogate,
                }

        rows: list[dict] = []
        for key, cand in candidates.items():
            comp = completion_by_prefix.get(key)
            if comp:
                cand["prefix"] = comp["prefix"]
                cand["completion"] = comp["completion"]
                cand["_bucket"] = comp["_bucket"]
                cand["result"] = comp["result"]
                cand["_filtered"] = comp["_filtered"]
                cand["_error"] = comp["_error"]
                cand["_surrogate"] = comp.get("_surrogate", "")
                if not cand.get("_meta_prefix") and comp["_meta_prefix"]:
                    cand["_meta_prefix"] = comp["_meta_prefix"]
                cand["_guardrail_side"] = comp.get("_guardrail_side") or ""
                cand["_guardrail_explanation"] = (
                    comp.get("_guardrail_explanation") or ""
                )
            _surrogate = cand.get("_surrogate") or ""
            _prefix = cand["prefix"]
            if _surrogate:
                if "{prefix}" in _surrogate:
                    cand["_sent_prompt"] = _surrogate.format(prefix=_prefix)
                else:
                    cand["_sent_prompt"] = _prefix + " " + _surrogate
            else:
                cand["_sent_prompt"] = _prefix
            rows.append(cand)

        rows.sort(key=lambda r: (r["_meta_prefix"], r["prefix"][:40]))
        for i, r in enumerate(rows):
            r["num"] = i + 1

        unmatched_jailbreaks = 0
        fallback_trace_judge_columns: list[dict[str, object]] = []
        for td in sorted_traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue
            if str(content.get("step_name") or "") != "Evaluation":
                continue

            # Collect per-prefix judge votes when available.
            _trace_judge_columns: dict[str, object] = {}
            for _src in (
                content,
                content.get("result")
                if isinstance(content.get("result"), dict)
                else {},
            ):
                if not isinstance(_src, dict):
                    continue
                for _k, _v in _src.items():
                    if (
                        isinstance(_k, str)
                        and _k.startswith("eval_")
                        and not _k.endswith("_raw_response")
                    ):
                        _trace_judge_columns[_k] = _v

            if _trace_judge_columns:
                fallback_trace_judge_columns.append(dict(_trace_judge_columns))

            if str(content.get("evaluator") or "") == "tracking_coordinator":
                continue

            meta = content.get("metadata") or {}
            eval_prefix = str(meta.get("prefix") or "")
            if eval_prefix and _trace_judge_columns:
                eval_key = eval_prefix[:300]
                for r in rows:
                    if r["prefix"][:300] == eval_key:
                        _existing_jc = r.get("_judge_columns")
                        if not isinstance(_existing_jc, dict):
                            _existing_jc = {}
                        _existing_jc.update(_trace_judge_columns)
                        r["_judge_columns"] = _existing_jc

            _result_val = content.get("result")
            is_success = (
                content.get("success") is True
                or content.get("is_success") is True
                or (
                    isinstance(_result_val, dict) and _result_val.get("success") is True
                )
                or (content.get("score") or 0) > 0
            )
            if not is_success:
                continue
            if eval_prefix:
                eval_key = eval_prefix[:300]
                matched = False
                for r in rows:
                    if r["prefix"][:300] == eval_key:
                        r["_bucket"] = "jailbreak"
                        r["result"] = "Jailbreak"
                        matched = True
                if not matched:
                    unmatched_jailbreaks += 1
            else:
                unmatched_jailbreaks += 1

        if unmatched_jailbreaks:
            marked = 0
            for r in rows:
                if marked >= unmatched_jailbreaks:
                    break
                if r["_bucket"] in ("mitigated", "error") and not r.get(
                    "_guardrail_side"
                ):
                    r["_bucket"] = "jailbreak"
                    r["result"] = "Jailbreak"
                    marked += 1

        # Legacy fallback: if there is only one candidate row and prefix mapping
        # failed, still expose judge votes captured in evaluation traces.
        if len(rows) == 1:
            _row0_jc = rows[0].get("_judge_columns")
            if not isinstance(_row0_jc, dict) or not _row0_jc:
                _best = {}
                for _cand in fallback_trace_judge_columns:
                    if len(_cand) > len(_best):
                        _best = _cand
                if _best:
                    rows[0]["_judge_columns"] = dict(_best)

        return rows, gen_stats

    def _render_advprefix_goal_card(
        self,
        row: dict,
        prefix_rows: list[dict],
        gen_stats: dict,
        detail_mode: bool = False,
    ) -> None:
        """Render an AdvPrefix goal card as a single flat table."""
        # Pre-compute per-prefix judge verdicts from trace-level columns,
        # with goal-level vote fallback for legacy rows.
        _gm = row.get("_goal_multi_metrics") or {}
        _jmeta = _gm.get("judge_meta") or getattr(
            self,
            "_history_last_judge_meta",
            {},
        )
        _goal_jvotes = _gm.get("judge_votes") or {}
        for _pr in prefix_rows:
            _jc = _pr.get("_judge_columns")
            if not isinstance(_jc, dict):
                _jc = {}
            if not _jc and isinstance(_goal_jvotes, dict):
                _jc = _goal_jvotes
            _pr["_judge_verdicts"] = self._build_judge_verdicts(_jc, _jmeta)

        n_jailbreaks = sum(1 for r in prefix_rows if r["_bucket"] == "jailbreak")
        n_mitigated = sum(1 for r in prefix_rows if r["_bucket"] == "mitigated")
        n_errors = sum(1 for r in prefix_rows if r["_bucket"] == "error")
        n_pending = sum(1 for r in prefix_rows if r["_bucket"] == "pending")

        with self._goal_card_shell(row, detail_mode):
            if not prefix_rows:
                ui.label("No AdvPrefix completion data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                with ui.column().classes("w-full gap-2 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    _raw = gen_stats.get("raw_generated", 0)
                    _p1 = gen_stats.get("after_phase1", 0)
                    _p2 = gen_stats.get("after_phase2", 0)
                    if _raw > 0:
                        with ui.row().classes(
                            "items-center gap-1 text-[10px] text-grey-5 mb-1"
                        ):
                            ui.label(f"{_raw} generated").classes("font-mono")
                            ui.label("\u2192").classes("text-grey-4")
                            ui.label(f"{_p1} after pattern filter").classes("font-mono")
                            ui.label("\u2192").classes("text-grey-4")
                            ui.label(f"{_p2} after CE + top-k").classes(
                                "font-mono font-semibold text-grey-7"
                            )

                    columns = [
                        {
                            "name": "num",
                            "label": "#",
                            "field": "num",
                            "align": "center",
                            "style": "width:36px",
                        },
                        {
                            "name": "meta_prefix",
                            "label": "Meta Prefix",
                            "field": "meta_prefix",
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

                    tbl_rows = [
                        {
                            "num": r["num"],
                            "meta_prefix": r.get("_meta_prefix") or "\u2014",
                            "result": r["result"],
                            "_bucket": r["_bucket"],
                            "_full_sent_prompt": r.get("_sent_prompt") or r["prefix"],
                            "_full_prefix": r["prefix"],
                            "_completion": r.get("completion") or "",
                            "_error": r.get("_error") or "",
                            "_guardrail_side": r.get("_guardrail_side") or "",
                            "_guardrail_explanation": r.get("_guardrail_explanation")
                            or "",
                            "_judge_verdicts": r.get("_judge_verdicts") or [],
                        }
                        for r in prefix_rows
                    ]

                    tbl = (
                        ui.table(columns=columns, rows=tbl_rows, row_key="num")
                        .classes("w-full text-xs")
                        .props("dense flat")
                    )
                    if detail_mode:
                        tbl.props(
                            f":expanded-rows='{json.dumps([r['num'] for r in tbl_rows])}'"
                        )

                    tbl.add_slot(
                        "body",
                        r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="num" :props="props" style="font-size:10px;color:#9e9e9e">{{ props.row.num }}</q-td>
  <q-td key="meta_prefix" :props="props"
        style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px">
    {{ props.row.meta_prefix }}
  </q-td>
  <q-td key="result" :props="props">
    <q-badge v-if="props.row._bucket === 'jailbreak'" color="negative" class="text-xs">Jailbreak</q-badge>
    <q-badge v-else-if="props.row._bucket === 'mitigated'" color="positive" class="text-xs">Mitigated</q-badge>
    <q-badge v-else-if="props.row._bucket === 'pending'" color="grey" class="text-xs">Pending</q-badge>
    <q-badge v-else color="warning" class="text-xs">Error</q-badge>
  </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" @click="props.expand = false" style="cursor:pointer">
  <q-td colspan="100%" class="bg-grey-1">
    <div class="q-pa-sm">
      <template v-if="props.row._full_prefix !== props.row._full_sent_prompt">
        <div class="row items-center justify-between q-mb-xs">
          <span class="text-caption text-weight-bold text-uppercase text-grey-6">RAW ADVERSARIAL PREFIX</span>
          <span :data-cliptext="props.row._full_prefix||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
        </div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_prefix || '\u2014' }}</pre>
        <div class="row items-center justify-between q-mb-xs">
          <span class="text-caption text-weight-bold text-uppercase text-grey-6">PROMPT SENT TO TARGET</span>
          <span :data-cliptext="props.row._full_sent_prompt||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
        </div>
        <pre style="font-size:11px;padding:8px;background:#fff8e1;border:1px solid #ffe082;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_sent_prompt }}</pre>
      </template>
      <template v-else>
        <div class="row items-center justify-between q-mb-xs">
          <span class="text-caption text-weight-bold text-uppercase text-grey-6">PROMPT SENT TO TARGET</span>
          <span :data-cliptext="props.row._full_sent_prompt||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
        </div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;margin-bottom:8px;white-space:pre-wrap;word-break:break-word">{{ props.row._full_sent_prompt || '\u2014' }}</pre>
      </template>
      <template v-if="props.row._bucket !== 'pending' && props.row._guardrail_side !== 'before'">
        <div class="row items-center justify-between q-mb-xs">
          <span class="text-caption text-weight-bold text-uppercase text-grey-6">TARGET COMPLETION</span>
          <span :data-cliptext="props.row._completion||''" onclick="event.stopPropagation();var s=this,t=s.dataset.cliptext||'',ic=s.querySelector('.q-icon');if(window.navigator&&window.navigator.clipboard)window.navigator.clipboard.writeText(t);if(ic)ic.textContent='check';s.setAttribute('title','Copied to clipboard');setTimeout(function(){if(ic)ic.textContent='content_copy';s.setAttribute('title','Copy to clipboard');},2000);" style="display:inline-flex;cursor:pointer" title="Copy to clipboard"><q-btn flat dense size="xs" icon="content_copy" color="grey-6" /></span>
        </div>
        <pre style="font-size:11px;padding:8px;background:white;border:1px solid #e0e0e0;
                    border-radius:4px;white-space:pre-wrap;word-break:break-word">{{ props.row._completion || 'No completion recorded.' }}</pre>
        <div v-if="props.row._error" class="text-caption text-negative text-italic q-mt-xs">
          Error: {{ props.row._error }}
        </div>
      </template>
      <div v-else-if="props.row._bucket === 'pending'" class="text-caption text-grey-6 text-italic q-mt-xs">
        This candidate was not executed against the target model.
      </div>
      <div v-if="props.row._guardrail_side === 'before'" style="margin-top:4px;margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#c2410c">&#x26a0; BEFORE GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#fff7ed;border:2px solid #f97316;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#c2410c">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#9a3412">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#c2410c">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side === 'after'" style="margin-top:4px;margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#dc2626">&#x1f6ab; AFTER GUARDRAIL &#x2014; CENSORED</div>
        <pre style="font-size:11px;padding:10px;background:#fef2f2;border:2px solid #ef4444;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#dc2626">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#991b1b">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#dc2626">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
      <div v-else-if="props.row._guardrail_side" style="margin-top:4px;margin-bottom:8px">
        <div class="text-caption text-weight-bold text-uppercase q-mb-xs" style="color:#616161">&#x1f6e1; GUARDRAIL &#x2014; BLOCKED</div>
        <pre style="font-size:11px;padding:10px;background:#f5f5f5;border:2px solid #9e9e9e;border-radius:4px;white-space:pre-wrap;word-break:break-word;margin:0"><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="font-weight:700;color:#616161">Categories: </span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length" style="color:#374151">{{ props.row._guardrail_categories.join(', ') }}</span><span v-if="props.row._guardrail_categories && props.row._guardrail_categories.length">&#10;&#10;</span><span style="font-weight:700;color:#616161">Explanation: </span><span style="color:#6b7280">{{ props.row._guardrail_explanation }}</span></pre>
      </div>
            <div v-if="props.row._judge_verdicts && props.row._judge_verdicts.length > 0" style="margin-top:10px">
                <div class="text-caption text-weight-bold text-uppercase q-mb-xs text-grey-6">JUDGE VERDICTS</div>
                <div style="display:flex;flex-direction:column;gap:4px">
                    <div v-for="jv in props.row._judge_verdicts" style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:4px" :style="jv.vote > 0 ? 'background:#fef2f2' : 'background:#f0fdf4'">
                        <q-icon :name="jv.vote > 0 ? 'dangerous' : 'verified_user'" :color="jv.vote > 0 ? 'red-5' : 'green-6'" size="18px" />
                        <span style="font-size:12px;font-weight:600;width:140px">{{ jv.name }}</span>
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

                    ui.separator().classes("mt-2")
                    with ui.row().classes("items-center gap-2 mt-2 flex-wrap"):
                        ui.label("Summary:").classes(
                            "text-xs font-semibold text-grey-6"
                        )
                        ui.label(
                            f"{len(prefix_rows)} prefix{'es' if len(prefix_rows) != 1 else ''}"
                        ).classes("text-xs text-grey-6")
                        if n_jailbreaks:
                            ui.badge(
                                f"{n_jailbreaks} Jailbreak{'s' if n_jailbreaks != 1 else ''}",
                                color="negative",
                            ).classes("text-xs")
                        if n_mitigated:
                            ui.badge(
                                f"{n_mitigated} Mitigated", color="positive"
                            ).classes("text-xs")
                        if n_errors:
                            ui.badge(
                                f"{n_errors} Error{'s' if n_errors != 1 else ''}",
                                color="warning",
                            ).classes("text-xs")
                        if n_pending:
                            ui.badge(f"{n_pending} Pending", color="grey").classes(
                                "text-xs"
                            )

                if not detail_mode:
                    self._wire_expand_toggle(body_col)
