"""Evaluation helpers for TAP using the shared evaluator framework."""

import logging
from typing import Any, Dict, List, Optional

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.client import AuthenticatedClient


class TapEvaluation(BaseEvaluationStep):
    """
    Evaluation wrapper for TAP judge and on-topic scoring.

    Provides convenience helpers that adapt TAP data structures to the
    shared multi-judge evaluation pipeline.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger,
        client: AuthenticatedClient,
    ):
        """
        Initialize the evaluation helper.

        Args:
            config: TAP configuration dict.
            logger: Logger instance used by evaluation utilities.
            client: Authenticated API client for evaluation requests.
        """
        super().__init__(config, logger, client)

    def evaluate_judge(
        self,
        input_data: List[Dict[str, Any]],
        judges_config: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Run configured judges and attach aggregated scores.

        Args:
            input_data: Rows with goal/prefix/completion fields.
            judges_config: List of judge configurations.

        Returns:
            Evaluated rows enriched with judge outputs and best_score.
        """
        base_config = self._build_base_eval_config()
        evaluated = self._run_evaluation(input_data, judges_config, base_config)
        self._enrich_items_with_scores(evaluated)
        return evaluated

    def evaluate_on_topic(
        self,
        input_data: List[Dict[str, Any]],
        on_topic_judges: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        Score prompts for topicality or default to on-topic when disabled.

        Args:
            input_data: Rows with goal/prefix/completion fields.
            on_topic_judges: Optional on-topic judge configuration list.

        Returns:
            Evaluated rows enriched with on-topic scores.
        """
        if not on_topic_judges:
            for row in input_data:
                row["eval_on_topic"] = 1
                row["explanation_on_topic"] = "On-topic check skipped"
            return input_data

        base_config = self._build_base_eval_config()
        return self._run_evaluation(input_data, on_topic_judges, base_config)

    def score_on_topic(
        self,
        goal: str,
        prompts: List[str],
        on_topic_judges: Optional[List[Dict[str, Any]]],
        default: int = 0,
    ) -> List[int]:
        """
        Convenience wrapper for on-topic scoring in TAP loops.

        Args:
            goal: The goal string for the prompts.
            prompts: List of candidate prompts to score.
            on_topic_judges: Optional on-topic judge configuration.
            default: Score used when evaluation output is missing.

        Returns:
            List of integer on-topic scores aligned with prompts.
        """
        rows = [
            {
                "goal": goal,
                "prefix": "",
                "completion": prompt,
            }
            for prompt in prompts
        ]
        evaluated = self.evaluate_on_topic(rows, on_topic_judges)
        return self.extract_scores(evaluated, "eval_on_topic", default=default)

    def score_candidates(
        self,
        goal: str,
        prompts: List[str],
        responses: List[str],
        judges_config: List[Dict[str, Any]],
        default: int = 0,
    ) -> List[int]:
        """
        Convenience wrapper for judge scoring of prompt-response pairs.

        Args:
            goal: The goal string for the prompt/response pairs.
            prompts: List of candidate prompts.
            responses: List of victim responses corresponding to prompts.
            judges_config: List of judge configurations.
            default: Score used when evaluation output is missing.

        Returns:
            List of integer judge scores aligned with prompts.
        """
        rows = [
            {
                "goal": goal,
                "prefix": prompt,
                "completion": response,
            }
            for prompt, response in zip(prompts, responses)
        ]
        evaluated = self.evaluate_judge(rows, judges_config)
        return self.extract_scores(evaluated, "best_score", default=default)

    @staticmethod
    def extract_scores(
        evaluated: List[Dict[str, Any]],
        score_key: str,
        default: int = 0,
    ) -> List[int]:
        """
        Extract numeric scores from evaluation output with fallback.

        Args:
            evaluated: List of evaluation rows.
            score_key: Key to read the score from each row.
            default: Fallback score when parsing fails.

        Returns:
            List of integer scores aligned with evaluated rows.
        """
        scores: List[int] = []
        for row in evaluated:
            value = row.get(score_key)
            if value is None:
                scores.append(default)
                continue
            try:
                scores.append(int(float(value)))
            except (TypeError, ValueError):
                scores.append(default)
        return scores


def _resolve_judges_config(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize judge config to a list for batch evaluation.

    Args:
        config: TAP configuration dict.

    Returns:
        List of judge configuration dicts (possibly empty).
    """
    judges = config.get("judges")
    if isinstance(judges, list) and judges:
        return judges
    judge = config.get("judge")
    if isinstance(judge, dict):
        return [judge]
    return []


def execute(
    input_data: List[Dict[str, Any]],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """
    Pipeline entry point for TAP evaluation.

    Ensures best_score/is_success are present and writes tracker traces
    based on the final best prompt/response for each goal.

    Args:
        input_data: List of result dicts from generation.
        config: TAP configuration dict.
        client: Authenticated API client for evaluation.
        logger: Logger for evaluation diagnostics.

    Returns:
        Input data enriched with evaluation fields.
    """
    if not input_data:
        return input_data

    evaluator = TapEvaluation(config=config, logger=logger, client=client)
    judges_config = _resolve_judges_config(config)
    tap_params = config.get("tap_params", {})
    success_threshold = tap_params.get("success_score_threshold", 1)

    tracker = config.get("_tracker")

    for idx, item in enumerate(input_data):
        best_prompt = item.get("best_prompt")
        best_response = item.get("best_response")
        best_score = item.get("best_score")

        if best_score is None and best_prompt and best_response and judges_config:
            score_list = evaluator.score_candidates(
                goal=item.get("goal", ""),
                prompts=[best_prompt],
                responses=[best_response],
                judges_config=judges_config,
                default=0,
            )
            best_score = score_list[0] if score_list else 0
            item["best_score"] = best_score
            item["is_success"] = best_score >= success_threshold

        if tracker:
            goal_ctx = tracker.get_goal_context(idx)
            if goal_ctx and best_score is not None:
                tracker.add_evaluation_trace(
                    ctx=goal_ctx,
                    evaluation_result={
                        "best_score": best_score,
                        "is_success": item.get("is_success", False),
                        "iterations_completed": item.get("iterations_completed"),
                    },
                    score=best_score,
                    explanation=(
                        f"Best score: {best_score} after "
                        f"{item.get('iterations_completed', 0)} iterations"
                    ),
                    evaluator_name="tap_judge",
                )

    return input_data
