# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TAP attack card rendering."""

from __future__ import annotations

import json
from collections import defaultdict

from nicegui import ui

from ._shared import AttackCardSharedMixin


class TapCardMixin:
    """Mixin providing TAP attack card parse + render."""

    @staticmethod
    def _parse_tap_traces(traces: list[dict]) -> tuple[list[dict], dict[int, dict]]:
        """Parse TAP traces into a list of candidate node dicts."""
        nodes: list[dict] = []
        seen_ids: set[str] = set()
        _interaction_counts: dict[int, int] = {}
        _summary_counts: dict[int, int] = {}

        def _add(node: dict) -> None:
            sid = node.get("self_id") or ""
            if sid and sid in seen_ids:
                return
            if sid:
                seen_ids.add(sid)
            nodes.append(node)

        for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
            content = td.get("content")
            if not isinstance(content, dict):
                continue

            step_name = str(content.get("step_name") or "")

            if "Depth" in step_name and "Candidate" in step_name:
                meta = content.get("metadata") or {}
                req = content.get("request") or {}
                prompt = req.get("prompt", "") if isinstance(req, dict) else ""
                resp = content.get("response")
                resp, _tap_g_side, _tap_g_expl, _tap_g_cats = (
                    AttackCardSharedMixin._extract_guardrail_from_response(resp)
                )
                response = str(resp) if resp not in (None, "") else ""
                depth_level = int(meta.get("iteration") or 0)
                _interaction_counts[depth_level] = (
                    _interaction_counts.get(depth_level, 0) + 1
                )
                _add(
                    {
                        "depth": depth_level,
                        "branch_index": meta.get("branch_index"),
                        "stream_index": meta.get("stream_index"),
                        "self_id": meta.get("self_id", ""),
                        "parent_id": meta.get("parent_id"),
                        "prompt": prompt,
                        "response": response,
                        "judge_score": meta.get("judge_score"),
                        "on_topic": meta.get("on_topic_score"),
                        "improvement": str(meta.get("improvement") or ""),
                        "_guardrail_side": _tap_g_side,
                        "_guardrail_explanation": _tap_g_expl,
                        "_guardrail_categories": _tap_g_cats,
                    }
                )
                continue

            if "Depth" in step_name and "Summary" in step_name:
                depth_level = int(content.get("depth") or 0)
                branches = [
                    b for b in (content.get("branches") or []) if isinstance(b, dict)
                ]
                _summary_counts[depth_level] = len(branches)
                for branch in branches:
                    _b_resp = branch.get("response")
                    _b_resp, _b_g_side, _b_g_expl, _b_g_cats = (
                        AttackCardSharedMixin._extract_guardrail_from_response(_b_resp)
                    )
                    _add(
                        {
                            "depth": depth_level,
                            "branch_index": branch.get("branch_index"),
                            "stream_index": branch.get("stream_index"),
                            "self_id": branch.get("self_id", ""),
                            "parent_id": branch.get("parent_id"),
                            "prompt": str(branch.get("prompt") or ""),
                            "response": str(_b_resp or ""),
                            "judge_score": branch.get("judge_score"),
                            "on_topic": branch.get("on_topic_score"),
                            "improvement": str(branch.get("improvement") or ""),
                            "_guardrail_side": _b_g_side,
                            "_guardrail_explanation": _b_g_expl,
                            "_guardrail_categories": _b_g_cats,
                        }
                    )
                continue

            if not step_name and "depth" in content and "branches" in content:
                depth_level = int(content.get("depth") or 0)
                branches = [
                    b for b in (content.get("branches") or []) if isinstance(b, dict)
                ]
                _summary_counts[depth_level] = len(branches)
                for branch in branches:
                    _b_resp2 = branch.get("response")
                    _b_resp2, _b2_g_side, _b2_g_expl, _b2_g_cats = (
                        AttackCardSharedMixin._extract_guardrail_from_response(_b_resp2)
                    )
                    _add(
                        {
                            "depth": depth_level,
                            "branch_index": branch.get("branch_index"),
                            "stream_index": branch.get("stream_index"),
                            "self_id": branch.get("self_id", ""),
                            "parent_id": branch.get("parent_id"),
                            "prompt": str(branch.get("prompt") or ""),
                            "response": str(_b_resp2 or ""),
                            "judge_score": branch.get("judge_score"),
                            "on_topic": branch.get("on_topic_score"),
                            "improvement": str(branch.get("improvement") or ""),
                            "_guardrail_side": _b2_g_side,
                            "_guardrail_explanation": _b2_g_expl,
                            "_guardrail_categories": _b2_g_cats,
                        }
                    )
                continue

        if not nodes:
            eval_idx = 0
            for td in sorted(traces, key=lambda x: x.get("sequence", 0)):
                content = td.get("content")
                if not isinstance(content, dict):
                    continue
                if content.get("step_name") != "Evaluation":
                    continue
                evaluator = str(content.get("evaluator") or "")
                if evaluator == "tracking_coordinator":
                    continue
                meta = content.get("metadata") or {}
                prompt = str(meta.get("prefix") or "")
                response = str(meta.get("completion") or "")
                if not prompt and not response:
                    continue
                score_raw = content.get("score")
                try:
                    score_val = int(float(score_raw)) if score_raw is not None else None
                except (TypeError, ValueError):
                    score_val = None
                _ev_lower = evaluator.lower()
                if score_val is not None and (
                    "harmbench" in _ev_lower or "jailbreakbench" in _ev_lower
                ):
                    score_val = 1 if score_val == 0 else 10
                eval_idx += 1
                nodes.append(
                    {
                        "depth": 0,
                        "branch_index": eval_idx - 1,
                        "stream_index": 0,
                        "self_id": "",
                        "parent_id": None,
                        "prompt": prompt,
                        "response": response,
                        "judge_score": score_val,
                        "on_topic": None,
                        "improvement": "",
                        "_guardrail_side": "",
                        "_guardrail_explanation": "",
                        "_guardrail_categories": [],
                    }
                )

        depth_stats: dict[int, dict] = {}
        all_depths = set(_interaction_counts) | set(_summary_counts)
        for _d in all_depths:
            _gen = _interaction_counts.get(_d)
            _surv = _summary_counts.get(_d)
            depth_stats[_d] = {
                "generated": _gen,
                "survived": _surv,
                "pruned": (_gen - _surv)
                if (_gen is not None and _surv is not None)
                else None,
            }

        return nodes, depth_stats

    def _render_tap_goal_card(
        self,
        row: dict,
        nodes: list[dict],
        depth_stats: dict[int, dict] | None = None,
        detail_mode: bool = False,
    ) -> None:
        """Render a TAP goal card: one table per depth."""
        with self._goal_card_shell(row, detail_mode):
            if not nodes:
                ui.label("No TAP candidate data recorded.").classes(
                    "text-sm text-grey-6"
                )
            else:
                by_depth: dict[int, list[dict]] = defaultdict(list)
                for n in nodes:
                    by_depth[n.get("depth") or 0].append(n)

                _global_num = 0
                _id_to_num: dict[str, int] = {}
                for depth_level in sorted(by_depth.keys()):
                    depth_nodes = by_depth[depth_level]
                    depth_nodes.sort(
                        key=lambda x: (
                            x.get("stream_index") or 0,
                            x.get("branch_index") or 0,
                        )
                    )
                    for n in depth_nodes:
                        _global_num += 1
                        n["_global_num"] = _global_num
                        sid = n.get("self_id") or ""
                        if sid:
                            _id_to_num[sid] = _global_num
                for n in nodes:
                    pid = n.get("parent_id") or ""
                    n["_parent_num"] = _id_to_num.get(pid)

                with ui.column().classes("w-full gap-2 mt-1") as body_col:
                    if not detail_mode:
                        body_col.set_visibility(False)

                    for depth_level in sorted(by_depth.keys()):
                        depth_nodes = by_depth[depth_level]
                        _ds = (depth_stats or {}).get(depth_level, {})
                        _n_cands = len(depth_nodes)
                        _cand_label = f"{_n_cands} candidate{'s' if _n_cands != 1 else ''} after pruning"
                        _depth_header = (
                            "Final Evaluation"
                            if depth_level == 0
                            else f"Depth {depth_level}"
                        )
                        with ui.row().classes("items-center gap-2 mt-3 mb-0.5 px-1"):
                            ui.label(_depth_header).classes(
                                "text-xs font-semibold text-grey-6 uppercase tracking-wide"
                            )
                            ui.badge(_cand_label, color="grey-5").classes("text-xs")

                        rows_data = []
                        for idx, n in enumerate(depth_nodes):
                            score = n.get("judge_score")
                            on_topic = n.get("on_topic")
                            prompt_text = n.get("prompt") or ""
                            parent_num = n.get("_parent_num")
                            _s_str = (
                                f"{int(float(score))}/10"
                                if score is not None
                                else "\u2014"
                            )
                            rows_data.append(
                                {
                                    "_num": n["_global_num"],
                                    "parent_str": str(parent_num)
                                    if parent_num is not None
                                    else "\u2014",
                                    "prompt_short": (prompt_text[:80] + "\u2026")
                                    if len(prompt_text) > 80
                                    else prompt_text or "\u2014",
                                    "score_val": float(score)
                                    if score is not None
                                    else -1,
                                    "score_str": _s_str,
                                    "on_topic_str": (
                                        "yes"
                                        if on_topic is not None
                                        and int(float(on_topic)) >= 1
                                        else "no"
                                        if on_topic is not None
                                        else "\u2014"
                                    ),
                                    "_on_topic": on_topic,
                                    "_full_prompt": prompt_text,
                                    "_response": n.get("response") or "",
                                    "_guardrail_side": n.get("_guardrail_side") or "",
                                    "_guardrail_explanation": n.get(
                                        "_guardrail_explanation"
                                    )
                                    or "",
                                }
                            )

                        columns = [
                            {
                                "name": "_num",
                                "label": "#",
                                "field": "_num",
                                "align": "center",
                                "style": "width:40px",
                            },
                            {
                                "name": "parent_str",
                                "label": "Parent",
                                "field": "parent_str",
                                "align": "center",
                                "style": "width:55px",
                            },
                            {
                                "name": "prompt_short",
                                "label": "Prompt",
                                "field": "prompt_short",
                                "align": "left",
                            },
                            {
                                "name": "on_topic_str",
                                "label": "On-topic",
                                "field": "on_topic_str",
                                "align": "center",
                                "style": "width:80px",
                            },
                            {
                                "name": "score_str",
                                "label": "Score",
                                "field": "score_str",
                                "align": "center",
                                "style": "width:80px",
                            },
                        ]

                        tbl = (
                            ui.table(columns=columns, rows=rows_data, row_key="_num")
                            .classes("w-full text-xs")
                            .props("dense flat")
                        )
                        if detail_mode:
                            tbl.props(
                                f":expanded-rows='{json.dumps([r['_num'] for r in rows_data])}'"
                            )

                        tbl.add_slot(
                            "body",
                            r"""
<q-tr :props="props" @click="props.expand = !props.expand" style="cursor:pointer">
  <q-td key="_num" :props="props" class="text-center text-grey-6">{{ props.row._num }}</q-td>
  <q-td key="parent_str" :props="props" class="text-center text-grey-5">{{ props.row.parent_str }}</q-td>
  <q-td key="prompt_short" :props="props"
        style="white-space:pre-wrap;word-break:break-word;max-width:360px">
    {{ props.row.prompt_short }}
  </q-td>
  <q-td key="on_topic_str" :props="props" class="text-center">
    <span class="text-grey-7">{{ props.row.on_topic_str }}</span>
  </q-td>
  <q-td key="score_str" :props="props" class="text-center">
    <span class="text-grey-7">{{ props.row.score_str }}</span>
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
