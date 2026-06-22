# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""History run results view (_open_run_history_results).

Provides ``DashboardRunHistoryResultsMixin`` for ``DashboardPage``. It builds
the results analysis view for a *historical* run, the History counterpart of
``DashboardRunResultsMixin``.

As with the run-results view, the mixin is essentially the single large
``_open_run_history_results`` coroutine and its inner helpers (per-attack
trace loaders, evaluation-label resolution, chips and the history charts).
It lives in its own module because the method is sizable and its inner
closures capture local view state.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
import json
from typing import Any
from uuid import UUID

from nicegui import ui

from hackagent.attacks.evaluator.metrics import (
    calculate_fleiss_kappa,
    calculate_majority_vote_asr,
    calculate_per_judge_asr,
    calculate_per_judge_strictness,
)

from ._helpers import (
    _eval_label,
    _format_latency,
    _rel_time,
    _result_bucket,
    _serialize,
)


class DashboardRunHistoryResultsMixin:
    """History run results view (_open_run_history_results)."""

    async def _open_run_history_results(self, run: dict) -> None:
        """Open the compact results list in a non-modal side dialog."""
        run_id_raw = str(run.get("id") or "")
        _run_num = run.get("run_progress") or run.get("run_number")

        if self.history_run_dialog_title is not None:
            _title_prefix = (
                f"Run Results — #{_run_num}"
                if _run_num
                else f"Run Results — {run_id_raw[:8]}…"
            )
            self.history_run_dialog_title.text = _title_prefix

        agent = str(run.get("agent_name") or "—")
        _hr_jailbreaks = int(run.get("successful_jailbreaks") or 0)
        _hr_errors = int(run.get("errors") or 0)
        _hr_run_latency_str = _format_latency(self._compute_run_latency_seconds(run))

        raw_run_config = run.get("run_config")
        run_config = {}
        fetched_dict = None
        if isinstance(raw_run_config, dict):
            run_config = raw_run_config
        elif isinstance(raw_run_config, str) and raw_run_config.strip():
            try:
                run_config = json.loads(raw_run_config)
            except Exception:
                run_config = raw_run_config

        if not run_config:
            with contextlib.suppress(Exception):
                fetched_run = self.backend.get_run(UUID(run_id_raw))
                fetched_dict = _serialize(fetched_run)
                fetched_raw = fetched_dict.get("run_config")
                if isinstance(fetched_raw, dict):
                    run_config = fetched_raw
                elif isinstance(fetched_raw, str) and fetched_raw.strip():
                    try:
                        run_config = json.loads(fetched_raw)
                    except Exception:
                        run_config = fetched_raw
        # Configuration panel should show ATTACK configuration (not run metrics payload).
        display_config: object = {}
        attack_id = str(run.get("attack_id") or "")
        if not attack_id and isinstance(fetched_dict, dict):
            attack_id = str(fetched_dict.get("attack_id") or "")

        if attack_id:
            with contextlib.suppress(Exception):
                attack_cfgs = self._attack_config_map_for_ids({attack_id})
                cfg = attack_cfgs.get(attack_id)
                if isinstance(cfg, dict) and cfg:
                    display_config = cfg

        if not display_config:
            if isinstance(run_config, dict):
                # Fallback: strip evaluation summary noise from run_config view.
                display_config = {
                    k: v for k, v in run_config.items() if k != "evaluation_summary"
                }
            elif run_config:
                display_config = run_config

        # Resolve attack type early (needed by the interpretation panel below).
        attack_type_str = str(run.get("attack_type") or "—")
        if attack_type_str == "—":
            _attack_id_hr = str(run.get("attack_id") or "")
            if _attack_id_hr:
                _atm_hr = self._attack_type_map_for_ids({_attack_id_hr})
                attack_type_str = _atm_hr.get(_attack_id_hr, "—")
        self._history_dialog_attack_str = attack_type_str

        if self.history_run_config_area is not None:
            self.history_run_config_area.clear()
            with self.history_run_config_area:
                _hcfg = display_config if isinstance(display_config, dict) else {}
                _hrc = run_config if isinstance(run_config, dict) else {}
                _h_evaluator_type = (
                    _hcfg.get("evaluator_type")
                    or _hrc.get("evaluator_type")
                    or "pattern"
                )
                _h_judge_cfg = (
                    _hcfg.get("judge_config") or _hrc.get("judge_config") or {}
                )
                _h_judge_model = (
                    (_h_judge_cfg.get("model_id") or _h_judge_cfg.get("model") or "")
                    if isinstance(_h_judge_cfg, dict)
                    else ""
                )
                _h_attack_str = (
                    attack_type_str
                    if attack_type_str and attack_type_str != "—"
                    else agent
                )
                _h_attack_display: dict[str, str] = {
                    "baseline": "Baseline",
                    "pair": "PAIR",
                    "tap": "TAP",
                    "bon": "Best-of-N",
                    "advprefix": "AdvPrefix",
                    "autodanturbo": "AutoDAN-Turbo",
                    "cipherchat": "CipherChat",
                    "flipattack": "FlipAttack",
                    "pap": "PAP",
                    "h4rm3l": "H4rm3l",
                    "mml": "MML",
                    "fc": "FC-Attack",
                    "tfc": "tFC-Attack",
                }

                def _h_resolve_eval_label(
                    attack: str,
                    cfg: dict,
                    ev_type: str,
                    jmodel: str,
                ) -> str:
                    if attack.lower() == "baseline":
                        if ev_type == "llm_judge":
                            return f"LLM judge{f' · {jmodel}' if jmodel else ''}"
                        if ev_type == "keyword":
                            return "Keyword matching"
                        return "Pattern matching"
                    judges = cfg.get("judges") or []
                    if isinstance(judges, list) and judges:
                        names = []
                        for j in judges:
                            if isinstance(j, dict):
                                n = (
                                    j.get("model_id")
                                    or j.get("identifier")
                                    or j.get("model")
                                    or ""
                                )
                                if n and n not in names:
                                    names.append(n)
                        if names:
                            if len(names) == 1:
                                return f"LLM judge · {names[0]}"
                            return f"LLM judges ({len(names)}): {', '.join(names)}"
                        return (
                            f"LLM judge{'s' if len(judges) > 1 else ''} × {len(judges)}"
                        )
                    if jmodel:
                        return f"LLM judge · {jmodel}"
                    return "LLM judge"

                ui.label("CONFIGURATION").classes(
                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase mb-1"
                )

                def _chip(_ic, _il, _iv):
                    with ui.row().classes(
                        "items-center gap-1 bg-grey-1 rounded px-2 py-1"
                    ):
                        ui.icon(_ic, size="xs").classes("text-grey-6")
                        ui.label(_il).classes(
                            "text-[10px] text-grey-5 font-semibold uppercase tracking-wide"
                        )
                        ui.label(_iv).classes("text-xs font-medium text-grey-9")

                # ── Line 1: Attack + attack-specific params ───────────
                _atk_lower = _h_attack_str.lower()
                with ui.row().classes("flex-wrap gap-2 items-center"):
                    _chip(
                        "flash_on",
                        "Attack",
                        _h_attack_display.get(
                            _h_attack_str.lower(), _h_attack_str.capitalize()
                        ),
                    )
                    if _atk_lower == "flipattack":
                        _fa_params = _hcfg.get("flipattack_params") or {}
                        _flip_mode = (
                            _fa_params.get("flip_mode", "FCS")
                            if isinstance(_fa_params, dict)
                            else "FCS"
                        )
                        _flip_mode_labels = {
                            "FWO": "Flip Word Order",
                            "FCW": "Flip Chars in Word",
                            "FCS": "Flip Chars in Sentence",
                            "FMM": "Fool Model Mode",
                        }
                        _chip(
                            "flip",
                            "Mode",
                            _flip_mode_labels.get(
                                str(_flip_mode).upper(), str(_flip_mode)
                            ),
                        )
                    elif _atk_lower == "h4rm3l":
                        _h4_params = _hcfg.get("h4rm3l_params") or {}
                        _h4_program = (
                            _h4_params.get("program", "")
                            if isinstance(_h4_params, dict)
                            else ""
                        )
                        if _h4_program:
                            _chip(
                                "layers",
                                "Decorators",
                                self._format_h4rm3l_program(_h4_program),
                            )
                    elif _atk_lower == "cipherchat":
                        _cc_params = _hcfg.get("cipherchat_params") or {}
                        _cc_cipher = (
                            _cc_params.get("encode_method", "—")
                            if isinstance(_cc_params, dict)
                            else "—"
                        )
                        _chip("lock", "Cipher", str(_cc_cipher))
                    elif _atk_lower == "bon":
                        _bon_params = _hcfg.get("bon_params") or {}
                        if isinstance(_bon_params, dict):
                            _chip(
                                "auto_awesome",
                                "Steps",
                                str(_bon_params.get("n_steps", 4)),
                            )
                            _chip(
                                "auto_awesome",
                                "Candidates/step",
                                str(_bon_params.get("num_concurrent_k", 5)),
                            )
                    elif _atk_lower == "tap":
                        _tap_p = _hcfg.get("tap_params") or {}
                        if isinstance(_tap_p, dict):
                            _chip("account_tree", "Depth", str(_tap_p.get("depth", 3)))
                            _chip("width", "Width", str(_tap_p.get("width", 4)))
                            _chip(
                                "call_split",
                                "Branching",
                                str(_tap_p.get("branching_factor", 3)),
                            )
                    elif _atk_lower == "mml":
                        _mml_params = _hcfg.get("mml_params") or {}
                        if isinstance(_mml_params, dict):
                            _mml_enc = _mml_params.get("encoding_mode", "")
                            if _mml_enc:
                                _chip("image", "Encoding", str(_mml_enc))
                    elif _atk_lower in ("fc", "tfc"):
                        _fc_params = (
                            _hcfg.get("fc_params") or _hcfg.get("tfc_params") or {}
                        )
                        if isinstance(_fc_params, dict):
                            _fc_layout = _fc_params.get("layout", "")
                            if _fc_layout:
                                _chip("account_tree", "Layout", str(_fc_layout))
                            _fc_steps = _fc_params.get("num_steps", "")
                            if _fc_steps:
                                _chip("format_list_numbered", "Steps", str(_fc_steps))
                            if _atk_lower == "tfc":
                                _fc_tfmt = _fc_params.get("text_format", "ascii")
                                _chip("text_fields", "Format", str(_fc_tfmt))
                # ── Line 2: Dataset ───────────────────────────────────
                _h_dataset_raw = _hcfg.get("dataset") or _hrc.get("dataset")
                if _h_dataset_raw is not None:
                    if isinstance(_h_dataset_raw, dict):
                        _h_ds_preset = _h_dataset_raw.get("preset") or ""
                        if _h_ds_preset:
                            _h_dataset_str = _h_ds_preset.replace("_", " ").title()
                        else:
                            _h_ds_desc = _h_dataset_raw.get("description") or ""
                            if _h_ds_desc:
                                _h_dataset_str = _h_ds_desc.split(" - ")[0].strip()
                            else:
                                _h_ds_path = _h_dataset_raw.get("path") or ""
                                _h_dataset_str = (
                                    _h_ds_path.rsplit("/", 1)[-1]
                                    if "/" in _h_ds_path
                                    else _h_ds_path or "Custom"
                                )
                    else:
                        _h_dataset_str = str(_h_dataset_raw)
                    if _h_dataset_str:
                        _h_ds_limit = (
                            _h_dataset_raw.get("limit")
                            if isinstance(_h_dataset_raw, dict)
                            else None
                        )
                        _h_ds_shuffle = (
                            _h_dataset_raw.get("shuffle")
                            if isinstance(_h_dataset_raw, dict)
                            else None
                        )
                        with ui.row().classes("flex-wrap gap-2 items-center mt-1"):
                            _chip("dataset", "Dataset", _h_dataset_str)
                            if _h_ds_limit is not None:
                                _chip("filter_list", "Limit", str(_h_ds_limit))
                            if _h_ds_shuffle is not None:
                                _chip("shuffle", "Shuffle", str(_h_ds_shuffle))

                # ── Line 3: Roles (Target, Judge/Scorer, Attacker, Generator, Decorator, …) ──
                with ui.row().classes("flex-wrap gap-2 items-center mt-1"):
                    _chip("smart_toy", "Target", agent)
                    _h_atk_lower_r = _h_attack_str.lower()
                    # PAIR / AutoDAN: scorer IS the judge — show Scorer, not Judge
                    if _h_atk_lower_r in ("pair", "autodanturbo"):
                        _h_scorer_cfg = _hcfg.get("scorer") or {}
                        if isinstance(_h_scorer_cfg, dict):
                            _h_scorer_id = (
                                _h_scorer_cfg.get("identifier")
                                or _h_scorer_cfg.get("model_id")
                                or ""
                            )
                            if _h_scorer_id:
                                _chip("analytics", "Scorer", str(_h_scorer_id))
                    else:
                        _chip(
                            "gavel",
                            "Judge",
                            _h_resolve_eval_label(
                                _h_attack_str, _hcfg, _h_evaluator_type, _h_judge_model
                            ),
                        )
                    # TAP: optional separate on-topic judge
                    if _h_atk_lower_r == "tap":
                        _h_ot_judge_cfg = _hcfg.get("on_topic_judge")
                        if isinstance(_h_ot_judge_cfg, dict):
                            _h_ot_id = (
                                _h_ot_judge_cfg.get("identifier")
                                or _h_ot_judge_cfg.get("model_id")
                                or ""
                            )
                            if _h_ot_id:
                                _chip("fact_check", "On-Topic Judge", str(_h_ot_id))
                    # Attacker LLM
                    _h_attacker_cfg = _hcfg.get("attacker") or {}
                    if isinstance(_h_attacker_cfg, dict):
                        _h_attacker_id = (
                            _h_attacker_cfg.get("identifier")
                            or _h_attacker_cfg.get("model_id")
                            or ""
                        )
                        if _h_attacker_id:
                            _chip("psychology", "Attacker", str(_h_attacker_id))
                    # AdvPrefix: generator role
                    if _h_atk_lower_r == "advprefix":
                        _h_gen_cfg = _hcfg.get("generator") or {}
                        if isinstance(_h_gen_cfg, dict):
                            _h_gen_id = (
                                _h_gen_cfg.get("identifier")
                                or _h_gen_cfg.get("model_id")
                                or ""
                            )
                            if _h_gen_id:
                                _chip("build", "Generator", str(_h_gen_id))
                    # AutoDAN: Summarizer + Embedder
                    if _h_atk_lower_r == "autodanturbo":
                        _h_summarizer_cfg = _hcfg.get("summarizer") or {}
                        if isinstance(_h_summarizer_cfg, dict):
                            _h_summarizer_id = (
                                _h_summarizer_cfg.get("identifier")
                                or _h_summarizer_cfg.get("model_id")
                                or ""
                            )
                            if _h_summarizer_id:
                                _chip("summarize", "Summarizer", str(_h_summarizer_id))
                        _h_embedder_cfg = _hcfg.get("embedder") or {}
                        if isinstance(_h_embedder_cfg, dict):
                            _h_embedder_id = (
                                _h_embedder_cfg.get("identifier")
                                or _h_embedder_cfg.get("model_id")
                                or ""
                            )
                            if _h_embedder_id:
                                _chip("hub", "Embedder", str(_h_embedder_id))
                    # h4rm3l: decorator LLM
                    if _h_atk_lower_r == "h4rm3l":
                        _h4_p = _hcfg.get("h4rm3l_params") or {}
                        _h_dec_llm_cfg = (
                            _h4_p.get("decorator_llm")
                            if isinstance(_h4_p, dict)
                            else None
                        ) or _hcfg.get("decorator_llm")
                        if isinstance(_h_dec_llm_cfg, dict):
                            _h_dec_id = (
                                _h_dec_llm_cfg.get("identifier")
                                or _h_dec_llm_cfg.get("model_id")
                                or ""
                            )
                            if _h_dec_id:
                                _chip("layers", "Decorator LLM", str(_h_dec_id))

                # ── Line 4: Guardrails (if present) ───────────────────
                _h_bg = _hrc.get("before_guardrail")
                _h_ag = _hrc.get("after_guardrail")
                if _h_bg or _h_ag:
                    with ui.row().classes("flex-wrap gap-2 items-center mt-1"):
                        if _h_bg:
                            _h_bg_id = (
                                _h_bg.get("identifier", "—")
                                if isinstance(_h_bg, dict)
                                else str(_h_bg)
                            )
                            _chip("shield", "Before Guardrail", _h_bg_id)
                        if _h_ag:
                            _h_ag_id = (
                                _h_ag.get("identifier", "—")
                                if isinstance(_h_ag, dict)
                                else str(_h_ag)
                            )
                            _chip("shield", "After Guardrail", _h_ag_id)

        if self.history_results_list_area is not None:
            self.history_results_list_area.clear()
        if self.history_results_empty_label is not None:
            self.history_results_empty_label.text = "Loading results…"
            self.history_results_empty_label.set_visibility(True)

        self._history_current_run = run

        self._open_runs_bottom_panel()

        await asyncio.sleep(0)

        try:
            run_uuid = UUID(run_id_raw)

            def _fetch_results():
                items = []
                page = 1
                while True:
                    rp = self.backend.list_results(
                        run_id=run_uuid, page=page, page_size=100
                    )
                    items.extend(rp.items)
                    if len(items) >= rp.total or not rp.items:
                        break
                    page += 1
                return items

            all_items = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_results
            )

            sorted_items = sorted(
                all_items,
                key=lambda item: (
                    int(getattr(item, "goal_index", 0)),
                    getattr(item, "created_at", None),
                ),
            )

            new_rows = []
            for idx, r in enumerate(sorted_items, start=1):
                d = _serialize(r)
                d["_rel"] = _rel_time(d.get("created_at"))
                d["goal_number"] = idx
                d["_goal_category"] = self._extract_goal_classifier_label(d, "category")
                d["_goal_subcategory"] = self._extract_goal_classifier_label(
                    d, "subcategory"
                )
                d["evaluation_label"] = _eval_label(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["evaluation_notes"] = d.get("evaluation_notes") or "—"
                d["_goal_latency_s"] = self._extract_goal_latency_seconds(d)
                d["_goal_latency"] = _format_latency(d.get("_goal_latency_s"))
                bucket = _result_bucket(
                    d.get("evaluation_status", ""), d.get("evaluation_notes")
                )
                d["_bucket"] = bucket
                new_rows.append(d)

            # ── Enrich rows with per-goal multi-judge verdicts ──────
            _hr_eval_summary: dict = {}
            if isinstance(run_config, dict):
                _es = run_config.get("evaluation_summary")
                if isinstance(_es, dict):
                    _hr_eval_summary = _es
            if not _hr_eval_summary:
                _hr_eval_summary = self._extract_run_evaluation_summary(run)
            _hr_is_multi = bool(_hr_eval_summary.get("is_multi_judge")) or (
                int(_hr_eval_summary.get("judge_count") or 0) > 1
            )
            if not _hr_is_multi:
                _hr_vc: set[str] = set()
                for _hr_r in new_rows:
                    _hr_vc.update(self._extract_eval_votes_from_result(_hr_r).keys())
                if len(_hr_vc) > 1:
                    _hr_is_multi = True
            if not _hr_is_multi:
                _hr_acfg = display_config if isinstance(display_config, dict) else {}
                _hr_jl = _hr_acfg.get("judges") or []
                if isinstance(_hr_jl, list) and len(_hr_jl) > 1:
                    _hr_is_multi = True
            if not _hr_is_multi and _hr_eval_summary:
                _hr_pja_check = _hr_eval_summary.get("per_judge_asr")
                if isinstance(_hr_pja_check, dict) and len(_hr_pja_check) > 1:
                    _hr_is_multi = True

            # Build judge metadata mapping: eval_key -> {id, name, type}
            _hr_judge_meta: dict[str, dict[str, Any]] = {}
            _hr_acfg2 = display_config if isinstance(display_config, dict) else {}
            _hr_jl2 = _hr_acfg2.get("judges") or []
            _hr_judge_meta, _ = self._build_judge_metadata(_hr_jl2)

            # Keep the latest judge metadata so the right panel can
            # reuse the exact same name/type mapping as the left panel
            # even when row-level metadata is missing in legacy runs.
            self._history_last_judge_meta = _hr_judge_meta

            for _hr_d in new_rows:
                _hr_d["_is_multi_judge"] = False
                _hr_d["_goal_multi_metrics"] = {}
                if _hr_is_multi:
                    _hr_gm = self._compute_goal_multi_judge_metrics(_hr_d)
                    if not _hr_gm:
                        _hr_pgm = _hr_eval_summary.get("per_goal_metrics")
                        if isinstance(_hr_pgm, dict):
                            _hr_gt = str(_hr_d.get("goal") or "")
                            _hr_gpgm = _hr_pgm.get(_hr_gt)
                            if isinstance(_hr_gpgm, dict):
                                _hr_pja = _hr_gpgm.get("per_judge_asr")
                                if isinstance(_hr_pja, dict) and _hr_pja:
                                    _hr_votes = {
                                        k: int(float(v) >= 0.5)
                                        for k, v in _hr_pja.items()
                                    }
                                    _hr_javg = (
                                        sum(_hr_votes.values()) / len(_hr_votes)
                                        if _hr_votes
                                        else None
                                    )
                                    _hr_gm = {
                                        "judge_count": len(_hr_votes),
                                        "judge_votes": dict(sorted(_hr_votes.items())),
                                        "judge_avg": _hr_javg,
                                        "majority_vote_asr": _hr_javg,
                                    }
                    if _hr_gm:
                        if _hr_judge_meta:
                            _hr_gm["judge_meta"] = _hr_judge_meta
                        _hr_d["_is_multi_judge"] = True
                        _hr_d["_goal_multi_metrics"] = _hr_gm

            # Pre-fetch traces for Baseline / BoN views
            baseline_traces_map_hr: dict[str, list[dict]] = {}
            if attack_type_str.lower() == "baseline" and new_rows:
                _hr_ids = [str(r.get("id") or "") for r in new_rows if r.get("id")]

                def _load_hr_traces() -> dict[str, list[dict]]:
                    _res: dict[str, list[dict]] = {}
                    for _rid in _hr_ids:
                        try:
                            _ts = self.backend.list_traces(result_id=UUID(_rid))
                            _res[_rid] = [_serialize(t) for t in _ts]
                        except Exception:
                            _res[_rid] = []
                    return _res

                baseline_traces_map_hr = await asyncio.get_event_loop().run_in_executor(
                    None, _load_hr_traces
                )

            bon_traces_map_hr: dict[str, list[dict]] = {}
            if attack_type_str.lower() == "bon" and new_rows:
                _bon_hr_ids = [str(r.get("id") or "") for r in new_rows if r.get("id")]

                def _load_bon_hr_traces() -> dict[str, list[dict]]:
                    _res: dict[str, list[dict]] = {}
                    for _rid in _bon_hr_ids:
                        try:
                            _ts = self.backend.list_traces(result_id=UUID(_rid))
                            _res[_rid] = [_serialize(t) for t in _ts]
                        except Exception:
                            _res[_rid] = []
                    return _res

                bon_traces_map_hr = await asyncio.get_event_loop().run_in_executor(
                    None, _load_bon_hr_traces
                )

            generic_traces_map_hr: dict[str, list[dict]] = {}
            if attack_type_str.lower() not in ("baseline", "bon") and new_rows:
                _gen_hr_ids = [str(r.get("id") or "") for r in new_rows if r.get("id")]

                def _load_gen_hr_traces() -> dict[str, list[dict]]:
                    _res: dict[str, list[dict]] = {}
                    for _rid in _gen_hr_ids:
                        try:
                            _ts = self.backend.list_traces(result_id=UUID(_rid))
                            _res[_rid] = [_serialize(t) for t in _ts]
                        except Exception:
                            _res[_rid] = []
                    return _res

                generic_traces_map_hr = await asyncio.get_event_loop().run_in_executor(
                    None, _load_gen_hr_traces
                )

            if self.history_results_list_area is not None:
                self.history_results_list_area.clear()

            if self.history_detail_area is not None:
                self.history_detail_area.clear()
                with self.history_detail_area:
                    ui.label("← Select a goal to view details").classes(
                        "text-grey-4 text-sm italic mt-16 w-full text-center"
                    )

            if self.history_results_empty_label is not None:
                if all_items:
                    self.history_results_empty_label.set_visibility(False)
                else:
                    self.history_results_empty_label.text = (
                        "No results found for this run."
                    )
                    self.history_results_empty_label.set_visibility(True)

            # ── Populate charts area (before goals) ───────────────────
            if self.history_charts_area is not None and new_rows:
                self.history_charts_area.clear()
                _n_jailbreaks = sum(
                    1 for r in new_rows if r.get("_bucket") == "jailbreak"
                )
                _n_mitigated = sum(
                    1 for r in new_rows if r.get("_bucket") == "mitigated"
                )
                _n_errors = sum(1 for r in new_rows if r.get("_bucket") == "failed")
                _total = len(new_rows)
                _asr = (100.0 * _n_jailbreaks / _total) if _total > 0 else 0.0
                _robustness = 100.0 - _asr
                _risk_hex = (
                    "#ef4444"
                    if _asr >= 70
                    else "#f97316"
                    if _asr >= 40
                    else "#eab308"
                    if _asr >= 10
                    else "#22c55e"
                )
                _risk_label = (
                    "Critical"
                    if _asr >= 70
                    else "High"
                    if _asr >= 40
                    else "Medium"
                    if _asr >= 10
                    else "Low"
                )
                _no_data = _total == 0

                with self.history_charts_area:
                    # ── Risk donut + Robustness side by side ───────────
                    with ui.row().classes("w-full flex-wrap gap-4 items-stretch"):
                        # Risk donut
                        with ui.card().classes("flex-1 min-w-64"):
                            _hrs_chart_ref: list = []

                            async def _dl_hrs():
                                if _hrs_chart_ref:
                                    await self._download_echart_svg(
                                        _hrs_chart_ref[0],
                                        f"risk_score_run{run_id_raw[:8]}",
                                    )

                            with ui.row().classes(
                                "items-center justify-between w-full"
                            ):
                                ui.label("Risk Score").classes("font-semibold text-sm")
                                ui.button(icon="download", on_click=_dl_hrs).props(
                                    "flat dense size=xs color=grey-6"
                                )
                            ui.label("Attack Success Rate across all tests").classes(
                                "text-xs text-grey-6 mb-3"
                            )
                            with ui.row().classes("items-center gap-6 flex-wrap"):
                                _hrs_chart_ref.append(
                                    ui.echart(
                                        {
                                            "series": [
                                                {
                                                    "type": "pie",
                                                    "radius": ["58%", "80%"],
                                                    "data": (
                                                        [
                                                            {
                                                                "value": 1,
                                                                "name": "No data",
                                                                "itemStyle": {
                                                                    "color": "#94a3b8"
                                                                },
                                                            }
                                                        ]
                                                        if _no_data
                                                        else [
                                                            {
                                                                "value": _n_jailbreaks,
                                                                "name": "Jailbreaks",
                                                                "itemStyle": {
                                                                    "color": "#ef4444"
                                                                },
                                                            },
                                                            {
                                                                "value": _n_mitigated,
                                                                "name": "Mitigated",
                                                                "itemStyle": {
                                                                    "color": "#22c55e"
                                                                },
                                                            },
                                                            {
                                                                "value": _n_errors,
                                                                "name": "Errors",
                                                                "itemStyle": {
                                                                    "color": "#f97316"
                                                                },
                                                            },
                                                            {
                                                                "value": max(
                                                                    0,
                                                                    _total
                                                                    - _n_jailbreaks
                                                                    - _n_mitigated
                                                                    - _n_errors,
                                                                ),
                                                                "name": "Pending",
                                                                "itemStyle": {
                                                                    "color": "#94a3b8"
                                                                },
                                                            },
                                                        ]
                                                    ),
                                                    "label": {"show": False},
                                                    "emphasis": {"scale": False},
                                                }
                                            ],
                                            "graphic": (
                                                []
                                                if _no_data
                                                else [
                                                    {
                                                        "type": "group",
                                                        "left": "center",
                                                        "top": "center",
                                                        "children": [
                                                            {
                                                                "type": "text",
                                                                "style": {
                                                                    "text": f"{_asr:.0f}%",
                                                                    "textAlign": "center",
                                                                    "fontSize": 22,
                                                                    "fontWeight": "bold",
                                                                    "fill": _risk_hex,
                                                                },
                                                                "top": -14,
                                                            },
                                                            {
                                                                "type": "text",
                                                                "style": {
                                                                    "text": _risk_label,
                                                                    "textAlign": "center",
                                                                    "fontSize": 11,
                                                                    "fill": _risk_hex,
                                                                },
                                                                "top": 12,
                                                            },
                                                        ],
                                                    }
                                                ]
                                            ),
                                            "tooltip": {
                                                "trigger": "item"
                                                if not _no_data
                                                else "none"
                                            },
                                        }
                                    )
                                    .classes("w-36 h-36 shrink-0")
                                    .props("renderer=svg")
                                )

                                # Legend
                                with ui.column().classes("gap-1"):
                                    for _leg_l, _leg_c, _leg_clr in [
                                        ("Jailbreaks", _n_jailbreaks, "#ef4444"),
                                        ("Mitigated", _n_mitigated, "#22c55e"),
                                        ("Errors", _n_errors, "#f97316"),
                                        (
                                            "Pending",
                                            max(
                                                0,
                                                _total
                                                - _n_jailbreaks
                                                - _n_mitigated
                                                - _n_errors,
                                            ),
                                            "#94a3b8",
                                        ),
                                    ]:
                                        if _leg_c > 0 or not _no_data:
                                            with ui.row().classes("items-center gap-2"):
                                                ui.element("div").classes(
                                                    "w-2.5 h-2.5 rounded-full shrink-0"
                                                ).style(f"background:{_leg_clr}")
                                                ui.label(f"{_leg_l}: {_leg_c}").classes(
                                                    "text-xs"
                                                )

                        # Robustness bar
                        with ui.card().classes("flex-1 min-w-64"):
                            ui.label("Robustness").classes("font-semibold text-sm mb-1")
                            ui.label("Percentage of tests the agent resisted").classes(
                                "text-xs text-grey-6 mb-3"
                            )
                            with ui.column().classes("gap-3 w-full"):
                                with ui.row().classes("items-end gap-2"):
                                    ui.label(f"{_robustness:.0f}%").classes(
                                        "text-4xl font-bold"
                                    )
                                    _rob_color = (
                                        "positive"
                                        if _robustness >= 80
                                        else "warning"
                                        if _robustness >= 50
                                        else "negative"
                                    )
                                    _rob_word = (
                                        "Strong"
                                        if _robustness >= 80
                                        else "Moderate"
                                        if _robustness >= 50
                                        else "Weak"
                                    )
                                    ui.badge(_rob_word, color=_rob_color).classes(
                                        "text-xs mb-1"
                                    )
                                ui.linear_progress(
                                    value=_robustness / 100.0,
                                    show_value=False,
                                    color=_rob_color,
                                ).classes("w-full").props("rounded size=12px")
                                with ui.row().classes("w-full justify-between"):
                                    ui.label(f"{_n_mitigated} mitigated").classes(
                                        "text-xs text-grey-6"
                                    )
                                    ui.label(f"{_n_jailbreaks} vulnerable").classes(
                                        "text-xs text-grey-6"
                                    )

                    # ── Category radar (if categories exist) ──────────
                    _hc_cat_stats: dict[str, dict[str, int]] = defaultdict(
                        lambda: {
                            "total": 0,
                            "vulnerable": 0,
                            "mitigated": 0,
                            "errors": 0,
                        }
                    )
                    for _row in new_rows:
                        _cat = _row.get("_goal_category") or ""
                        if not _cat or _cat == "N/A":
                            continue
                        _bkt = _row.get("_bucket", "pending")
                        _entry = _hc_cat_stats[_cat]
                        _entry["total"] += 1
                        if _bkt == "jailbreak":
                            _entry["vulnerable"] += 1
                        elif _bkt == "mitigated":
                            _entry["mitigated"] += 1
                        elif _bkt == "failed":
                            _entry["errors"] += 1

                    if _hc_cat_stats:
                        _hc_items = []
                        for _lbl, _sts in _hc_cat_stats.items():
                            _t = int(_sts.get("total") or 0)
                            _v = int(_sts.get("vulnerable") or 0)
                            if _t <= 0:
                                continue
                            _hc_items.append(
                                {
                                    "label": _lbl,
                                    "total": _t,
                                    "vulnerable": _v,
                                    "mitigated": int(_sts.get("mitigated") or 0),
                                    "errors": int(_sts.get("errors") or 0),
                                    "robustness": 100.0 * (_t - _v) / _t,
                                }
                            )
                        _hc_items.sort(key=lambda x: x["label"], reverse=True)
                        if _hc_items:
                            with ui.column().classes("w-full gap-3"):
                                with ui.card().classes("w-full"):
                                    _hcb_chart_ref: list = []

                                    async def _dl_hcb():
                                        if _hcb_chart_ref:
                                            await self._download_echart_svg(
                                                _hcb_chart_ref[0],
                                                f"category_breakdown_run{run_id_raw[:8]}",
                                            )

                                    with ui.row().classes(
                                        "items-center justify-between w-full"
                                    ):
                                        ui.label("Vulnerability by Category").classes(
                                            "font-semibold text-sm"
                                        )
                                        ui.button(
                                            icon="download", on_click=_dl_hcb
                                        ).props("flat dense size=xs color=grey-6")
                                    _hc_labels = [x["label"] for x in _hc_items]
                                    _hc_vuln = [x["vulnerable"] for x in _hc_items]
                                    _hc_mit = [x["mitigated"] for x in _hc_items]
                                    _hc_err = [x["errors"] for x in _hc_items]
                                    _hcb_chart_ref.append(
                                        ui.echart(
                                            {
                                                "tooltip": {"trigger": "axis"},
                                                "legend": {
                                                    "data": [
                                                        "Vulnerable",
                                                        "Mitigated",
                                                        "Errors",
                                                    ],
                                                    "bottom": 0,
                                                },
                                                "grid": {
                                                    "left": "3%",
                                                    "right": "4%",
                                                    "top": "3%",
                                                    "bottom": "14%",
                                                    "containLabel": True,
                                                },
                                                "xAxis": {"type": "value"},
                                                "yAxis": {
                                                    "type": "category",
                                                    "data": _hc_labels,
                                                    "axisLabel": {
                                                        "width": 140,
                                                        "overflow": "truncate",
                                                    },
                                                },
                                                "series": [
                                                    {
                                                        "name": "Vulnerable",
                                                        "type": "bar",
                                                        "stack": "total",
                                                        "data": _hc_vuln,
                                                        "itemStyle": {
                                                            "color": "#ef4444"
                                                        },
                                                    },
                                                    {
                                                        "name": "Mitigated",
                                                        "type": "bar",
                                                        "stack": "total",
                                                        "data": _hc_mit,
                                                        "itemStyle": {
                                                            "color": "#22c55e"
                                                        },
                                                    },
                                                    {
                                                        "name": "Errors",
                                                        "type": "bar",
                                                        "stack": "total",
                                                        "data": _hc_err,
                                                        "itemStyle": {
                                                            "color": "#f97316"
                                                        },
                                                    },
                                                ],
                                            }
                                        )
                                        .classes("w-full h-72")
                                        .props("renderer=svg")
                                    )

                                # Radar chart (only when 3+ categories)
                                if len(_hc_items) >= 3:
                                    _hc_top = _hc_items[:9]
                                    _hc_top.sort(key=lambda x: x["label"])
                                    _hc_indicators = [
                                        {"name": x["label"], "max": 100}
                                        for x in _hc_top
                                    ]
                                    _hc_values = [
                                        round(x["robustness"], 1) for x in _hc_top
                                    ]

                                    with ui.card().classes("w-full"):
                                        _hcr_chart_ref: list = []

                                        async def _dl_hcr():
                                            if _hcr_chart_ref:
                                                await self._download_echart_svg(
                                                    _hcr_chart_ref[0],
                                                    f"robustness_radar_run{run_id_raw[:8]}",
                                                )

                                        with ui.row().classes(
                                            "items-center justify-between w-full"
                                        ):
                                            ui.label("Robustness by Category").classes(
                                                "font-semibold text-sm"
                                            )
                                            ui.button(
                                                icon="download", on_click=_dl_hcr
                                            ).props("flat dense size=xs color=grey-6")
                                        with ui.row().classes("w-full justify-center"):
                                            _hcr_chart_ref.append(
                                                ui.echart(
                                                    {
                                                        "radar": {
                                                            "shape": "polygon",
                                                            "indicator": _hc_indicators,
                                                            "splitNumber": 5,
                                                            "center": ["50%", "52%"],
                                                            "radius": "64%",
                                                            "axisName": {
                                                                "fontSize": 11,
                                                                "color": "#374151",
                                                            },
                                                            "splitLine": {
                                                                "lineStyle": {
                                                                    "color": "#d1d5db"
                                                                }
                                                            },
                                                            "splitArea": {
                                                                "areaStyle": {
                                                                    "color": ["#ffffff"]
                                                                }
                                                            },
                                                        },
                                                        "series": [
                                                            {
                                                                "type": "radar",
                                                                "symbol": "circle",
                                                                "symbolSize": 8,
                                                                "itemStyle": {
                                                                    "color": "#22c55e"
                                                                },
                                                                "lineStyle": {
                                                                    "color": "#22c55e",
                                                                    "width": 2,
                                                                },
                                                                "areaStyle": {
                                                                    "color": "rgba(34,197,94,0.15)"
                                                                },
                                                                "data": [
                                                                    {
                                                                        "value": _hc_values,
                                                                        "name": "Robustness",
                                                                    }
                                                                ],
                                                            }
                                                        ],
                                                        "tooltip": {"trigger": "item"},
                                                    }
                                                )
                                                .classes("w-full h-72")
                                                .props("renderer=svg")
                                            )

            # ── Populate multi-judge statistics panel ─────────────────
            if self.history_multi_judge_panel is not None:
                self.history_multi_judge_panel.clear()
                # Compute multi-judge data — use already-resolved run_config
                _mj_eval_summary: dict = {}
                if isinstance(run_config, dict):
                    _es = run_config.get("evaluation_summary")
                    if isinstance(_es, dict):
                        _mj_eval_summary = _es
                if not _mj_eval_summary:
                    _mj_eval_summary = self._extract_run_evaluation_summary(run)
                _mj_judge_count = int(_mj_eval_summary.get("judge_count") or 0)
                _mj_is_multi = bool(_mj_eval_summary.get("is_multi_judge")) or (
                    _mj_judge_count > 1
                )
                # Also check actual vote columns in results
                _mj_vote_columns: set[str] = set()
                for _mj_row in new_rows:
                    _mj_vote_columns.update(
                        self._extract_eval_votes_from_result(_mj_row).keys()
                    )
                if len(_mj_vote_columns) > 1:
                    _mj_is_multi = True
                # Fallback: check attack config judges array
                if not _mj_is_multi:
                    _mj_attack_cfg = (
                        display_config if isinstance(display_config, dict) else {}
                    )
                    _mj_judges_list = _mj_attack_cfg.get("judges") or []
                    if isinstance(_mj_judges_list, list) and len(_mj_judges_list) > 1:
                        _mj_is_multi = True
                        _mj_judge_count = len(_mj_judges_list)
                # Fallback: check per_judge_asr has multiple keys
                if not _mj_is_multi and _mj_eval_summary:
                    _mj_pja_check = _mj_eval_summary.get("per_judge_asr")
                    if isinstance(_mj_pja_check, dict) and len(_mj_pja_check) > 1:
                        _mj_is_multi = True

                if _mj_is_multi:
                    # Build vote rows for metric computation
                    _mj_vote_rows: list[dict[str, int]] = []
                    for _mj_row in new_rows:
                        _mj_votes = self._extract_eval_votes_from_result(_mj_row)
                        if not _mj_votes:
                            _mj_gm_row = _mj_row.get("_goal_multi_metrics")
                            if isinstance(_mj_gm_row, dict):
                                _mj_gv = _mj_gm_row.get("judge_votes")
                                if isinstance(_mj_gv, dict) and _mj_gv:
                                    _mj_votes = {
                                        _k: self._coerce_binary_vote(_v)
                                        for _k, _v in _mj_gv.items()
                                        if self._is_canonical_eval_vote_key(_k)
                                    }
                        if not _mj_votes:
                            _mj_rid = str(_mj_row.get("id") or "")
                            _mj_traces = generic_traces_map_hr.get(_mj_rid, [])
                            _mj_trace_votes: dict[str, int] = {}
                            for _mj_td in _mj_traces:
                                _mj_content = _mj_td.get("content")
                                if not isinstance(_mj_content, dict):
                                    continue
                                if (
                                    str(_mj_content.get("step_name") or "")
                                    != "Evaluation"
                                ):
                                    continue
                                for _mj_src in (
                                    _mj_content,
                                    _mj_content.get("result")
                                    if isinstance(_mj_content.get("result"), dict)
                                    else {},
                                ):
                                    if not isinstance(_mj_src, dict):
                                        continue
                                    for _mj_k, _mj_v in _mj_src.items():
                                        if not self._is_canonical_eval_vote_key(_mj_k):
                                            continue
                                        if _mj_v is None:
                                            continue
                                        _mj_trace_votes[_mj_k] = (
                                            self._coerce_binary_vote(_mj_v)
                                        )
                            if _mj_trace_votes:
                                _mj_votes = dict(sorted(_mj_trace_votes.items()))
                        if _mj_votes:
                            _mj_vote_rows.append(dict(_mj_votes))

                    # Compute metrics
                    _mj_majority_asr = self._safe_float(
                        _mj_eval_summary.get("majority_vote_asr")
                    ) or self._safe_float(
                        _mj_eval_summary.get("overall_majority_vote_asr")
                    )
                    if _mj_majority_asr is None and _mj_vote_rows:
                        _mj_majority_asr = calculate_majority_vote_asr(_mj_vote_rows)

                    _mj_fleiss = self._safe_float(
                        _mj_eval_summary.get("fleiss_kappa")
                    ) or self._safe_float(_mj_eval_summary.get("overall_fleiss_kappa"))
                    if _mj_fleiss is None and _mj_vote_rows:
                        _mj_fleiss = calculate_fleiss_kappa(_mj_vote_rows)

                    _mj_per_judge_asr = _mj_eval_summary.get("per_judge_asr")
                    if (
                        not isinstance(_mj_per_judge_asr, dict) or not _mj_per_judge_asr
                    ) and _mj_vote_rows:
                        _mj_per_judge_asr = calculate_per_judge_asr(_mj_vote_rows)

                    _mj_strictness = _mj_eval_summary.get("per_judge_strictness")
                    if (
                        not isinstance(_mj_strictness, dict)
                        or not any(k != "bias_gap" for k in _mj_strictness.keys())
                    ) and _mj_vote_rows:
                        _mj_strictness = calculate_per_judge_strictness(_mj_vote_rows)

                    # Build judge metadata mapping: eval_key -> {name, type}
                    _mj_attack_cfg = (
                        display_config if isinstance(display_config, dict) else {}
                    )
                    _mj_judges_cfg_list = _mj_attack_cfg.get("judges") or []
                    _mj_judge_meta, _mj_declared_eval_keys = self._build_judge_metadata(
                        _mj_judges_cfg_list
                    )

                    with self.history_multi_judge_panel:
                        with ui.card().classes("w-full"):
                            # Compute judge keys early for accurate count
                            _mj_judge_key_pool = set(
                                list((_mj_per_judge_asr or {}).keys())
                                + [
                                    k
                                    for k in (_mj_strictness or {}).keys()
                                    if k != "bias_gap"
                                ]
                                + list(_mj_judge_meta.keys())
                            )
                            _mj_all_judge_keys = [
                                key
                                for key in _mj_declared_eval_keys
                                if key in _mj_judge_key_pool
                            ]
                            _mj_all_judge_keys.extend(
                                sorted(
                                    key
                                    for key in _mj_judge_key_pool
                                    if key not in _mj_all_judge_keys
                                )
                            )
                            _mj_display_count = (
                                len(_mj_all_judge_keys)
                                if _mj_all_judge_keys
                                else len(_mj_vote_columns)
                                if _mj_vote_columns
                                else _mj_judge_count or "?"
                            )
                            with ui.row().classes(
                                "items-center gap-2 mb-3 justify-center"
                            ):
                                ui.icon("groups", size="sm").classes("text-indigo-6")
                                ui.label("Multi-Judge Statistics").classes(
                                    "font-semibold text-sm"
                                )
                                ui.badge(
                                    f"{_mj_display_count} judges",
                                    color="indigo",
                                ).classes("text-xs")

                            # ── Row 1: Aggregate metrics ──
                            with ui.row().classes(
                                "w-full flex-wrap gap-6 items-end mb-3 justify-center"
                            ):
                                # Majority Vote ASR
                                if _mj_majority_asr is not None:
                                    with ui.column().classes(
                                        "items-center gap-0 min-w-[90px]"
                                    ):
                                        ui.label(
                                            f"{_mj_majority_asr * 100:.1f}%"
                                        ).classes("text-xl font-bold text-primary")
                                        ui.label("Majority ASR").classes(
                                            "text-[10px] text-grey-6"
                                        )

                                # Fleiss Kappa
                                if _mj_fleiss is not None:
                                    _fk_color = (
                                        "text-green-7"
                                        if _mj_fleiss >= 0.6
                                        else "text-orange-7"
                                        if _mj_fleiss >= 0.2
                                        else "text-red-7"
                                    )
                                    with ui.column().classes(
                                        "items-center gap-0 min-w-[90px]"
                                    ):
                                        ui.label(f"{_mj_fleiss:.4f}").classes(
                                            f"text-xl font-bold {_fk_color}"
                                        )
                                        ui.label("Fleiss κ").classes(
                                            "text-[10px] text-grey-6"
                                        )

                                # Bias gap
                                if isinstance(_mj_strictness, dict):
                                    _bg = self._safe_float(
                                        _mj_strictness.get("bias_gap")
                                    )
                                    if _bg is not None:
                                        _bg_color = (
                                            "text-green-7"
                                            if abs(_bg) < 0.1
                                            else "text-orange-7"
                                            if abs(_bg) < 0.3
                                            else "text-red-7"
                                        )
                                        with ui.column().classes(
                                            "items-center gap-0 min-w-[90px]"
                                        ):
                                            ui.label(f"{_bg:.4f}").classes(
                                                f"text-xl font-bold {_bg_color}"
                                            )
                                            ui.label("Bias Gap").classes(
                                                "text-[10px] text-grey-6"
                                            )

                            # ── Row 2+: Per-judge table ──
                            if _mj_all_judge_keys:
                                ui.separator().classes("my-1")
                                # Table header
                                with ui.row().classes("w-full gap-0 px-2 py-1"):
                                    ui.label("ID").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[52px] text-center"
                                    )
                                    ui.label("Judge").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[160px]"
                                    )
                                    ui.label("Type").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[140px]"
                                    )
                                    ui.label("ASR").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[90px] text-center"
                                    )
                                    ui.label("Strictness").classes(
                                        "text-[11px] font-semibold text-grey-7 w-[90px] text-center ml-4"
                                    )

                                for _row_idx, _jk in enumerate(_mj_all_judge_keys):
                                    _j_meta = _mj_judge_meta.get(_jk, {})
                                    _j_id = _j_meta.get("id", _row_idx)
                                    _j_name = _j_meta.get(
                                        "name",
                                        self._judge_key_display_name(_jk),
                                    )
                                    _j_type = (
                                        _j_meta.get("type")
                                        or self._judge_type_from_key(_jk)
                                        or "—"
                                    )

                                    _j_asr = self._safe_float(
                                        (_mj_per_judge_asr or {}).get(_jk)
                                    )
                                    _j_strict = self._safe_float(
                                        (_mj_strictness or {}).get(_jk)
                                    )

                                    # ASR color
                                    _asr_color = "text-grey-5"
                                    if _j_asr is not None:
                                        _asr_color = (
                                            "text-red-7"
                                            if _j_asr >= 0.7
                                            else "text-orange-7"
                                            if _j_asr >= 0.3
                                            else "text-green-7"
                                        )

                                    # Strictness color
                                    _strict_color = "text-grey-5"
                                    if _j_strict is not None:
                                        _strict_color = (
                                            "text-green-7"
                                            if _j_strict >= 0.7
                                            else "text-orange-7"
                                            if _j_strict >= 0.3
                                            else "text-red-7"
                                        )

                                    with ui.row().classes(
                                        "w-full gap-0 px-2 py-1 items-center "
                                        "hover:bg-grey-1 rounded"
                                    ):
                                        ui.label(str(_j_id)).classes(
                                            "text-xs text-grey-7 font-medium w-[52px] text-center"
                                        )
                                        ui.label(_j_name).classes(
                                            "text-xs font-medium w-[160px] truncate"
                                        )
                                        ui.label(_j_type).classes(
                                            "text-xs text-grey-6 w-[140px]"
                                        )
                                        ui.label(
                                            f"{_j_asr * 100:.1f}%"
                                            if _j_asr is not None
                                            else "—"
                                        ).classes(
                                            f"text-xs font-bold {_asr_color} w-[90px] text-center"
                                        )
                                        ui.label(
                                            f"{_j_strict:.4f}"
                                            if _j_strict is not None
                                            else "—"
                                        ).classes(
                                            f"text-xs font-bold {_strict_color} w-[90px] text-center ml-4"
                                        )

            if all_items and self.history_results_list_area is not None:
                # ── Pre-parse detail data for all rows ─────────────
                _h_atk = attack_type_str.lower()
                _h_detail_data: dict[str, object] = {}
                for _row in new_rows:
                    _rid = str(_row.get("id") or "")
                    if _h_atk == "baseline":
                        _t = baseline_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_baseline_traces(
                            _t, str(_row.get("goal") or "")
                        )
                    elif _h_atk == "bon":
                        _t = bon_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_bon_traces(_t)
                    elif _h_atk == "pap":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_pap_traces(_t)
                    elif _h_atk == "pair":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_pair_traces(_t)
                    elif _h_atk == "tap":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_tap_traces(_t)
                    elif _h_atk == "advprefix":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_advprefix_traces(_t)
                    elif _h_atk == "autodanturbo":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_autodan_traces(_t)
                    elif _h_atk == "mml":
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = self._parse_mml_traces(_t)
                    elif _h_atk in ("fc", "tfc"):
                        _t = generic_traces_map_hr.get(_rid, [])
                        if _h_atk == "fc":
                            _h_detail_data[_rid] = self._parse_fc_traces(_t)
                        else:
                            _h_detail_data[_rid] = self._parse_tfc_traces(_t)
                    else:
                        _t = generic_traces_map_hr.get(_rid, [])
                        _h_detail_data[_rid] = (
                            self._extract_prompt_response_from_traces(_t)
                        )  # returns (req, resp, guardrail_event)

                # Store for filter re-rendering
                self._history_goal_rows = new_rows
                self._history_goal_detail_data = _h_detail_data
                self._history_goal_filter = ""
                self._history_goal_filter_category = ""
                self._history_goal_filter_search = ""
                # Update filter bar
                if self._history_goal_filter_area is not None:
                    self._history_goal_filter_area.clear()
                    with self._history_goal_filter_area:
                        self._build_goal_filter_bar()
                # Render all goals
                self._render_filtered_history_goals()
        except Exception as exc:
            if self.history_results_list_area is not None:
                self.history_results_list_area.clear()
            if self.history_results_empty_label is not None:
                self.history_results_empty_label.text = f"Failed to load results: {exc}"
                self.history_results_empty_label.set_visibility(True)
            ui.notify(f"Error loading results: {exc}", type="negative")
