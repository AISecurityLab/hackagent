# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
FC-Attack evaluation module.

Evaluates attack success using multi-judge LLM evaluation via
``BaseEvaluationStep``, following the same paradigm as MML/FlipAttack.

Supports multiple judges (HarmBench, JailbreakBench, Nuanced), merges
their scores, computes ``best_score`` / ``success``, syncs to server,
and logs per-judge ASR.
"""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.server.client import AuthenticatedClient


def _build_prompt_prefix(item: Dict[str, Any]) -> str:
    """Build the 'prefix' field from FC-Attack item data."""
    full_prompt = item.get("full_prompt")
    if full_prompt:
        return str(full_prompt)
    return item.get("text_prompt", "")


class FCEvaluation(BaseEvaluationStep):
    """
    FC-Attack evaluation step using the shared multi-judge pipeline.

    Transforms FC response data into the standard evaluation
    format ``(goal, prefix, completion)``, runs all configured judges,
    merges results back, and syncs to the server.
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
        Evaluate FC-Attack responses using the multi-judge pipeline.

        Args:
            input_data: Dicts from generation step (with ``response``,
                        ``goal``, ``text_prompt``, etc.).

        Returns:
            Same list enriched with judge columns, ``best_score``, ``success``.
        """
        if not input_data:
            return input_data

        self._statistics["input_count"] = len(input_data)

        fc_params = (
            self._raw_config.get("fc_params")
            or self._raw_config.get("tfc_params")
            or {}
        )
        judges_config = self._resolve_judges_from_config(technique_params=fc_params)

        self.logger.info(
            f"Evaluating {len(input_data)} responses with {len(judges_config)} judge(s)"
        )

        if self._tracker:
            self.logger.info("Evaluation tracking via Tracker enabled")

        # Transform to evaluation format
        eval_rows, error_indices = self._transform_to_eval_rows(input_data)

        if not eval_rows:
            self.logger.warning("No valid rows to evaluate (all errors)")
            self._enrich_items_with_scores(input_data, error_indices)
            return input_data

        # Build evaluator base config
        base_config = self._build_base_eval_config(technique_params=fc_params)

        # Run multi-judge evaluation
        evaluated_rows = self._run_evaluation(eval_rows, judges_config, base_config)
        self._statistics["evaluated_count"] = len(evaluated_rows)

        # Merge results back into input_data
        self._merge_back_to_input(input_data, evaluated_rows, error_indices)

        # Compute best_score / success
        self._enrich_items_with_scores(input_data, error_indices)

        # Tracker integration
        self._update_tracker(input_data, evaluator_prefix="fc_eval")

        # Sync to server
        judge_keys = self._build_judge_keys_from_data(input_data)
        self._sync_to_server(input_data, judge_keys)

        # Log ASR
        self._log_evaluation_asr(input_data)

        return input_data

    @staticmethod
    def _transform_to_eval_rows(
        input_data: List[Dict[str, Any]],
    ) -> tuple:
        """
        Convert FC-Attack items to ``(goal, prefix, completion)`` rows.

        Returns:
            ``(eval_rows, error_indices)``
        """
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
                    "prefix": _build_prompt_prefix(item),
                    "completion": item.get("response", "") or "",
                }
            )

        return eval_rows, error_indices

    def _merge_back_to_input(
        self,
        input_data: List[Dict[str, Any]],
        evaluated_rows: List[Dict[str, Any]],
        error_indices: set,
    ) -> None:
        """Merge evaluated judge columns back into *input_data* items."""
        all_judge_cols: set = set()
        for cols in self.JUDGE_COLUMN_MAP.values():
            all_judge_cols.update(cols)

        lookup: Dict[tuple, Dict[str, Any]] = {}
        for row in evaluated_rows:
            key = (
                self._normalize_merge_key("goal", row.get("goal")),
                self._normalize_merge_key("prefix", row.get("prefix")),
                self._normalize_merge_key("completion", row.get("completion")),
            )
            lookup[key] = {col: row[col] for col in all_judge_cols if col in row}

        for idx, item in enumerate(input_data):
            if idx in error_indices:
                continue
            key = (
                self._normalize_merge_key("goal", item.get("goal")),
                self._normalize_merge_key("prefix", _build_prompt_prefix(item)),
                self._normalize_merge_key("completion", item.get("response")),
            )
            merged = lookup.get(key, {})
            item.update(merged)


def execute(
    input_data: List[Dict],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict]:
    """Pipeline-compatible function entry point."""
    step = FCEvaluation(config=config, logger=logger, client=client)
    return step.execute(input_data=input_data)
