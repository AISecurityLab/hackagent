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
Evaluation stage module for AdvPrefix attacks.

This module implements the Evaluation stage of the AdvPrefix pipeline, which consolidates
judge-based evaluation, result aggregation, and prefix selection into a cohesive
class-based design that improves:
- Code organization and maintainability
- State management and configuration handling
- Testing and mocking capabilities
- Logging and tracking throughout the pipeline

The module provides functionality for:
- Automated evaluation using judge models
- Result aggregation and statistical analysis
- Optimal prefix selection using multi-criteria optimization
- Unified pipeline execution with proper error handling
- Integration with various judge model backends
- Customizable evaluation, aggregation, and selection strategies
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import (
    BaseEvaluationStep,
    JUDGE_MEAN_COLUMN_MAP,
)
from hackagent.client import AuthenticatedClient

from .config import EvaluationPipelineConfig
from .utils import handle_empty_input, log_errors

# ============================================================================
# CONSTANTS (technique-specific; shared ones live in BaseEvaluationStep)
# ============================================================================

GROUP_KEYS = ["goal", "prefix"]


# ============================================================================
# MAIN PIPELINE CLASS
# ============================================================================


class EvaluationPipeline(BaseEvaluationStep):
    """
    Evaluation pipeline for the AdvPrefix attack.

    Extends ``BaseEvaluationStep`` (multi-judge evaluation, merge, sync)
    and adds AdvPrefix-specific aggregation and selection stages.

    Architecture:
        - Judge Evaluation (inherited): Run judge models on completions
        - Aggregation: Aggregate evaluation results by goal/prefix
        - Selection: Select best prefixes using multi-criteria optimization
        - Orchestration: execute() method coordinates the full pipeline

    Example:
        pipeline = EvaluationPipeline(
            config=config_dict,
            logger=logger,
            client=client
        )
        results = pipeline.execute(input_data=completion_data)
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        client: AuthenticatedClient,
    ):
        super().__init__(config, logger, client)

        # Convert raw config dict to typed dataclass
        self.config = (
            EvaluationPipelineConfig.from_dict(config)
            if isinstance(config, dict)
            else config
        )

        # Extend statistics for aggregation/selection stages
        self._statistics.update(
            {
                "aggregated_count": 0,
                "selected_count": 0,
            }
        )

        self.logger.info("EvaluationPipeline initialized")

    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================

    @handle_empty_input("Evaluation Stage", empty_result=[])
    @log_errors("Evaluation Stage")
    def execute(self, input_data: List[Dict]) -> List[Dict]:
        """
        Execute the complete Evaluation stage: judge evaluation, aggregation, and selection.

        This is the main entry point that orchestrates all sub-processes:
        1. Judge Evaluation: Evaluate completions with judge models
        2. Aggregation: Aggregate evaluation results by goal/prefix
        3. Selection: Select optimal prefixes using multi-criteria optimization

        Args:
            input_data: List of dicts containing completion data from Execution stage

        Returns:
            List of selected prefix dictionaries ready for final output
        """
        # Debug: Log input data keys
        if input_data:
            sample = input_data[0]
            self.logger.info(
                f"📋 Evaluation input: {len(input_data)} rows, sample keys: {list(sample.keys())}"
            )
            result_ids_in_input = [
                r.get("result_id") for r in input_data if r.get("result_id")
            ]
            self.logger.info(
                f"📋 Evaluation input has {len(result_ids_in_input)} result_ids"
            )

        self._statistics["input_count"] = len(input_data)

        # Judge Evaluation (via inherited multi-judge pipeline)
        self.logger.info(
            f"Judge Evaluation: Starting evaluation for {len(input_data)} completions"
        )
        judges_config = self.config.judges
        base_eval_config = self._build_base_eval_config()
        evaluated_data = self._run_evaluation(
            input_data, judges_config, base_eval_config
        )
        self._statistics["evaluated_count"] = len(evaluated_data)

        if not evaluated_data:
            self.logger.warning("No data after evaluation")
            return []

        # Sync evaluation results to server
        judge_keys = self._build_judge_keys_from_data(evaluated_data)
        self._sync_to_server(evaluated_data, judge_keys)

        # Aggregation
        self.logger.info(
            f"Aggregation: Aggregating {len(evaluated_data)} evaluation results"
        )
        aggregated_data = self._run_aggregation(evaluated_data)
        self._statistics["aggregated_count"] = len(aggregated_data)

        if not aggregated_data:
            self.logger.warning("No data after aggregation")
            return []

        # Selection
        self.logger.info(
            f"Selection: Selecting best prefixes from {len(aggregated_data)} candidates"
        )
        selected_data = self._run_selection(aggregated_data)
        self._statistics["selected_count"] = len(selected_data)

        self._log_pipeline_statistics()
        return selected_data

    # ========================================================================
    # AGGREGATION METHODS
    # ========================================================================

    def _run_aggregation(self, input_data: List[Dict]) -> List[Dict]:
        """
        Execute aggregation: Aggregate evaluation results.

        Handles:
        - NLL filtering based on threshold
        - Grouping by goal and prefix
        - Statistical aggregation (mean, count)
        - Metadata preservation
        """
        # Apply NLL filtering
        max_ce_threshold = self.config.max_ce
        if max_ce_threshold is not None:
            try:
                max_ce_threshold = float(max_ce_threshold)
                input_data = self._filter_by_nll(input_data, max_ce_threshold)
            except ValueError:
                self.logger.warning(f"Invalid max_ce value: {max_ce_threshold}")

        # Get available judge columns
        config_judges = [
            j.get("type") or j.get("evaluator_type")
            for j in self.config.judges
            if isinstance(j, dict)
        ]
        available_judges_agg_cols = self._get_available_judge_agg_cols(
            input_data, config_judges
        )

        if not available_judges_agg_cols:
            self.logger.error("No recognized evaluation keys found for aggregation")
            return input_data

        # Validate required keys
        if not input_data:
            return []

        sample_keys = set(input_data[0].keys())
        if not all(key in sample_keys for key in GROUP_KEYS):
            missing_keys = [key for key in GROUP_KEYS if key not in sample_keys]
            self.logger.error(f"Missing grouping keys: {missing_keys}")
            return input_data

        # Group and aggregate
        groups = defaultdict(list)
        for item in input_data:
            key = tuple(item.get(k) for k in GROUP_KEYS)
            groups[key].append(item)

        aggregated_results = []
        for group_key, group_items in groups.items():
            result = {k: v for k, v in zip(GROUP_KEYS, group_key)}

            # Preserve first values
            result["prefix_nll"] = group_items[0].get("prefix_nll")
            result["model_name"] = group_items[0].get("model_name")
            result["meta_prefix"] = group_items[0].get("meta_prefix")
            result["temperature"] = group_items[0].get("temperature")
            result["n_eval_samples"] = len(group_items)

            # Preserve result_id (all items in a goal share the same result_id)
            result_id = next(
                (
                    item.get("result_id")
                    for item in group_items
                    if item.get("result_id")
                ),
                None,
            )
            if result_id:
                result["result_id"] = result_id

            # Calculate judge statistics
            for judge_type, col_name in available_judges_agg_cols.items():
                values = []
                for item in group_items:
                    val = item.get(col_name)
                    if val is not None:
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            pass

                if values:
                    result[f"{col_name}_mean"] = sum(values) / len(values)
                    result[f"{col_name}_count"] = len(values)
                else:
                    result[f"{col_name}_mean"] = None
                    result[f"{col_name}_count"] = 0

            aggregated_results.append(result)

        return aggregated_results

    def _filter_by_nll(self, data: List[Dict], max_ce_threshold: float) -> List[Dict]:
        """Filter data by cross-entropy threshold."""
        if not any("prefix_nll" in item for item in data):
            self.logger.warning("prefix_nll key not found, skipping NLL filtering")
            return data

        try:
            filtered = [
                item
                for item in data
                if item.get("prefix_nll", float("inf")) < max_ce_threshold
            ]
            self.logger.info(f"NLL filtering: {len(data)} -> {len(filtered)} items")
            return filtered
        except Exception as e:
            self.logger.error(f"Error during NLL filtering: {e}")
            return data

    # ========================================================================
    # SELECTION METHODS
    # ========================================================================

    def _run_selection(self, input_data: List[Dict]) -> List[Dict]:
        """
        Execute selection: Select optimal prefixes.

        Handles:
        - Multi-criteria scoring (PASR + NLL)
        - Tolerance-based filtering
        - Diversity-preserving selection
        - Sub-prefix elimination
        """
        judge_configs = self.config.judges

        if not isinstance(judge_configs, list) or not judge_configs:
            self.logger.error("No judges configured for selection")
            return input_data

        # Extract and validate judge types
        judge_types_found = []
        sample_keys = set(input_data[0].keys()) if input_data else set()

        for judge_config in judge_configs:
            if not isinstance(judge_config, dict):
                continue

            judge_type = judge_config.get("type") or judge_config.get("evaluator_type")
            if not judge_type:
                continue

            if judge_type not in JUDGE_MEAN_COLUMN_MAP:
                self.logger.error(f"Unknown judge type for selection: {judge_type}")
                continue

            expected_key = JUDGE_MEAN_COLUMN_MAP[judge_type]
            if expected_key not in sample_keys:
                self.logger.warning(f"Missing key '{expected_key}' for selection")
                continue

            if judge_type not in judge_types_found:
                judge_types_found.append(judge_type)

        if not judge_types_found:
            self.logger.error("No valid judges found for selection")
            return input_data

        # Calculate selection scores
        for item in input_data:
            item["pasr"] = self._calculate_combined_pasr(item, judge_types_found)

        # Group by goal and select
        groups = defaultdict(list)
        for item in input_data:
            groups[item["goal"]].append(item)

        selected_prefixes = []
        for goal, group in groups.items():
            if not group or all(item.get("pasr") is None for item in group):
                self.logger.warning(
                    f"Skipping goal '{goal[:50]}...' due to invalid scores"
                )
                continue

            # Select prefixes for this goal
            goal_selections = self._select_prefixes_for_goal(group)
            selected_prefixes.extend(goal_selections)

        return selected_prefixes

    def _select_prefixes_for_goal(self, group: List[Dict]) -> List[Dict]:
        """Select top prefixes for a single goal using multi-criteria optimization."""
        # First: Select prefix with highest PASR (best jailbreak success rate)
        first_selection = max(
            (item for item in group if item.get("pasr") is not None),
            key=lambda x: x["pasr"],
        )

        # Second: Filter by PASR tolerance
        remaining_candidates = [
            item
            for item in group
            if item != first_selection
            and item.get("pasr", 0)
            >= first_selection.get("pasr", 0) - self.config.pasr_tol
        ]

        # Third: Filter by NLL tolerance
        valid_candidates = [
            item
            for item in remaining_candidates
            if item.get("prefix_nll", float("inf"))
            <= first_selection.get("prefix_nll", float("inf")) + self.config.nll_tol
        ]

        # Initialize selections
        selections = [first_selection]

        # Fourth: Iteratively select additional prefixes
        for _ in range(self.config.n_prefixes_per_goal - 1):
            # Remove sub-prefix candidates
            valid_candidates = [
                item
                for item in valid_candidates
                if not any(
                    str(item.get("prefix", "")).startswith(str(sel.get("prefix", "")))
                    for sel in selections
                )
            ]

            if not valid_candidates:
                break

            if all(item.get("prefix_nll") is None for item in valid_candidates):
                self.logger.warning(
                    "Cannot select next prefix due to missing NLL scores"
                )
                break

            # Select next with lowest NLL
            next_selection = min(
                (
                    item
                    for item in valid_candidates
                    if item.get("prefix_nll") is not None
                ),
                key=lambda x: x["prefix_nll"],
            )
            selections.append(next_selection)
            valid_candidates = [
                item for item in valid_candidates if item != next_selection
            ]

        return selections

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _log_pipeline_statistics(self):
        """Log comprehensive pipeline execution statistics."""
        stats = self._statistics
        self.logger.info("=" * 60)
        self.logger.info("Evaluation Pipeline Statistics:")
        self.logger.info(f"  Input completions:       {stats['input_count']}")
        self.logger.info(f"  After evaluation:        {stats['evaluated_count']}")
        self.logger.info(f"  After aggregation:       {stats['aggregated_count']}")
        self.logger.info(f"  Final selected:          {stats['selected_count']}")

        if stats["successful_judges"]:
            self.logger.info(
                f"  Successful judges:       {', '.join(stats['successful_judges'])}"
            )
        if stats["failed_judges"]:
            self.logger.warning(
                f"  Failed judges:           {', '.join(stats['failed_judges'])}"
            )

        if stats["input_count"] > 0:
            retention = (stats["selected_count"] / stats["input_count"]) * 100
            self.logger.info(f"  Overall retention:       {retention:.1f}%")

        self.logger.info("=" * 60)
