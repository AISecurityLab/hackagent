# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AutoDAN-Turbo evaluation wrapper using the shared LLM-judge pipeline."""

from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from .dashboard_tracing import emit_phase_trace
from .log_styles import format_phase_message


class AutoDANTurboEvaluation(BaseEvaluationStep):
    """Finalize AutoDAN-Turbo outputs with the shared multi-judge flow.

    AutoDAN generation still produces an internal attack score
    (``autodan_score``/``attack_score``), but jailbreak success is always
    computed by configured LLM judge(s) via :class:`BaseEvaluationStep`.
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

    @staticmethod
    def _drop_legacy_judge_fields(item: Dict[str, Any]) -> None:
        """Remove stale judge fields from previous pipeline versions."""
        stale_keys = [
            key
            for key in list(item.keys())
            if key.startswith("eval_")
            or key.startswith("explanation_")
            or key.startswith("judge_")
        ]
        for key in stale_keys:
            item.pop(key, None)

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate AutoDAN outputs using LLM judges.

        Args:
            input_data: Per-goal attack outputs from lifelong phase.

        Returns:
            Enriched result list with judge outputs, ``best_score``, and
            ``success`` fields.
        """
        if not input_data:
            return input_data

        self.logger.info(
            format_phase_message(
                "evaluation",
                f"Running shared LLM-judge evaluation on {len(input_data)} response(s)",
            )
        )
        self._tracker = self._raw_config.get("_tracker")

        for idx, item in enumerate(input_data):
            self._drop_legacy_judge_fields(item)
            auto_score = self._extract_autodan_score(item)
            item["autodan_score"] = auto_score
            item["attack_score"] = auto_score

            self.logger.info(
                format_phase_message(
                    "evaluation",
                    f"Goal {idx}: autodan_score={auto_score:.1f}/10",
                )
            )
            emit_phase_trace(
                self._raw_config,
                phase="EVALUATION",
                subphase="SCORER_FINALIZATION",
                step_name="Evaluation - Scorer Finalization",
                goal=item.get("goal"),
                payload={
                    "dashboard_section": "Evaluation",
                    "dashboard_group": "Evaluation",
                    "dashboard_item": "Scorer Finalization",
                    "prompt": item.get("full_prompt", item.get("prompt", "")),
                    "response": item.get("response", ""),
                    "autodan_score": auto_score,
                    "message": "Pre-judge score normalization",
                },
            )

        input_data = self.run_full_evaluation(input_data)

        total = len(input_data)
        successes = sum(1 for item in input_data if item.get("success"))
        self.logger.info(
            format_phase_message(
                "evaluation",
                f"ASR-LLMJudge: {successes}/{total} ({(successes / total * 100.0):.1f}%)",
            )
        )
        return input_data


def execute(input_data, config, client, logger):
    """Module-level pipeline entry point used by attack orchestrator.

    Args:
        input_data: Lifelong phase outputs to evaluate.
        config: Full attack configuration.
        client: Authenticated client for result sync.
        logger: Logger instance.

    Returns:
        Finalized and enriched results list.
    """
    return AutoDANTurboEvaluation(config=config, logger=logger, client=client).execute(
        input_data
    )
