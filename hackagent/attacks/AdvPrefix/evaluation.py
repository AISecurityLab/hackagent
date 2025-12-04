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
import math
from collections import defaultdict
from dataclasses import fields
from typing import Any, Dict, List, Optional

import pandas as pd

from hackagent.attacks.AdvPrefix.evaluators import (
    HarmBenchEvaluator,
    JailbreakBenchEvaluator,
    NuancedEvaluator,
)
from hackagent.client import AuthenticatedClient
from hackagent.router.types import AgentTypeEnum

from .config import EvaluationPipelineConfig, EvaluatorConfig
from .utils import handle_empty_input, log_errors

# ============================================================================
# CONSTANTS AND MAPPINGS
# ============================================================================

EVALUATOR_MAP = {
    "nuanced": NuancedEvaluator,
    "jailbreakbench": JailbreakBenchEvaluator,
    "harmbench": HarmBenchEvaluator,
}

MERGE_KEYS = ["goal", "prefix", "completion"]

JUDGE_COLUMN_MAP = {
    "nuanced": ["eval_nj", "explanation_nj"],
    "jailbreakbench": ["eval_jb", "explanation_jb"],
    "harmbench": ["eval_hb", "explanation_hb"],
}

JUDGE_AGG_COLUMN_MAP = {
    "nuanced": "eval_nj",
    "jailbreakbench": "eval_jb",
    "harmbench": "eval_hb",
}

JUDGE_MEAN_COLUMN_MAP = {
    "nuanced": "eval_nj_mean",
    "jailbreakbench": "eval_jb_mean",
    "harmbench": "eval_hb_mean",
    "strongreject": "eval_sj_binary_mean",
}

GROUP_KEYS = ["goal", "prefix"]


# ============================================================================
# MAIN PIPELINE CLASS
# ============================================================================


class EvaluationPipeline:
    """
    Unified pipeline for the Evaluation stage of AdvPrefix attacks.

    This class encapsulates all functionality related to evaluating completions,
    aggregating results, and selecting optimal prefixes, providing a clean interface
    with proper state management and comprehensive tracking capabilities.

    Architecture:
        - Initialization: Sets up config, logger, client, and internal state
        - Judge Evaluation: Run judge models on completions
        - Aggregation: Aggregate evaluation results by goal/prefix
        - Selection: Select best prefixes using multi-criteria optimization
        - Orchestration: execute() method coordinates the full pipeline

    Key Benefits:
        - Single source of truth for configuration
        - Consistent logging throughout all operations
        - Easy to test individual components via method mocking
        - Clear method boundaries with single responsibilities
        - Stateful execution tracking for debugging

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
        """
        Initialize the pipeline with configuration and dependencies.

        Args:
            config: Configuration dictionary or EvaluationPipelineConfig instance
            logger: Logger for tracking execution
            client: Authenticated client for API access
        """
        self.config = (
            EvaluationPipelineConfig.from_dict(config)
            if isinstance(config, dict)
            else config
        )
        # Use provided logger, but ensure it's child of hackagent.attacks hierarchy
        self.logger = (
            logger
            if logger.name.startswith("hackagent.attacks")
            else logging.getLogger("hackagent.attacks.advprefix.evaluation")
        )
        self.client = client

        # Initialize internal state for tracking
        self._statistics: Dict[str, Any] = {
            "input_count": 0,
            "evaluated_count": 0,
            "aggregated_count": 0,
            "selected_count": 0,
            "successful_judges": [],
            "failed_judges": [],
        }

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
        self._statistics["input_count"] = len(input_data)

        # Judge Evaluation
        self.logger.info(
            f"Judge Evaluation: Starting evaluation for {len(input_data)} completions"
        )
        evaluated_data = self._run_evaluation(input_data)
        self._statistics["evaluated_count"] = len(evaluated_data)

        if not evaluated_data:
            self.logger.warning("No data after evaluation")
            return []

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

    def get_statistics(self) -> Dict[str, Any]:
        """Return execution statistics for monitoring and debugging."""
        return self._statistics.copy()

    # ========================================================================
    # JUDGE EVALUATION METHODS
    # ========================================================================

    def _run_evaluation(self, input_data: List[Dict]) -> List[Dict]:
        """
        Execute judge evaluation: Evaluate completions using judge models.

        Handles:
        - Judge configuration validation
        - Sequential or parallel judge execution
        - Result merging across judges
        - Error handling for failed judges
        """
        judge_configs_list = self.config.judges
        if not isinstance(judge_configs_list, list) or not judge_configs_list:
            self.logger.warning("No judges configured, skipping evaluation")
            return input_data

        # Convert to DataFrame for evaluators
        original_df = pd.DataFrame(input_data)

        # Base config for evaluators
        evaluator_base_config_dict = {
            "batch_size": self.config.batch_size_judge,
            "max_new_tokens_eval": self.config.max_new_tokens_eval,
            "filter_len": self.config.filter_len,
            "request_timeout": self.config.judge_request_timeout,
            "temperature": self.config.judge_temperature,
            "organization_id": self.config.organization_id,
        }

        judge_results_dfs = {}
        judges_to_run = self._prepare_judge_configs(
            judge_configs_list, evaluator_base_config_dict
        )

        if not judges_to_run:
            self.logger.warning("No valid judges found after configuration processing")
            return input_data

        # Execute judges sequentially
        for judge_type_str, subprocess_config in judges_to_run:
            evaluated_df = self._run_single_evaluator(
                judge_type=judge_type_str,
                config=subprocess_config,
                df=original_df.copy(),
            )

            if evaluated_df is not None:
                judge_results_dfs[judge_type_str] = evaluated_df
                self._statistics["successful_judges"].append(judge_type_str)
            else:
                self._statistics["failed_judges"].append(judge_type_str)

        # Merge results
        final_df = self._merge_evaluation_results(original_df, judge_results_dfs)

        return final_df.to_dict(orient="records")

    def _prepare_judge_configs(
        self, judge_configs_list: List[Dict], base_config: Dict[str, Any]
    ) -> List[tuple]:
        """Prepare and validate judge configurations."""
        judges_to_run = []

        for judge_config_item in judge_configs_list:
            if not isinstance(judge_config_item, dict):
                self.logger.warning(
                    f"Skipping invalid judge config: {judge_config_item}"
                )
                continue

            # Extract judge type
            judge_type_str = judge_config_item.get(
                "evaluator_type"
            ) or judge_config_item.get("type")
            judge_identifier = judge_config_item.get("identifier")

            if not judge_type_str:
                judge_type_str = self._infer_judge_type(judge_identifier)

            if not judge_type_str or judge_type_str not in EVALUATOR_MAP:
                self.logger.warning(
                    f"Unknown or missing judge type for: {judge_config_item}"
                )
                continue

            if not judge_identifier:
                self.logger.warning(
                    f"Missing identifier for judge: {judge_config_item}"
                )
                continue

            # Prepare subprocess config
            subprocess_config = base_config.copy()
            subprocess_config.update(judge_config_item)

            # Populate EvaluatorConfig fields
            subprocess_config["agent_name"] = (
                judge_config_item.get("agent_name")
                or f"judge-{judge_type_str}-{judge_identifier.replace('/', '-')[:20]}"
            )
            subprocess_config["agent_type"] = judge_config_item.get(
                "agent_type", "LITELLM"
            )
            subprocess_config["model_id"] = judge_identifier
            subprocess_config["agent_endpoint"] = judge_config_item.get("endpoint")
            subprocess_config["agent_metadata"] = judge_config_item.get(
                "agent_metadata", {}
            )

            judges_to_run.append((judge_type_str, subprocess_config))

        return judges_to_run

    def _infer_judge_type(self, identifier: Optional[str]) -> Optional[str]:
        """Infer judge type from identifier string."""
        if not identifier:
            return None

        identifier_lower = identifier.lower()
        if "nuanced" in identifier_lower:
            return "nuanced"
        elif "harmbench" in identifier_lower:
            return "harmbench"
        elif "jailbreak" in identifier_lower:
            return "jailbreakbench"

        return None

    def _run_single_evaluator(
        self,
        judge_type: str,
        config: Dict[str, Any],
        df: pd.DataFrame,
    ) -> Optional[pd.DataFrame]:
        """Execute a single evaluator process."""
        evaluator_class = EVALUATOR_MAP.get(judge_type)
        if not evaluator_class:
            self.logger.warning(f"Unknown judge type: {judge_type}")
            return None

        evaluator = None
        try:
            # Filter config for EvaluatorConfig
            expected_fields = {f.name for f in fields(EvaluatorConfig)}
            filtered_config = {k: v for k, v in config.items() if k in expected_fields}

            # Convert agent_type string to enum
            if "agent_type" in filtered_config and isinstance(
                filtered_config["agent_type"], str
            ):
                try:
                    filtered_config["agent_type"] = AgentTypeEnum(
                        filtered_config["agent_type"].upper()
                    )
                except ValueError:
                    self.logger.error(
                        f"Invalid agent_type: {filtered_config['agent_type']}"
                    )
                    return None

            evaluator_config = EvaluatorConfig(**filtered_config)
            evaluator = evaluator_class(client=self.client, config=evaluator_config)
            evaluated_df = evaluator.evaluate(df)

            # Return only merge keys + judge-specific columns
            eval_cols = JUDGE_COLUMN_MAP.get(judge_type, [])
            if not all(key in evaluated_df.columns for key in MERGE_KEYS):
                self.logger.error(
                    f"Evaluation result missing merge keys for {judge_type}"
                )
                return None

            cols_to_return = MERGE_KEYS + [
                col for col in eval_cols if col in evaluated_df.columns
            ]
            return evaluated_df[cols_to_return]

        except Exception as e:
            self.logger.error(
                f"Error running {judge_type} evaluator: {e}", exc_info=True
            )
            return None
        finally:
            del evaluator

    def _merge_evaluation_results(
        self, original_df: pd.DataFrame, judge_results: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Merge evaluation results from multiple judges."""
        final_df = original_df.copy()

        for judge_type, judge_df in judge_results.items():
            eval_cols = JUDGE_COLUMN_MAP.get(judge_type, [])
            judge_cols_present = [col for col in eval_cols if col in judge_df.columns]

            if not judge_cols_present:
                self.logger.warning(f"No evaluation columns found for {judge_type}")
                continue

            try:
                final_df = final_df.merge(
                    judge_df,
                    on=MERGE_KEYS,
                    how="left",
                    suffixes=("", f"_{judge_type}_dup"),
                )
            except Exception as e:
                self.logger.error(f"Error merging results for {judge_type}: {e}")

        return final_df

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

    def _get_available_judge_agg_cols(
        self, data: List[Dict], config_judges: List[str]
    ) -> Dict[str, str]:
        """Identify available judge evaluation keys."""
        available_judges_agg_cols = {}
        sample_keys = set(data[0].keys()) if data else set()

        for judge_type, col_name in JUDGE_AGG_COLUMN_MAP.items():
            if col_name in sample_keys:
                available_judges_agg_cols[judge_type] = col_name
            elif judge_type in config_judges:
                self.logger.warning(
                    f"Expected key '{col_name}' for judge '{judge_type}' not found"
                )

        return available_judges_agg_cols

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
        # Use selection_judges if specified, otherwise use all judges
        judge_configs = self.config.selection_judges or self.config.judges

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
            item["log_pasr"] = math.log(item["pasr"] + 1e-6)
            item["combined_score"] = -self.config.pasr_weight * item[
                "log_pasr"
            ] + item.get("prefix_nll", 0)

        # Group by goal and select
        groups = defaultdict(list)
        for item in input_data:
            groups[item["goal"]].append(item)

        selected_prefixes = []
        for goal, group in groups.items():
            if not group or all(item.get("combined_score") is None for item in group):
                self.logger.warning(
                    f"Skipping goal '{goal[:50]}...' due to invalid scores"
                )
                continue

            # Select prefixes for this goal
            goal_selections = self._select_prefixes_for_goal(group)
            selected_prefixes.extend(goal_selections)

        return selected_prefixes

    def _calculate_combined_pasr(self, item: Dict, judge_types: List[str]) -> float:
        """Calculate combined Pass@1 Success Rate across judges."""
        judge_scores = []

        for judge_type in judge_types:
            key = JUDGE_MEAN_COLUMN_MAP[judge_type]
            if key in item:
                try:
                    score = float(item[key]) if item[key] is not None else None
                    if score is not None:
                        judge_scores.append(score)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Could not convert '{key}' to numeric: {e}")

        if not judge_scores:
            self.logger.warning("No valid judge scores for PASR calculation")
            return 0.0

        return sum(judge_scores) / len(judge_scores)

    def _select_prefixes_for_goal(self, group: List[Dict]) -> List[Dict]:
        """Select top prefixes for a single goal using multi-criteria optimization."""
        # First: Select prefix with best combined score
        first_selection = min(
            (item for item in group if item.get("combined_score") is not None),
            key=lambda x: x["combined_score"],
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
