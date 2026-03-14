# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
FlipAttack evaluation module.

Evaluates attack success using multi-judge LLM evaluation via
``BaseEvaluationStep``, following the same paradigm as AdvPrefix.

Supports multiple judges (HarmBench, JailbreakBench, Nuanced), merges
their scores, computes ``best_score`` / ``success``, syncs to server,
and logs per-judge ASR.

Result Tracking:
    Uses Tracker (passed via config["_tracker"]) to add evaluation traces
    per goal and sync evaluation status to server.
"""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.client import AuthenticatedClient


# ============================================================================
# DATA HELPERS
# ============================================================================


def _build_prompt_prefix(item: Dict[str, Any]) -> str:
    """Build the 'prefix' field from FlipAttack item data."""
    full_prompt = item.get("full_prompt")
    if full_prompt:
        return str(full_prompt)

    parts = [item.get("system_prompt", ""), item.get("user_prompt", "")]
    return "\n\n".join([p for p in parts if p]).strip()


# ============================================================================
# EVALUATION STEP
# ============================================================================


class FlipAttackEvaluation(BaseEvaluationStep):
    """
    FlipAttack evaluation step using the shared multi-judge pipeline.

    Transforms FlipAttack response data into the standard evaluation
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

    # ------------------------------------------------------------------ #
    # PUBLIC INTERFACE
    # ------------------------------------------------------------------ #

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluate FlipAttack responses using the multi-judge pipeline.

        Args:
            input_data: Dicts from generation step (with ``response``,
                        ``goal``, ``full_prompt``, etc.).

        Returns:
            Same list enriched with judge columns, ``best_score``, ``success``.
        """
        if not input_data:
            return input_data

        self._statistics["input_count"] = len(input_data)

        fa_params = self._raw_config.get("flipattack_params", {})
        judges_config = self._resolve_judges_from_config(technique_params=fa_params)

        self.logger.info(
            f"Evaluating {len(input_data)} responses with "
            f"{len(judges_config)} judge(s)…"
        )

        if self._tracker:
            self.logger.info("📊 Evaluation tracking via Tracker enabled")

        # ----- Transform to evaluation format ----- #
        eval_rows, error_indices = self._transform_to_eval_rows(input_data)

        if not eval_rows:
            self.logger.warning("No valid rows to evaluate (all errors)")
            self._enrich_items_with_scores(input_data, error_indices)
            return input_data

        # ----- Build evaluator base config ----- #
        base_config = self._build_base_eval_config(technique_params=fa_params)

        # ----- Run multi-judge evaluation ----- #
        evaluated_rows = self._run_evaluation(eval_rows, judges_config, base_config)
        self._statistics["evaluated_count"] = len(evaluated_rows)

        # ----- Merge results back into input_data ----- #
        self._merge_back_to_input(input_data, evaluated_rows, error_indices)

        # ----- Compute best_score / success ----- #
        self._enrich_items_with_scores(input_data, error_indices)

        # ----- Tracker integration ----- #
        self._update_tracker(
            input_data,
            evaluator_prefix="flipattack_eval",
        )

        # ----- Sync to server ----- #
        judge_keys = self._build_judge_keys_from_data(input_data)
        self._sync_to_server(input_data, judge_keys)

        # ----- Log ASR ----- #
        self._log_evaluation_asr(input_data)

        return input_data

    # ------------------------------------------------------------------ #
    # PRIVATE HELPERS
    # ------------------------------------------------------------------ #

    @staticmethod
    def _transform_to_eval_rows(
        input_data: List[Dict[str, Any]],
    ) -> tuple:
        """
        Convert FlipAttack items to ``(goal, prefix, completion)`` rows.

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
        """
        Merge evaluated judge columns back into *input_data* items.

        Uses (goal, prefix, completion) lookup to match rows.
        """
        # Collect all judge columns
        all_judge_cols: set = set()
        for cols in self.JUDGE_COLUMN_MAP.values():
            all_judge_cols.update(cols)

        # Build lookup from evaluated rows
        lookup: Dict[tuple, Dict[str, Any]] = {}
        for row in evaluated_rows:
            key = (
                self._normalize_merge_key("goal", row.get("goal")),
                self._normalize_merge_key("prefix", row.get("prefix")),
                self._normalize_merge_key("completion", row.get("completion")),
            )
            lookup[key] = {col: row[col] for col in all_judge_cols if col in row}

        # Apply to input_data
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


# ============================================================================
# MODULE-LEVEL execute() — backward-compatible pipeline interface
# ============================================================================


def execute(
    input_data: List[Dict],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict]:
    """
    Pipeline-compatible function entry point.

    Wraps ``FlipAttackEvaluation`` so that ``attack.py`` can reference
    ``evaluation.execute`` directly in the pipeline step definition.
    """
    step = FlipAttackEvaluation(config=config, logger=logger, client=client)
    return step.execute(input_data=input_data)
