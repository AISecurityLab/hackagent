# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AutoDAN-Turbo evaluation — multi-judge scoring via BaseEvaluationStep."""

from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from .dashboard_tracing import emit_phase_trace
from .log_styles import format_phase_message


class AutoDANTurboEvaluation(BaseEvaluationStep):
    """Run standardized hackagent multi-judge evaluation on attack outputs.

    Paper relation: this is an integration-layer extension (not in original
    AutoDAN-Turbo paper code) used to align metrics with other techniques.
    """

    @staticmethod
    def _extract_autodan_score(item: Dict[str, Any]) -> float:
        """Pick the internal AutoDAN attack score from a result item.

        Args:
            item: Result row containing one of ``autodan_score``,
                ``attack_score`` or ``score``.

        Returns:
            Floating-point score, defaulting to ``0.0`` when absent.
        """
        for key in ("autodan_score", "attack_score", "score"):
            val = item.get(key)
            if isinstance(val, (int, float)):
                return float(val)
        return 0.0

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate generated responses with configured judges and merge scores.

        Args:
            input_data: Per-goal attack outputs from lifelong phase.

        Returns:
            Enriched result list containing judge columns, aggregated
            ``best_score``, and flags like ``judge_success`` while preserving
            ``autodan_score``/``attack_score`` fields.
        """
        if not input_data:
            return input_data

        params = self._raw_config.get("autodan_turbo_params", {})
        judges = self._resolve_judges_from_config(technique_params=params)
        self.logger.info(
            format_phase_message(
                "evaluation",
                f"Evaluating {len(input_data)} responses with {len(judges)} judge(s)",
            )
        )
        self._tracker = self._raw_config.get("_tracker")

        # Transform to eval format
        eval_rows, errors = [], set()
        for i, item in enumerate(input_data):
            if item.get("error"):
                errors.add(i)
                item.update(best_score=0.0, success=False)
                continue
            auto_score = self._extract_autodan_score(item)
            item["autodan_score"] = auto_score
            item.setdefault("attack_score", auto_score)
            eval_rows.append(
                {
                    "goal": item.get("goal", ""),
                    "prefix": item.get("full_prompt", item.get("prompt", "")),
                    "completion": item.get("response", ""),
                }
            )

        if not eval_rows:
            self._enrich_items_with_scores(input_data, errors)
            return input_data

        # Run judges
        base_config = self._build_base_eval_config(technique_params=params)
        evaluated = self._run_evaluation(eval_rows, judges, base_config)

        # Merge results back
        all_cols = {col for cols in self.JUDGE_COLUMN_MAP.values() for col in cols}

        normalize = self._normalize_merge_key
        lookup = {}
        for row in evaluated:
            key = (
                normalize("goal", row.get("goal")),
                normalize("prefix", row.get("prefix")),
                normalize("completion", row.get("completion")),
            )
            lookup[key] = {c: row[c] for c in all_cols if c in row}

        for i, item in enumerate(input_data):
            if i not in errors:
                key = (
                    normalize("goal", item.get("goal")),
                    normalize(
                        "prefix", item.get("full_prompt", item.get("prompt", ""))
                    ),
                    normalize("completion", item.get("response")),
                )
                item.update(lookup.get(key, {}))

        self._enrich_items_with_scores(input_data, errors)

        for item in input_data:
            auto_score = self._extract_autodan_score(item)
            judge_best_score = float(item.get("best_score", 0.0) or 0.0)
            item["autodan_score"] = auto_score
            item["attack_score"] = auto_score
            item["judge_best_score"] = judge_best_score
            # For AutoDAN dashboard summaries, best_score must represent scorer score.
            item["best_score"] = auto_score
            item["judge_success"] = bool(item.get("success", False))

        for idx, item in enumerate(input_data):
            hb_expl = str(item.get("explanation_hb", ""))
            hb_expl_short = hb_expl[:220] + "..." if len(hb_expl) > 220 else hb_expl
            self.logger.info(
                format_phase_message(
                    "evaluation",
                    f"Goal {idx}: AutoDAN score={item.get('autodan_score', 0.0):.1f}/10 | "
                    f"Judge best_score={item.get('best_score', 0.0):.1f} | "
                    f"Final success={item.get('judge_success', False)} | "
                    f"HB explanation={hb_expl_short}",
                )
            )
            emit_phase_trace(
                self._raw_config,
                phase="EVALUATION",
                subphase="JUDGE_SCORING",
                step_name="Evaluation - Judge Scoring",
                goal=item.get("goal"),
                payload={
                    "dashboard_section": "Evaluation",
                    "dashboard_group": "Evaluation",
                    "dashboard_item": "Judge Scoring",
                    "prompt": item.get("full_prompt", item.get("prompt", "")),
                    "response": item.get("response", ""),
                    "autodan_score": item.get("autodan_score", 0.0),
                    "judge_best_score": item.get("judge_best_score", 0.0),
                    "judge_success": item.get("judge_success", False),
                    "eval_hb": item.get("eval_hb"),
                    "eval_jb": item.get("eval_jb"),
                    "eval_nj": item.get("eval_nj"),
                    "explanation_hb": item.get("explanation_hb"),
                    "explanation_jb": item.get("explanation_jb"),
                    "explanation_nj": item.get("explanation_nj"),
                },
            )

        self._update_tracker(input_data, evaluator_prefix="autodan_turbo_eval")
        self._sync_to_server(input_data, self._build_judge_keys_from_data(input_data))
        self._log_evaluation_asr(input_data)
        return input_data


def execute(input_data, config, client, logger):
    """Module-level pipeline entry point used by attack orchestrator.

    Args:
        input_data: Lifelong phase outputs to evaluate.
        config: Full attack configuration.
        client: Authenticated client for judge routing.
        logger: Logger instance.

    Returns:
        Evaluated and enriched results list.
    """
    return AutoDANTurboEvaluation(config=config, logger=logger, client=client).execute(
        input_data
    )
