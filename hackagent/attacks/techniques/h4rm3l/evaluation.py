# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
h4rm3l evaluation module.

Multi-judge evaluation via ``BaseEvaluationStep``.
Evaluates whether the target model's response to a decorated prompt
constitutes a successful jailbreak.
"""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.server.client import AuthenticatedClient


class H4rm3lEvaluation(BaseEvaluationStep):
    """Evaluation step for h4rm3l attack.

    Transforms h4rm3l response data into the standard evaluation format
    ``(goal, prefix, completion)``, runs all configured judges, merges
    results back, and syncs to the server.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        client: AuthenticatedClient,
    ):
        super().__init__(config, logger, client)

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluate h4rm3l responses using the multi-judge pipeline.

        Args:
            input_data: Dicts from generation step (with ``response``,
                        ``goal``, ``full_prompt``, etc.).

        Returns:
            Same list enriched with judge columns, ``best_score``, ``success``.
        """
        if not input_data:
            return input_data

        self._statistics["input_count"] = len(input_data)

        params = self._raw_config.get("h4rm3l_params", {})
        judges_config = self._resolve_judges_from_config(technique_params=params)

        self.logger.info(
            f"Evaluating {len(input_data)} responses with {len(judges_config)} judge(s)"
        )

        if self._tracker:
            self.logger.info("Evaluation tracking via Tracker enabled")

            for idx, item in enumerate(input_data):
                goal_text = item.get("goal", "")
                goal_ctx = (
                    self._tracker.get_goal_context_by_goal(goal_text)
                    if goal_text
                    else self._tracker.get_goal_context(idx)
                )
                if not goal_ctx:
                    continue

                for step in item.get("decoration_steps", []) or []:
                    step_index = step.get("step_index")
                    decorator_name = step.get("decorator", "UnknownDecorator")
                    self._tracker.add_custom_trace(
                        ctx=goal_ctx,
                        step_name=f"Decoration Step {step_index}: {decorator_name}",
                        content={
                            "step_name": f"Decoration Step {step_index}",
                            "decorator": decorator_name,
                            "input_prompt": step.get("input_prompt", ""),
                            "decoration_applied": decorator_name,
                            "decorated_prompt": step.get("decorated_prompt", ""),
                            "input_length": step.get("input_length"),
                            "output_length": step.get("output_length"),
                            "length_delta": step.get("length_delta"),
                            "content_changed": step.get("content_changed"),
                            "uses_decorator_llm": step.get("uses_decorator_llm", False),
                            "decorator_llm_identifier": step.get(
                                "decorator_llm_identifier"
                            ),
                            "decorator_llm_endpoint": step.get(
                                "decorator_llm_endpoint"
                            ),
                            "decorator_llm_prompt": step.get("decorator_llm_prompt"),
                            "decorator_llm_response": step.get(
                                "decorator_llm_response"
                            ),
                        },
                    )

        # ----- Transform to evaluation format ----- #
        eval_rows: List[Dict[str, Any]] = []
        error_indices: set = set()

        for idx, item in enumerate(input_data):
            if item.get("error"):
                error_indices.add(idx)
                item["best_score"] = 0.0
                item["success"] = False
                item["evaluation_notes"] = f"Execution error: {item['error']}"
                continue

            eval_rows.append(
                {
                    "goal": item.get("goal", ""),
                    "prefix": item.get("full_prompt", ""),
                    "completion": item.get("response", "") or "",
                }
            )

        if not eval_rows:
            self.logger.warning("No valid rows to evaluate (all errors)")
            self._enrich_items_with_scores(input_data, error_indices)
            return input_data

        # ----- Build evaluator base config ----- #
        base_config = self._build_base_eval_config(technique_params=params)

        # ----- Run multi-judge evaluation ----- #
        evaluated_rows = self._run_evaluation(eval_rows, judges_config, base_config)
        self._statistics["evaluated_count"] = len(evaluated_rows)

        # ----- Merge results back into input_data ----- #
        all_judge_cols: set = set()
        for cols in self.JUDGE_COLUMN_MAP.values():
            all_judge_cols.update(cols)

        normalize = self._normalize_merge_key
        lookup = {}
        for row in evaluated_rows:
            key = (
                normalize("goal", row.get("goal")),
                normalize("prefix", row.get("prefix")),
                normalize("completion", row.get("completion")),
            )
            lookup[key] = {c: row[c] for c in all_judge_cols if c in row}

        for i, item in enumerate(input_data):
            if i not in error_indices:
                key = (
                    normalize("goal", item.get("goal")),
                    normalize("prefix", item.get("full_prompt", "")),
                    normalize("completion", item.get("response", "")),
                )
                item.update(lookup.get(key, {}))

        # ----- Compute best_score / success ----- #
        self._enrich_items_with_scores(input_data, error_indices)

        # ----- Tracker integration ----- #
        self._update_tracker(
            input_data,
            evaluator_prefix="h4rm3l_eval",
        )

        # ----- Sync to server ----- #
        judge_keys = self._build_judge_keys_from_data(input_data)
        self._sync_to_server(input_data, judge_keys)

        # ----- Log ASR ----- #
        self._log_evaluation_asr(input_data)

        return input_data


def execute(
    input_data: List[Dict[str, Any]],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Module-level entry point for the pipeline."""
    return H4rm3lEvaluation(config=config, logger=logger, client=client).execute(
        input_data
    )
