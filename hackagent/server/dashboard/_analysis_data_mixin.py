# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run/result aggregation, judges and evaluation helpers.

Provides ``DashboardAnalysisDataMixin`` for ``DashboardPage``. This is the
*pure data* layer shared by every view: it has no widget-building code, only
lookups, normalisation and metric computation. Keeping it widget-free lets its
static helpers be unit-tested in isolation.

Responsibilities:
    - ID → name/type/config lookup maps for agents and attacks (paginating the
      backend as needed).
    - Normalising heterogeneous result payloads (``_extract_row``, evaluation
      votes, category/latency extraction, run status derivation).
    - Multi-judge metrics: per-judge ASR/strictness, majority vote, Fleiss'
      kappa, and run-level summaries (``_summarize_run_results``).
"""

from __future__ import annotations

import contextlib
import json
import math
from typing import Any
from uuid import UUID


from hackagent.attacks.evaluator.metrics import (
    calculate_majority_vote_asr,
)

from ._helpers import (
    _duration_seconds,
    _result_bucket,
    _serialize,
)


class DashboardAnalysisDataMixin:
    """Run/result aggregation, judges and evaluation helpers."""

    @staticmethod
    def _extract_row(payload: object) -> dict | None:
        """Normalize NiceGUI/Quasar click payloads to a row dictionary."""
        if isinstance(payload, dict):
            row = payload.get("row")
            if isinstance(row, dict):
                return row
            if "id" in payload:
                return payload
            return None

        if isinstance(payload, (list, tuple)):
            for item in payload:
                row = DashboardAnalysisDataMixin._extract_row(item)
                if row is not None:
                    return row

        return None

    def _attack_type_map(self) -> dict[str, str]:
        """Return mapping attack_id -> attack type for run table enrichment."""
        return self._attack_type_map_for_ids(None)

    def _agent_name_map(self) -> dict[str, str]:
        """Return mapping agent_id -> agent name for table enrichment."""
        return self._agent_name_map_for_ids(None)

    def _attack_type_map_for_ids(self, required_ids: set[str] | None) -> dict[str, str]:
        """Fetch attack types, paginating until required IDs are found."""
        out: dict[str, str] = {}
        page = 1
        page_size = 100

        while True:
            attacks_p = self.backend.list_attacks(page=page, page_size=page_size)
            if not attacks_p.items:
                break

            for attack in attacks_p.items:
                attack_id = str(attack.id)
                if required_ids is None or attack_id in required_ids:
                    out[attack_id] = attack.type

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((attacks_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    def _attack_config_map_for_ids(
        self, required_ids: set[str] | None
    ) -> dict[str, dict]:
        """Fetch attack configurations, paginating until required IDs are found.

        Returns mapping attack_id -> configuration dict (may be empty dict).
        """
        out: dict[str, dict] = {}
        page = 1
        page_size = 100

        while True:
            attacks_p = self.backend.list_attacks(page=page, page_size=page_size)
            if not attacks_p.items:
                break

            for attack in attacks_p.items:
                attack_id = str(attack.id)
                if required_ids is None or attack_id in required_ids:
                    # AttackRecord.configuration is a dict
                    cfg = getattr(attack, "configuration", {})
                    out[attack_id] = cfg or {}

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((attacks_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    def _agent_name_map_for_ids(self, required_ids: set[str] | None) -> dict[str, str]:
        """Fetch agent names, paginating until required IDs are found."""
        out: dict[str, str] = {}
        page = 1
        page_size = 100

        while True:
            agents_p = self.backend.list_agents(page=page, page_size=page_size)
            if not agents_p.items:
                break

            for agent in agents_p.items:
                agent_id = str(agent.id)
                if required_ids is None or agent_id in required_ids:
                    out[agent_id] = agent.name

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((agents_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    def _agent_records_map_for_ids(
        self, required_ids: set[str] | None
    ) -> dict[str, dict]:
        """Fetch serialized agent records, paginating until required IDs are found."""
        out: dict[str, dict] = {}
        page = 1
        page_size = 100

        while True:
            agents_p = self.backend.list_agents(page=page, page_size=page_size)
            if not agents_p.items:
                break

            for agent in agents_p.items:
                agent_id = str(agent.id)
                if required_ids is None or agent_id in required_ids:
                    out[agent_id] = _serialize(agent)

            if required_ids is not None and required_ids.issubset(out.keys()):
                break

            total_pages = max(1, math.ceil((agents_p.total or 0) / page_size))
            if page >= total_pages:
                break
            page += 1

        return out

    @staticmethod
    def _derive_run_status(
        result_statuses: list[tuple[str, str | None]],
        observed_total_results: int | None = None,
        expected_total_goals: int | None = None,
        fallback: str = "",
    ) -> str:
        """Derive run status from associated goal evaluation statuses."""
        if observed_total_results is None:
            observed_total_results = len(result_statuses)

        if (
            isinstance(expected_total_goals, int)
            and expected_total_goals > 0
            and observed_total_results < expected_total_goals
        ):
            fallback_status = str(fallback or "").upper()
            if fallback_status in {"FAILED", "CANCELLED"}:
                return fallback_status
            return "RUNNING"

        buckets = [_result_bucket(status=s, notes=n) for s, n in result_statuses]
        has_pending = any(b == "pending" for b in buckets)
        if has_pending:
            return "RUNNING"
        if buckets:
            return "COMPLETED"
        return fallback or "PENDING"

    @staticmethod
    def _extract_expected_total_goals(run_data: dict) -> int | None:
        """Extract expected goal count from run_config when available."""
        if not isinstance(run_data, dict):
            return None

        run_cfg = run_data.get("run_config")
        if not isinstance(run_cfg, dict):
            return None

        candidates = (
            run_cfg.get("expected_total_goals"),
            run_cfg.get("expected_goal_count"),
            run_cfg.get("total_goals"),
            run_cfg.get("goal_count"),
        )
        for value in candidates:
            try:
                parsed = int(value)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """Best-effort float parsing with None fallback."""
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_run_evaluation_summary(run_data: dict) -> dict:
        """Extract evaluation_summary from run payload/run_config."""
        if not isinstance(run_data, dict):
            return {}

        run_cfg = run_data.get("run_config")
        if isinstance(run_cfg, dict):
            summary = run_cfg.get("evaluation_summary")
            return summary if isinstance(summary, dict) else {}

        if isinstance(run_cfg, str) and run_cfg.strip():
            with contextlib.suppress(Exception):
                parsed = json.loads(run_cfg)
                if isinstance(parsed, dict):
                    summary = parsed.get("evaluation_summary")
                    if isinstance(summary, dict):
                        return summary
        return {}

    @staticmethod
    def _coerce_binary_vote(value: object) -> int:
        """Normalize common vote values to 0/1 for dashboard metrics."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(float(value) > 0)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {
                "1",
                "true",
                "yes",
                "y",
                "success",
                "successful",
                "jailbreak",
                "harmful",
                "violating",
                "1_violating",
            }:
                return 1
            if normalized in {
                "0",
                "false",
                "no",
                "n",
                "safe",
                "compliant",
                "mitigated",
                "0_compliant",
                "",
            }:
                return 0
            with contextlib.suppress(ValueError):
                return int(float(normalized) > 0)
        return 0

    @staticmethod
    def _is_canonical_eval_vote_key(key: object) -> bool:
        """True only for canonical eval vote keys (exclude derived stats)."""
        if not isinstance(key, str):
            return False
        if not key.startswith("eval_"):
            return False
        if key.endswith("_raw_response"):
            return False
        if key.endswith("_mean") or key.endswith("_count"):
            return False
        return True

    @staticmethod
    def _judge_key_display_name(judge_key: object) -> str:
        """Return compact judge name for UI labels (e.g. eval_hbv -> hbv)."""
        if isinstance(judge_key, str) and judge_key.startswith("eval_"):
            return judge_key[5:]
        return str(judge_key)

    @staticmethod
    def _judge_type_from_key(judge_key: str) -> str:
        """Infer judge type display string from eval key abbreviation."""
        _abbr_to_type = {
            "hb": "Harmbench",
            "hbv": "Harmbench Variant",
            "jb": "Jailbreakbench",
            "nj": "Nuanced",
            "on_topic": "On Topic",
        }
        stripped = judge_key[5:] if judge_key.startswith("eval_") else judge_key
        # Remove trailing _N suffix (e.g. hbv_1 -> hbv)
        base = (
            stripped.rsplit("_", 1)[0]
            if "_" in stripped and stripped.rsplit("_", 1)[1].isdigit()
            else stripped
        )
        return _abbr_to_type.get(base, "")

    @classmethod
    def _build_judge_metadata(
        cls, judges_cfg: object
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """Build eval-key metadata mapping from attack judge configuration."""
        if not isinstance(judges_cfg, list):
            return {}, []

        type_counts: dict[str, int] = {}
        for judge_cfg in judges_cfg:
            if not isinstance(judge_cfg, dict):
                continue
            judge_type = str(judge_cfg.get("type") or "unknown")
            type_counts[judge_type] = type_counts.get(judge_type, 0) + 1

        type_idx: dict[str, int] = {}
        type_abbr_map = {
            "harmbench": "hb",
            "harmbench_variant": "hbv",
            "jailbreakbench": "jb",
            "nuanced": "nj",
            "on_topic": "on_topic",
        }

        judge_meta: dict[str, dict[str, Any]] = {}
        declared_eval_keys: list[str] = []

        for judge_idx, judge_cfg in enumerate(judges_cfg):
            if not isinstance(judge_cfg, dict):
                continue

            judge_type = str(judge_cfg.get("type") or "unknown")
            judge_name = str(
                judge_cfg.get("identifier") or judge_cfg.get("agent_name") or judge_type
            )
            abbr = type_abbr_map.get(judge_type, judge_type)

            type_idx[judge_type] = type_idx.get(judge_type, 0) + 1
            if type_counts.get(judge_type, 0) > 1:
                eval_key = f"eval_{abbr}_{type_idx[judge_type]}"
            else:
                eval_key = f"eval_{abbr}"

            declared_eval_keys.append(eval_key)
            judge_meta[eval_key] = {
                "id": judge_idx,
                "name": judge_name,
                "type": judge_type.replace("_", " ").title(),
            }

        return judge_meta, declared_eval_keys

    @classmethod
    def _extract_eval_votes_from_result(cls, result_data: dict) -> dict[str, int]:
        """Collect canonical eval_* judge votes from top-level/metadata/metrics."""
        votes: dict[str, int] = {}
        for source in (
            result_data,
            result_data.get("metadata"),
            result_data.get("evaluation_metrics"),
        ):
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                if not cls._is_canonical_eval_vote_key(key):
                    continue
                if value is None:
                    continue
                votes[key] = cls._coerce_binary_vote(value)

        return dict(sorted(votes.items()))

    @classmethod
    def _compute_goal_multi_judge_metrics(cls, result_data: dict) -> dict:
        """Compute per-goal multi-judge metrics from a single result row."""
        votes = cls._extract_eval_votes_from_result(result_data)
        if len(votes) <= 1:
            return {}

        row_votes = dict(votes)
        judge_avg = (
            sum(float(vote) for vote in row_votes.values()) / len(row_votes)
            if row_votes
            else None
        )
        return {
            "judge_count": len(row_votes),
            "judge_votes": dict(sorted(row_votes.items())),
            "judge_avg": judge_avg,
            # Keep an explicit majority_vote_asr alias so downstream consumers
            # can consistently derive per-goal majority verdicts.
            "majority_vote_asr": judge_avg,
        }

    def _summarize_run_results(
        self, run_id: UUID, run_data: dict | None = None
    ) -> dict[str, object]:
        """Return per-run result counts and derived run status."""
        evaluation_summary = self._extract_run_evaluation_summary(run_data or {})
        judge_count = int(evaluation_summary.get("judge_count") or 0)
        is_multi_judge = bool(evaluation_summary.get("is_multi_judge")) or (
            judge_count > 1
        )

        majority_vote_asr = self._safe_float(
            evaluation_summary.get("majority_vote_asr")
            if isinstance(evaluation_summary, dict)
            else None
        )
        if majority_vote_asr is None and isinstance(evaluation_summary, dict):
            majority_vote_asr = self._safe_float(
                evaluation_summary.get("overall_majority_vote_asr")
            )

        overall_success_rate = self._safe_float(
            evaluation_summary.get("overall_success_rate")
            if isinstance(evaluation_summary, dict)
            else None
        )
        overall_effective_asr = self._safe_float(
            evaluation_summary.get("overall_effective_asr")
            if isinstance(evaluation_summary, dict)
            else None
        )

        page = 1
        page_size = 100
        fetched = 0
        total = 0
        successful_jailbreaks = 0
        mitigations = 0
        finished_goal_latencies_s: list[float] = []
        statuses: list[tuple[str, str | None]] = []
        computed_run_vote_columns: set[str] = set()
        computed_run_vote_rows: list[dict[str, int]] = []

        while True:
            rp = self.backend.list_results(
                run_id=run_id, page=page, page_size=page_size
            )
            if page == 1:
                total = int(rp.total or 0)
            if not rp.items:
                break

            for result in rp.items:
                serialized_result = _serialize(result)
                row_votes = self._extract_eval_votes_from_result(serialized_result)
                if row_votes:
                    computed_run_vote_columns.update(row_votes.keys())
                    computed_run_vote_rows.append(dict(row_votes))

                bucket = _result_bucket(
                    result.evaluation_status, result.evaluation_notes
                )
                if bucket == "jailbreak":
                    successful_jailbreaks += 1
                elif bucket == "mitigated":
                    mitigations += 1
                if bucket != "pending":
                    latency_s = self._extract_goal_latency_seconds(_serialize(result))
                    if isinstance(latency_s, (int, float)):
                        finished_goal_latencies_s.append(float(latency_s))
                statuses.append((result.evaluation_status, result.evaluation_notes))

            fetched += len(rp.items)
            if total > 0 and fetched >= total:
                break
            page += 1

        if total == 0:
            total = fetched

        expected_total_goals = self._extract_expected_total_goals(run_data or {})

        computed_judge_count = len(computed_run_vote_columns)
        if computed_judge_count > 0:
            judge_count = computed_judge_count
            is_multi_judge = judge_count > 1

        if is_multi_judge and majority_vote_asr is None and computed_run_vote_rows:
            majority_vote_asr = calculate_majority_vote_asr(
                [dict(row) for row in computed_run_vote_rows]
            )

        avg_goal_latency_s = (
            sum(finished_goal_latencies_s) / len(finished_goal_latencies_s)
            if finished_goal_latencies_s
            else None
        )

        overall_asr_rate = None
        if is_multi_judge and majority_vote_asr is not None:
            overall_asr_rate = majority_vote_asr
        elif overall_effective_asr is not None:
            overall_asr_rate = overall_effective_asr
        elif overall_success_rate is not None:
            overall_asr_rate = overall_success_rate
        elif total > 0:
            overall_asr_rate = successful_jailbreaks / total

        overall_asr_display = (
            f"{(overall_asr_rate * 100):.1f}%"
            if isinstance(overall_asr_rate, (int, float))
            else "—"
        )

        return {
            "total_results": total,
            "successful_jailbreaks": successful_jailbreaks,
            "mitigations": mitigations,
            "failed_attacks": mitigations,
            "avg_goal_latency_s": avg_goal_latency_s,
            "evaluation_summary": evaluation_summary,
            "is_multi_judge": is_multi_judge,
            "judge_count": judge_count,
            "overall_asr_rate": overall_asr_rate,
            "overall_asr_display": overall_asr_display,
            "expected_total_goals": expected_total_goals,
            "status": self._derive_run_status(
                statuses,
                observed_total_results=total,
                expected_total_goals=expected_total_goals,
            ),
        }

    @staticmethod
    def _compute_run_latency_seconds(run_data: dict) -> float | None:
        """Best-effort run wall-time latency from run timestamps."""
        return _duration_seconds(
            str(run_data.get("created_at") or "") or None,
            str(run_data.get("updated_at") or "") or None,
        )

    @staticmethod
    def _extract_goal_latency_seconds(result_data: dict) -> float | None:
        """Best-effort per-goal latency from metadata/metrics or timestamps."""
        metadata = (
            result_data.get("metadata")
            if isinstance(result_data.get("metadata"), dict)
            else {}
        )
        metrics = (
            result_data.get("evaluation_metrics")
            if isinstance(result_data.get("evaluation_metrics"), dict)
            else {}
        )

        # Prefer end-to-end goal elapsed_s written by Tracker.finalize_goal().
        for key in ("elapsed_s",):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            value = metrics.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))

        # Secondary explicit fields if elapsed_s is missing.
        for key in ("latency_s", "duration_s"):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            value = metrics.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))

        return _duration_seconds(
            str(result_data.get("created_at") or "") or None,
            str(result_data.get("updated_at") or "") or None,
        )

    @staticmethod
    def _extract_category_label(result_data: dict) -> str | None:
        """Best-effort category label lookup from result metadata/metrics."""
        sources = []
        for src in (
            result_data,
            result_data.get("metadata"),
            result_data.get("evaluation_metrics"),
        ):
            if isinstance(src, dict):
                sources.append(src)

        key_candidates = (
            "category",
            "category_name",
            "harm_category",
            "risk_category",
            "risk_domain",
            "topic",
            "label",
            "l2_name",
            "l3_name",
            "l4_name",
            "l2-name",
            "l3-name",
            "l4-name",
        )

        for src in sources:
            for key in key_candidates:
                val = src.get(key)
                if val not in (None, ""):
                    return str(val)
            taxonomy = src.get("taxonomy")
            if isinstance(taxonomy, dict):
                for key in ("l2", "l3", "l4", "name", "category"):
                    val = taxonomy.get(key)
                    if val not in (None, ""):
                        return str(val)

        return None

    @staticmethod
    def _extract_goal_classifier_label(result_data: dict, field: str) -> str:
        """Extract classifier category/subcategory labels from result payload."""
        normalized = (field or "").strip().lower()
        if normalized not in {"category", "subcategory"}:
            return "N/A"

        sources = []
        for src in (
            result_data,
            result_data.get("metadata"),
            result_data.get("evaluation_metrics"),
        ):
            if isinstance(src, dict):
                sources.append(src)

        if normalized == "category":
            key_candidates = (
                "category",
                "category_name",
                "harm_category",
                "risk_category",
            )
            taxonomy_keys = ("category", "l2", "name")
        else:
            key_candidates = (
                "subcategory",
                "subcategory_name",
                "harm_subcategory",
                "risk_subcategory",
            )
            taxonomy_keys = ("subcategory", "l3", "l4", "name")

        for src in sources:
            for key in key_candidates:
                val = src.get(key)
                if val not in (None, ""):
                    return str(val)

            taxonomy = src.get("taxonomy")
            if isinstance(taxonomy, dict):
                for key in taxonomy_keys:
                    val = taxonomy.get(key)
                    if val not in (None, ""):
                        return str(val)

        return "N/A"

    @staticmethod
    def _goal_category_badge_text(result_data: dict) -> str:
        """Compose a single category/subcategory badge label for a goal."""
        category = DashboardAnalysisDataMixin._extract_goal_classifier_label(
            result_data, "category"
        )
        subcategory = DashboardAnalysisDataMixin._extract_goal_classifier_label(
            result_data, "subcategory"
        )
        category = category if category and category != "N/A" else "N/A"
        subcategory = subcategory if subcategory and subcategory != "N/A" else "N/A"
        return f"{category} / {subcategory}"
