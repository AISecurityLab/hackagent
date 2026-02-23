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
Base evaluation step for attack pipeline stages.

This module provides ``BaseEvaluationStep``, the shared foundation for all
evaluation pipeline stages across attack techniques (AdvPrefix, FlipAttack, etc.).

It centralises the common logic that was previously duplicated:
- Multi-judge evaluation orchestration
- Judge type inference from model identifiers
- Agent type resolution (string / enum → ``AgentTypeEnum``)
- ``EvaluatorConfig`` construction from raw judge config dicts
- Single evaluator instantiation and execution
- Result merging via lookup keys ``(goal, prefix, completion)``
- Server sync via ``sync_evaluation_to_server``
- Best-score computation across judge columns
- ASR logging

Subclasses only need to implement ``execute()`` and, optionally, override
configuration or data-transformation hooks.

Usage:
    from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep

    class MyEvaluation(BaseEvaluationStep):
        def execute(self, input_data):
            ...
"""

import logging
from dataclasses import fields
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.attacks.evaluator.judge_evaluators import EVALUATOR_MAP
from hackagent.attacks.evaluator.sync import sync_evaluation_to_server
from hackagent.attacks.techniques.advprefix.config import EvaluatorConfig
from hackagent.client import AuthenticatedClient
from hackagent.router.types import AgentTypeEnum

if TYPE_CHECKING:
    from hackagent.router.tracking import Tracker


# ============================================================================
# CONSTANTS — shared across all evaluation stages
# ============================================================================

MERGE_KEYS: List[str] = ["goal", "prefix", "completion"]

JUDGE_TYPE_LABELS: Dict[str, str] = {
    "jailbreakbench": "JailbreakBench",
    "harmbench": "HarmBench",
    "nuanced": "Nuanced",
    "on_topic": "OnTopic",
}

JUDGE_COLUMN_MAP: Dict[str, List[str]] = {
    "nuanced": ["eval_nj", "explanation_nj"],
    "jailbreakbench": ["eval_jb", "explanation_jb"],
    "harmbench": ["eval_hb", "explanation_hb"],
    "on_topic": ["eval_on_topic", "explanation_on_topic"],
}

JUDGE_AGG_COLUMN_MAP: Dict[str, str] = {
    "nuanced": "eval_nj",
    "jailbreakbench": "eval_jb",
    "harmbench": "eval_hb",
    "on_topic": "eval_on_topic",
}

JUDGE_MEAN_COLUMN_MAP: Dict[str, str] = {
    "nuanced": "eval_nj_mean",
    "jailbreakbench": "eval_jb_mean",
    "harmbench": "eval_hb_mean",
    "strongreject": "eval_sj_binary_mean",
    "on_topic": "eval_on_topic_mean",
}


# ============================================================================
# BASE CLASS
# ============================================================================


class BaseEvaluationStep:
    """
    Shared foundation for evaluation pipeline stages.

    Provides multi-judge evaluation, result merging, server sync,
    best-score computation, and ASR logging.  Subclasses implement
    ``execute()`` with technique-specific data transformation.
    """

    # Expose constants as class attributes for easy subclass access
    MERGE_KEYS = MERGE_KEYS
    JUDGE_TYPE_LABELS = JUDGE_TYPE_LABELS
    JUDGE_COLUMN_MAP = JUDGE_COLUMN_MAP
    JUDGE_AGG_COLUMN_MAP = JUDGE_AGG_COLUMN_MAP
    JUDGE_MEAN_COLUMN_MAP = JUDGE_MEAN_COLUMN_MAP

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        client: AuthenticatedClient,
    ):
        """
        Extract common tracking context and dependencies.

        Args:
            config: Step configuration dictionary (may contain ``_run_id``,
                     ``_client``, ``_tracker`` internal keys).
            logger: Logger instance.
            client: ``AuthenticatedClient`` for backend API calls.
        """
        # Store raw config for subclass access
        self._raw_config: Dict[str, Any] = config if isinstance(config, dict) else {}

        self._run_id: Optional[str] = (
            config.get("_run_id") if isinstance(config, dict) else None
        )
        self._tracking_client = (
            config.get("_client") if isinstance(config, dict) else None
        )
        self._tracker: Optional["Tracker"] = (
            config.get("_tracker") if isinstance(config, dict) else None
        )
        self.logger = (
            logger
            if logger.name.startswith("hackagent.attacks")
            else logging.getLogger("hackagent.attacks.evaluation")
        )
        self.client = client

        # Statistics dict — subclasses may extend
        self._statistics: Dict[str, Any] = {
            "input_count": 0,
            "evaluated_count": 0,
            "successful_judges": [],
            "failed_judges": [],
        }

    # ====================================================================
    # PUBLIC HELPERS
    # ====================================================================

    @staticmethod
    def infer_judge_type(
        identifier: Optional[str], default: Optional[str] = None
    ) -> Optional[str]:
        """
        Infer judge evaluator type from a model identifier string.

        Checks for known substrings (``harmbench``, ``nuanced``,
        ``jailbreak``) and returns the matching type key, or *default*.
        """
        if not identifier:
            return default
        identifier_lower = identifier.lower()
        if "harmbench" in identifier_lower:
            return "harmbench"
        if "nuanced" in identifier_lower:
            return "nuanced"
        if "jailbreak" in identifier_lower:
            return "jailbreakbench"
        return default

    def resolve_agent_type(self, agent_type_value: Any) -> AgentTypeEnum:
        """Convert a string, enum, or ``None`` into an ``AgentTypeEnum``."""
        if isinstance(agent_type_value, AgentTypeEnum):
            return agent_type_value
        if not agent_type_value:
            return AgentTypeEnum.OPENAI_SDK
        try:
            return AgentTypeEnum(str(agent_type_value).upper())
        except ValueError:
            self.logger.warning(
                f"Invalid agent_type '{agent_type_value}', defaulting to OPENAI_SDK"
            )
            return AgentTypeEnum.OPENAI_SDK

    # ====================================================================
    # CONFIGURATION HELPERS
    # ====================================================================

    def _build_base_eval_config(
        self, technique_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build the standard evaluator base config from ``_raw_config``.

        Looks up common judge-related keys in ``_raw_config`` first,
        then falls back to *technique_params* (e.g. ``flipattack_params``).

        Returns:
            Dict ready to be passed to ``_run_evaluation`` as
            *evaluator_base_config*.
        """
        cfg = self._raw_config
        tp = technique_params or {}
        return {
            "batch_size": (
                cfg.get("batch_size_judge") or tp.get("judge_batch_size", 1)
            ),
            "max_new_tokens_eval": (
                cfg.get("max_new_tokens_eval")
                or tp.get("judge_max_new_tokens_eval", 256)
            ),
            "filter_len": (cfg.get("filter_len") or tp.get("judge_filter_len", 10)),
            "request_timeout": (
                cfg.get("judge_request_timeout") or tp.get("judge_request_timeout", 120)
            ),
            "temperature": (
                cfg.get("judge_temperature") or tp.get("judge_temperature", 0.0)
            ),
            "max_judge_retries": (
                cfg.get("max_judge_retries") or tp.get("judge_max_retries", 1)
            ),
            "organization_id": cfg.get("organization_id"),
        }

    def _resolve_judges_from_config(
        self,
        technique_params: Optional[Dict[str, Any]] = None,
        default_judge: str = "gpt-4-0613",
        default_type: str = "jailbreakbench",
    ) -> List[Dict[str, Any]]:
        """
        Resolve the judges list from ``_raw_config``.

        If no top-level ``judges`` key is present, builds a single-judge
        fallback from *technique_params* for backward compatibility.

        Args:
            technique_params: Technique-specific params dict with legacy
                              judge keys (e.g. ``judge``, ``judge_type``).
            default_judge:    Default judge model identifier.
            default_type:     Default judge evaluator type.

        Returns:
            List of judge config dicts.
        """
        judges = self._raw_config.get("judges")
        if isinstance(judges, list) and judges:
            return judges

        tp = technique_params or {}
        judge_model = tp.get("judge", default_judge)
        judge_type = tp.get("judge_type") or self.infer_judge_type(
            judge_model, default_type
        )
        fallback: Dict[str, Any] = {
            "identifier": judge_model,
            "type": judge_type,
        }
        for key in (
            "endpoint",
            "agent_type",
            "api_key",
            "api_key_env",
            "agent_metadata",
            "agent_name",
        ):
            val = tp.get(f"judge_{key}") or tp.get(key)
            if val is not None:
                fallback[key] = val

        self.logger.info(
            f"No top-level 'judges' config \u2014 falling back to "
            f"technique_params.judge='{judge_model}'"
        )
        return [fallback]

    def _get_available_judge_agg_cols(
        self,
        data: List[Dict[str, Any]],
        config_judges: List[Optional[str]],
    ) -> Dict[str, str]:
        """
        Identify which ``JUDGE_AGG_COLUMN_MAP`` columns are present in *data*.

        Args:
            data:           Evaluated data rows.
            config_judges:  List of configured judge type strings.

        Returns:
            ``{judge_type: column_name}`` for judges whose column exists
            in the first row of *data*.
        """
        available: Dict[str, str] = {}
        sample_keys = set(data[0].keys()) if data else set()

        for judge_type, col_name in self.JUDGE_AGG_COLUMN_MAP.items():
            if col_name in sample_keys:
                available[judge_type] = col_name
            elif judge_type in config_judges:
                self.logger.warning(
                    f"Expected key '{col_name}' for judge '{judge_type}' not found"
                )

        return available

    def _calculate_combined_pasr(
        self, item: Dict[str, Any], judge_types: List[str]
    ) -> float:
        """
        Calculate combined Pass@1 Success Rate across judges.

        Averages the ``_mean`` score columns for each judge type present
        in *item*.  Returns 0.0 when no valid scores are found.
        """
        judge_scores: List[float] = []

        for judge_type in judge_types:
            key = self.JUDGE_MEAN_COLUMN_MAP.get(judge_type)
            if not key or key not in item:
                continue
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

    # ====================================================================
    # MULTI-JUDGE EVALUATION PIPELINE
    # ====================================================================

    def _run_evaluation(
        self,
        input_data: List[Dict[str, Any]],
        judges_config: List[Dict[str, Any]],
        evaluator_base_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run the multi-judge evaluation loop.

        1. Prepare and validate judge configurations.
        2. Execute each judge sequentially.
        3. Merge per-judge results into *original_data*.

        Returns the enriched data list (same objects, mutated in-place).
        """
        if not isinstance(judges_config, list) or not judges_config:
            self.logger.warning("No judges configured — skipping evaluation")
            return input_data

        original_data = [row.copy() for row in input_data]
        base_config = evaluator_base_config or {}

        judges_to_run = self._prepare_judge_configs(judges_config, base_config)
        if not judges_to_run:
            self.logger.warning("No valid judges found after configuration processing")
            return input_data

        judge_results: Dict[str, List[Dict[str, Any]]] = {}
        for judge_type_str, subprocess_config in judges_to_run:
            evaluated_data = self._run_single_evaluator(
                judge_type=judge_type_str,
                config=subprocess_config,
                data=[row.copy() for row in original_data],
            )
            if evaluated_data is not None:
                judge_results[judge_type_str] = evaluated_data
                self._statistics["successful_judges"].append(judge_type_str)
            else:
                self._statistics["failed_judges"].append(judge_type_str)

        final_data = self._merge_evaluation_results(original_data, judge_results)
        return final_data

    # ====================================================================
    # JUDGE CONFIGURATION
    # ====================================================================

    def _prepare_judge_configs(
        self,
        judge_configs_list: List[Dict[str, Any]],
        base_config: Dict[str, Any],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Validate and enrich judge configurations into ``(type, config)`` pairs."""
        judges_to_run: List[Tuple[str, Dict[str, Any]]] = []

        for judge_config_item in judge_configs_list:
            if not isinstance(judge_config_item, dict):
                self.logger.warning(
                    f"Skipping invalid judge config: {judge_config_item}"
                )
                continue

            # Determine judge type
            judge_type_str = judge_config_item.get(
                "evaluator_type"
            ) or judge_config_item.get("type")
            judge_identifier = judge_config_item.get("identifier")

            if not judge_type_str:
                judge_type_str = self.infer_judge_type(judge_identifier)

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

            # Build subprocess config
            subprocess_config = base_config.copy()
            subprocess_config.update(judge_config_item)

            subprocess_config["agent_name"] = (
                judge_config_item.get("agent_name")
                or f"judge-{judge_type_str}-{judge_identifier.replace('/', '-')[:20]}"
            )

            subprocess_config["agent_type"] = judge_config_item.get(
                "agent_type", "OPENAI_SDK"
            )
            subprocess_config["model_id"] = judge_identifier
            subprocess_config["agent_endpoint"] = judge_config_item.get("endpoint")
            subprocess_config["agent_metadata"] = dict(
                judge_config_item.get("agent_metadata", {}) or {}
            )

            # Inject API key into metadata
            api_key = judge_config_item.get("api_key") or judge_config_item.get(
                "api_key_env"
            )
            if api_key:
                subprocess_config["agent_metadata"]["api_key"] = api_key

            judges_to_run.append((judge_type_str, subprocess_config))

        return judges_to_run

    # ====================================================================
    # SINGLE EVALUATOR EXECUTION
    # ====================================================================

    def _run_single_evaluator(
        self,
        judge_type: str,
        config: Dict[str, Any],
        data: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Instantiate one judge evaluator, run ``evaluate()``, return filtered rows."""
        evaluator_class = EVALUATOR_MAP.get(judge_type)
        if not evaluator_class:
            self.logger.warning(f"Unknown judge type: {judge_type}")
            return None

        evaluator = None
        try:
            # Filter config to EvaluatorConfig fields only
            expected_fields = {f.name for f in fields(EvaluatorConfig)}
            filtered_config = {k: v for k, v in config.items() if k in expected_fields}

            # Resolve agent_type
            if "agent_type" in filtered_config:
                filtered_config["agent_type"] = self.resolve_agent_type(
                    filtered_config["agent_type"]
                )

            evaluator_config = EvaluatorConfig(**filtered_config)
            evaluator = evaluator_class(
                client=self.client,
                config=evaluator_config,
                run_id=self._run_id,
                tracking_client=self._tracking_client,
                tracker=self._tracker,
            )
            evaluated_data = evaluator.evaluate(data)

            # Validate and filter to merge keys + judge columns
            eval_cols = self.JUDGE_COLUMN_MAP.get(judge_type, [])
            if not evaluated_data:
                return None
            if not all(key in evaluated_data[0] for key in self.MERGE_KEYS):
                self.logger.error(
                    f"Evaluation result missing merge keys for {judge_type}"
                )
                return None

            cols_to_return = set(self.MERGE_KEYS + list(eval_cols))
            return [
                {k: v for k, v in row.items() if k in cols_to_return}
                for row in evaluated_data
            ]

        except Exception as e:
            self.logger.error(
                f"Error running {judge_type} evaluator: {e}", exc_info=True
            )
            return None
        finally:
            del evaluator

    # ====================================================================
    # RESULT MERGING
    # ====================================================================

    @staticmethod
    def _normalize_merge_key(key_name: str, value: Any) -> str:
        """Normalize merge-key values (the evaluator converts None → "")."""
        if key_name in ("goal", "prefix", "completion"):
            return str(value) if value is not None else ""
        return value

    def _merge_evaluation_results(
        self,
        original_data: List[Dict[str, Any]],
        judge_results: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Merge per-judge evaluation columns into *original_data* via lookup."""
        for judge_type, judge_data in judge_results.items():
            eval_cols = self.JUDGE_COLUMN_MAP.get(judge_type, [])
            if not judge_data:
                continue

            lookup: Dict[tuple, Dict[str, Any]] = {}
            for row in judge_data:
                key = tuple(
                    self._normalize_merge_key(k, row.get(k)) for k in self.MERGE_KEYS
                )
                lookup[key] = {col: row.get(col) for col in eval_cols if col in row}

            for row in original_data:
                key = tuple(
                    self._normalize_merge_key(k, row.get(k)) for k in self.MERGE_KEYS
                )
                if key in lookup:
                    row.update(lookup[key])

        return original_data

    # ====================================================================
    # SCORING HELPERS
    # ====================================================================

    def compute_best_score(self, item: Dict[str, Any]) -> float:
        """Return the best (max) binary score across all judge columns."""
        score = 0.0
        for _judge_type, cols in self.JUDGE_COLUMN_MAP.items():
            eval_col = cols[0]
            val = item.get(eval_col)
            if val is not None:
                try:
                    score = max(score, float(val))
                except (TypeError, ValueError):
                    pass
        return score

    def _enrich_items_with_scores(
        self, data: List[Dict[str, Any]], error_indices: Optional[set] = None
    ) -> None:
        """
        Add ``best_score`` and ``success`` to every item in *data*.

        Items whose index is in *error_indices* get ``best_score=0, success=False``.
        """
        for idx, item in enumerate(data):
            if error_indices and idx in error_indices:
                item.setdefault("best_score", 0.0)
                item.setdefault("success", False)
                continue
            item["best_score"] = self.compute_best_score(item)
            item["success"] = item["best_score"] > 0

    # ====================================================================
    # SERVER SYNC
    # ====================================================================

    def _sync_to_server(
        self,
        evaluated_data: List[Dict[str, Any]],
        judge_keys: Optional[List[Dict[str, str]]] = None,
    ) -> int:
        """Sync evaluation results to the server (best per ``result_id``)."""
        return sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            client=self._tracking_client,
            logger=self.logger,
            judge_keys=judge_keys,
        )

    def _build_judge_keys_from_data(
        self, data: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Auto-detect which judge columns are present in *data* and return
        the ``judge_keys`` list expected by ``sync_evaluation_to_server``.
        """
        judge_keys: List[Dict[str, str]] = []
        for judge_type, cols in self.JUDGE_COLUMN_MAP.items():
            eval_col, expl_col = cols[0], cols[1]
            if any(x.get(eval_col) is not None for x in data):
                judge_keys.append(
                    {
                        "key": eval_col,
                        "explanation": expl_col,
                        "label": self.JUDGE_TYPE_LABELS.get(judge_type, judge_type),
                    }
                )
        return judge_keys

    # ====================================================================
    # ASR LOGGING
    # ====================================================================

    def _log_evaluation_asr(
        self, data: List[Dict[str, Any]], judges_used: Optional[List[str]] = None
    ) -> None:
        """Log Attack Success Rate per judge and overall."""
        total = len(data)
        if total == 0:
            return

        if judges_used is None:
            judges_used = list(self._statistics.get("successful_judges", []))

        for judge_type in judges_used:
            cols = self.JUDGE_COLUMN_MAP.get(judge_type)
            if not cols:
                continue
            eval_col = cols[0]
            successes = sum(1 for x in data if x.get(eval_col) == 1)
            label = self.JUDGE_TYPE_LABELS.get(judge_type, judge_type)
            self.logger.info(
                f"ASR-{label}: {successes}/{total} ({successes / total * 100:.1f}%)"
            )

        overall = sum(1 for x in data if x.get("best_score", 0) > 0)
        self.logger.info(
            f"ASR-Overall: {overall}/{total} ({overall / total * 100:.1f}%)"
        )

    # ====================================================================
    # TRACKER INTEGRATION
    # ====================================================================

    def _update_tracker(
        self,
        data: List[Dict[str, Any]],
        judges_used: Optional[List[str]] = None,
        evaluator_prefix: str = "eval",
    ) -> None:
        """
        Add evaluation traces to the goal-level ``Tracker`` for each item.

        Args:
            data: Evaluated items (must have ``best_score``, ``success``).
            judges_used: Which judge types were run (for trace naming).
            evaluator_prefix: Prefix string for evaluator_name.
        """
        if not self._tracker:
            return

        if judges_used is None:
            judges_used = list(self._statistics.get("successful_judges", []))

        for idx, item in enumerate(data):
            goal_ctx = self._tracker.get_goal_context(idx)
            if not goal_ctx:
                continue

            eval_result: Dict[str, Any] = {"success": item.get("success", False)}
            for judge_type in judges_used:
                cols = self.JUDGE_COLUMN_MAP.get(judge_type)
                if cols and cols[0] in item:
                    eval_result[cols[0]] = item[cols[0]]

            notes_parts = []
            for judge_type in judges_used:
                cols = self.JUDGE_COLUMN_MAP.get(judge_type)
                if not cols:
                    continue
                eval_col, expl_col = cols
                label = self.JUDGE_TYPE_LABELS.get(judge_type, judge_type)
                if eval_col in item:
                    notes_parts.append(f"{label}: {item[eval_col]}")
                if expl_col in item:
                    notes_parts.append(item[expl_col])

            explanation = " | ".join(notes_parts) if notes_parts else ""

            self._tracker.add_evaluation_trace(
                ctx=goal_ctx,
                evaluation_result=eval_result,
                score=item.get("best_score", 0.0),
                explanation=explanation,
                evaluator_name=f"{evaluator_prefix}_{'_'.join(judges_used)}",
            )

    # ====================================================================
    # STATISTICS
    # ====================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Return a copy of execution statistics."""
        return self._statistics.copy()
