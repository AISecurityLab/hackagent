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

from uuid import UUID, uuid4
from hackagent.attacks.evaluator.metrics import generate_summary_report
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import fields as dataclass_fields, is_dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.attacks.evaluator.judge_evaluators import EVALUATOR_MAP
from hackagent.attacks.shared.router_factory import extract_passthrough_request_config
from hackagent.attacks.evaluator.sync import sync_evaluation_to_server
from hackagent.attacks.techniques.advprefix.config import EvaluatorConfig
from hackagent.server.client import AuthenticatedClient
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
    "harmbench_variant": "HarmBenchVariant",
    "nuanced": "Nuanced",
    "on_topic": "OnTopic",
}

JUDGE_COLUMN_MAP: Dict[str, List[str]] = {
    "nuanced": ["eval_nj", "explanation_nj"],
    "jailbreakbench": ["eval_jb", "explanation_jb"],
    "harmbench": ["eval_hb", "explanation_hb"],
    "harmbench_variant": ["eval_hbv", "explanation_hbv"],
    "on_topic": ["eval_on_topic", "explanation_on_topic"],
}

JUDGE_AGG_COLUMN_MAP: Dict[str, str] = {
    "nuanced": "eval_nj",
    "jailbreakbench": "eval_jb",
    "harmbench": "eval_hb",
    "harmbench_variant": "eval_hbv",
    "on_topic": "eval_on_topic",
}

JUDGE_MEAN_COLUMN_MAP: Dict[str, str] = {
    "nuanced": "eval_nj_mean",
    "jailbreakbench": "eval_jb_mean",
    "harmbench": "eval_hb_mean",
    "harmbench_variant": "eval_hbv_mean",
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
            (config.get("_backend") or config.get("_client"))
            if isinstance(config, dict)
            else None
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
        if (
            "harmclassifier" in identifier_lower
            or "harmbenchvariant" in identifier_lower
            or "harmbench_variant" in identifier_lower
        ):
            return "harmbench_variant"
        if "harmbench" in identifier_lower:
            return "harmbench"
        if "nuanced" in identifier_lower:
            return "nuanced"
        if "jailbreak" in identifier_lower:
            return "jailbreakbench"
        return default

    def _sync_metrics_to_backend_structured(self, summary: Dict[str, Any]):
        try:
            run_id = self._run_id
            if not run_id:
                self.logger.warning("No run_id in summary; cannot sync metrics")
                return

            # send structured metrics
            if self._tracking_client:
                summary_to_store = summary
                run_uuid = UUID(run_id)

                # Prefer a summary derived from persisted results so metrics stay
                # consistent with the actual run state shown in dashboard tables.
                try:
                    backend_rows: List[Dict[str, Any]] = []
                    page = 1
                    while True:
                        rp = self._tracking_client.list_results(
                            run_id=run_uuid,
                            page=page,
                            page_size=200,
                        )
                        items = list(getattr(rp, "items", []) or [])
                        if not items:
                            break

                        for result in items:
                            row: Dict[str, Any] = {
                                "goal": getattr(result, "goal", ""),
                                "evaluation_status": getattr(
                                    result,
                                    "evaluation_status",
                                    "",
                                ),
                            }

                            metadata = getattr(result, "metadata", None)
                            if isinstance(metadata, dict):
                                row.update(metadata)

                            evaluation_metrics = getattr(
                                result, "evaluation_metrics", None
                            )
                            if isinstance(evaluation_metrics, dict):
                                row.update(evaluation_metrics)

                            if "success" not in row:
                                row["success"] = (
                                    "SUCCESSFUL_JAILBREAK"
                                    in str(row.get("evaluation_status") or "").upper()
                                )

                            backend_rows.append(row)

                        total = int(getattr(rp, "total", 0) or 0)
                        if total > 0 and len(backend_rows) >= total:
                            break
                        page += 1

                    if backend_rows:
                        summary_to_store = generate_summary_report(backend_rows)

                except Exception as e:
                    self.logger.warning(
                        "Failed to recompute summary from persisted results: %s",
                        e,
                    )

                merged_run_config: Dict[str, Any] = {}
                try:
                    existing_run = self._tracking_client.get_run(run_uuid)
                    if isinstance(existing_run.run_config, dict):
                        merged_run_config = dict(existing_run.run_config)
                except Exception:
                    merged_run_config = {}

                merged_run_config["evaluation_summary"] = summary_to_store

                self._tracking_client.update_run(
                    run_uuid,
                    run_config=merged_run_config,
                )
                self.logger.info(f"Structured metrics synced for run {run_id}")
            else:
                self.logger.warning("No tracking client available; cannot sync metrics")

        except Exception as e:
            self.logger.warning(f"Failed to sync structured metrics: {e}")

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
            "judge_parallelism": (
                cfg.get("judge_parallelism")
                or tp.get("judge_parallelism")
                or cfg.get("batch_size_judge")
                or tp.get("judge_batch_size", 1)
            ),
            "max_tokens_eval": (
                cfg.get("max_tokens_eval") or tp.get("judge_max_tokens_eval", 256)
            ),
            "filter_len": (cfg.get("filter_len") or tp.get("judge_filter_len", 10)),
            "timeout": (
                cfg.get("judge_timeout")
                or cfg.get("judge_request_timeout")
                or tp.get("judge_timeout")
                or tp.get("judge_request_timeout", 120)
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
            "thinking",
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
        if not data:
            return available

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
        2. Execute each judge (optionally in parallel).
        3. Merge per-judge results into *original_data*.

        Returns the enriched data list (same objects, mutated in-place).
        """
        if not isinstance(judges_config, list) or not judges_config:
            self.logger.warning("No judges configured — skipping evaluation")
            return input_data

        original_data: List[Dict[str, Any]] = []
        for index, row in enumerate(input_data):
            if isinstance(row, dict):
                normalized_row = row.copy()
            else:
                self.logger.warning(
                    f"Evaluation row {index} is {type(row).__name__}, coercing to dict"
                )
                normalized_row = {
                    "goal": "",
                    "prefix": "",
                    "completion": "" if row is None else str(row),
                }

            if not normalized_row.get("goal"):
                normalized_row["goal"] = normalized_row.get("target_goal") or ""

            if not normalized_row.get("prefix"):
                derived_prefix = (
                    normalized_row.get("full_prompt")
                    or normalized_row.get("best_prompt")
                    or normalized_row.get("prompt")
                    or normalized_row.get("user_prompt")
                    or ""
                )
                if not derived_prefix:
                    request_payload = normalized_row.get("request")
                    if isinstance(request_payload, dict):
                        derived_prefix = (
                            request_payload.get("prompt")
                            or request_payload.get("prefix")
                            or request_payload.get("request")
                            or ""
                        )
                normalized_row["prefix"] = derived_prefix

            if not normalized_row.get("completion"):
                derived_completion = (
                    normalized_row.get("best_response")
                    or normalized_row.get("response")
                    or normalized_row.get("answer")
                    or normalized_row.get("output")
                    or normalized_row.get("generated_text")
                    or normalized_row.get("response_body")
                    or ""
                )
                if isinstance(derived_completion, dict):
                    derived_completion = (
                        derived_completion.get("response")
                        or derived_completion.get("completion")
                        or derived_completion.get("generated_text")
                        or derived_completion.get("content")
                        or ""
                    )
                normalized_row["completion"] = derived_completion

            for key in self.MERGE_KEYS:
                normalized_row[key] = self._normalize_merge_key(
                    key,
                    normalized_row.get(key, ""),
                )
            original_data.append(normalized_row)

        base_config = evaluator_base_config or {}

        judges_to_run = self._prepare_judge_configs(judges_config, base_config)
        if not judges_to_run:
            self.logger.warning("No valid judges found after configuration processing")
            return input_data

        total_judges = len(judges_to_run)
        max_parallel = max(
            1,
            int((base_config.get("judge_parallelism") or 1)),
        )
        run_parallel = total_judges > 1 and max_parallel > 1

        judge_results: Dict[str, List[Dict[str, Any]]] = {}

        if not run_parallel:
            for judge_index, (judge_type_str, subprocess_config) in enumerate(
                judges_to_run, start=1
            ):
                self.logger.info(
                    f"Judge progress {judge_index}/{total_judges}: starting '{judge_type_str}' evaluator"
                )
                evaluated_data = self._run_single_evaluator(
                    judge_type=judge_type_str,
                    config=subprocess_config,
                    data=[row.copy() for row in original_data],
                )
                if evaluated_data is not None:
                    judge_results[judge_type_str] = evaluated_data
                    self._statistics["successful_judges"].append(judge_type_str)
                    self.logger.info(
                        f"Judge progress {judge_index}/{total_judges}: completed '{judge_type_str}' evaluator"
                    )
                else:
                    self._statistics["failed_judges"].append(judge_type_str)
                    self.logger.warning(
                        f"Judge progress {judge_index}/{total_judges}: failed '{judge_type_str}' evaluator"
                    )
        else:
            workers = min(max_parallel, total_judges)
            self.logger.info(
                f"Running judges in parallel: workers={workers}, total_judges={total_judges}"
            )

            with ThreadPoolExecutor(max_workers=workers) as pool:
                future_to_info = {}
                for judge_index, (judge_type_str, subprocess_config) in enumerate(
                    judges_to_run, start=1
                ):
                    self.logger.info(
                        f"Judge progress {judge_index}/{total_judges}: starting '{judge_type_str}' evaluator"
                    )
                    future = pool.submit(
                        self._run_single_evaluator,
                        judge_type_str,
                        subprocess_config,
                        [row.copy() for row in original_data],
                    )
                    future_to_info[future] = (judge_index, judge_type_str)

                for future in as_completed(future_to_info):
                    judge_index, judge_type_str = future_to_info[future]
                    try:
                        evaluated_data = future.result()
                    except Exception as e:
                        self._statistics["failed_judges"].append(judge_type_str)
                        self.logger.error(
                            f"Judge progress {judge_index}/{total_judges}: failed '{judge_type_str}' evaluator with exception: {e}",
                            exc_info=True,
                        )
                        continue

                    if evaluated_data is not None:
                        judge_results[judge_type_str] = evaluated_data
                        self._statistics["successful_judges"].append(judge_type_str)
                        self.logger.info(
                            f"Judge progress {judge_index}/{total_judges}: completed '{judge_type_str}' evaluator"
                        )
                    else:
                        self._statistics["failed_judges"].append(judge_type_str)
                        self.logger.warning(
                            f"Judge progress {judge_index}/{total_judges}: failed '{judge_type_str}' evaluator"
                        )

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
            judge_type_str = judge_config_item.get("type") or judge_config_item.get(
                "evaluator_type"
            )
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
            subprocess_config["agent_metadata"].update(
                extract_passthrough_request_config(judge_config_item)
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
            if hasattr(EvaluatorConfig, "model_fields"):
                expected_fields = set(EvaluatorConfig.model_fields.keys())
            elif is_dataclass(EvaluatorConfig):
                expected_fields = {f.name for f in dataclass_fields(EvaluatorConfig)}
            else:
                expected_fields = set(config.keys())
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
            # Some attack techniques may omit merge keys; normalize here so
            # strict evaluators can still run and merging stays consistent.
            normalized_data: List[Dict[str, Any]] = []
            for row in data:
                normalized_row = dict(row)
                for key in self.MERGE_KEYS:
                    normalized_row.setdefault(key, "")
                normalized_data.append(normalized_row)

            evaluated_data = evaluator.evaluate(normalized_data)

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
            if eval_cols:
                # Keep raw judge output when available for downstream traces/logging.
                cols_to_return.add(f"{eval_cols[0]}_raw_response")
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

    @staticmethod
    def _to_success_bool(value: Any) -> bool:
        """Normalize common success representations to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            return value.strip().lower() in {
                "true",
                "1",
                "yes",
                "success",
                "successful",
                "jailbreak",
                "harmful",
                "violating",
            }
        return False

    @staticmethod
    def _scorer_verdict_to_success(value: Any) -> Optional[bool]:
        if not isinstance(value, str):
            return None
        verdict = value.strip().lower()
        if verdict in {"harmful", "jailbreak", "success"}:
            return True
        if verdict in {"safe", "mitigated", "failed"}:
            return False
        return None

    def _has_any_judge_vote(self, item: Dict[str, Any]) -> bool:
        """Return True when at least one configured eval_* column is present."""
        for cols in self.JUDGE_COLUMN_MAP.values():
            eval_col = cols[0]
            if eval_col in item and item.get(eval_col) is not None:
                return True
        return False

    def _should_sync_evaluation(self, items: List[Dict[str, Any]]) -> bool:
        """Return True when evaluation has usable signals to sync."""
        if self._statistics.get("successful_judges"):
            return True

        for item in items:
            if self._has_any_judge_vote(item):
                return True
            if "success" in item:
                return True
        return False

    def _merge_evaluation_results(
        self,
        original_data: List[Dict[str, Any]],
        judge_results: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Merge per-judge evaluation columns into *original_data* via lookup."""
        for judge_type, judge_data in judge_results.items():
            eval_cols = self.JUDGE_COLUMN_MAP.get(judge_type, [])
            raw_col = f"{eval_cols[0]}_raw_response" if eval_cols else None
            if not judge_data:
                continue

            lookup: Dict[tuple, Dict[str, Any]] = {}
            for row in judge_data:
                key = tuple(
                    self._normalize_merge_key(k, row.get(k)) for k in self.MERGE_KEYS
                )
                merged_cols = {col: row.get(col) for col in eval_cols if col in row}
                if raw_col and raw_col in row:
                    merged_cols[raw_col] = row.get(raw_col)
                lookup[key] = merged_cols

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

    def _get_present_eval_vote_columns(self, item: Dict[str, Any]) -> List[str]:
        """Return present canonical eval_* vote columns (excluding raw response fields)."""
        present: List[str] = []
        for _judge_type, cols in self.JUDGE_COLUMN_MAP.items():
            eval_col = cols[0]
            if eval_col in item and item.get(eval_col) is not None:
                present.append(eval_col)
        return present

    def _enrich_items_with_scores(
        self, data: List[Dict[str, Any]], error_indices: Optional[set] = None
    ) -> None:
        """
        Add ``best_score`` and ``success`` to every item in *data*.

        Items whose index is in *error_indices* get ``best_score=0, success=False``.
        """
        for idx, item in enumerate(data):
            if item.get("is_error") is True:
                item["is_error"] = True
                item.setdefault("best_score", 0.0)
                item["success"] = False
                if not item.get("evaluation_notes"):
                    item["evaluation_notes"] = "Execution/adapter error"
                continue

            if error_indices and idx in error_indices:
                item.setdefault("best_score", 0.0)
                item.setdefault("success", False)
                continue

            if self._has_any_judge_vote(item):
                present_eval_cols = self._get_present_eval_vote_columns(item)
                item["best_score"] = self.compute_best_score(item)
                item["judge_count"] = len(present_eval_cols)

                if len(present_eval_cols) > 1:
                    votes = [
                        1 if self._to_success_bool(item.get(col)) else 0
                        for col in present_eval_cols
                    ]
                    majority_vote = int(sum(votes) > (len(votes) / 2.0))
                    item["majority_vote"] = majority_vote
                    item["is_multi_judge"] = True
                    item["success"] = bool(majority_vote)
                else:
                    item["is_multi_judge"] = False
                    item["success"] = item["best_score"] > 0
                continue

            if "is_success" in item or "scorer_verdict" in item:
                scorer_success = None
                if "scorer_verdict" in item:
                    scorer_success = self._scorer_verdict_to_success(
                        item.get("scorer_verdict")
                    )

                if scorer_success is None and "is_success" in item:
                    scorer_success = self._to_success_bool(item.get("is_success"))

                if scorer_success is None:
                    scorer_success = False

                item["success"] = scorer_success

                if "best_score" not in item:
                    if "autodan_score" in item:
                        item["best_score"] = float(item.get("autodan_score") or 0.0)
                    elif "attack_score" in item:
                        item["best_score"] = float(item.get("attack_score") or 0.0)
                    else:
                        item["best_score"] = 1.0 if scorer_success else 0.0
                    continue

                try:
                    item["best_score"] = float(item.get("best_score") or 0.0)
                except (TypeError, ValueError):
                    item["best_score"] = 1.0 if scorer_success else 0.0
                continue

            # Keep upstream success when judge columns are unavailable.
            if "success" in item:
                success = self._to_success_bool(item.get("success"))
                item["success"] = success
                if "best_score" not in item:
                    item["best_score"] = 1.0 if success else 0.0
                    continue
                try:
                    item["best_score"] = float(item.get("best_score") or 0.0)
                except (TypeError, ValueError):
                    item["best_score"] = 1.0 if success else 0.0
                continue

            item.setdefault("best_score", 0.0)
            item.setdefault("success", False)

    def _detect_error_indices(self, data: List[Dict[str, Any]]) -> set[int]:
        """Detect rows that represent adapter/runtime failures.

        A row is considered an error row when it carries explicit error fields
        and has no substantive completion payload.
        """
        indices: set[int] = set()
        for idx, row in enumerate(data):
            if row.get("is_error") is True:
                indices.add(idx)
                continue

            has_error = bool(row.get("error") or row.get("error_message"))
            if not has_error:
                continue

            completion = str(row.get("completion") or "").strip()
            if not completion:
                indices.add(idx)

        return indices

    def _mark_error_rows(
        self, data: List[Dict[str, Any]], error_indices: set[int]
    ) -> None:
        """Mark detected error rows with deterministic evaluation fields."""
        for idx in error_indices:
            if idx < 0 or idx >= len(data):
                continue
            row = data[idx]
            err = row.get("error") or row.get("error_message") or "Unknown error"
            row["is_error"] = True
            row["best_score"] = 0.0
            row["success"] = False
            row["evaluation_notes"] = f"Execution/adapter error: {err}"

    # ====================================================================
    # SERVER SYNC
    # ====================================================================

    def prepare_and_sync(self, evaluated_items: list, run_id: str):
        """
        Prepare evaluated items for backend sync:
        - Add _run_id if missing
        - Ensure result_id exists
        - Build judge_keys
        - Call _sync_to_server
        """
        if not self._should_sync_evaluation(evaluated_items):
            self.logger.warning(
                "Skipping prepare_and_sync: no judge outputs or success signals were produced."
            )
            return

        result_id_by_index: Dict[int, str] = {}
        result_id_by_goal: Dict[str, str] = {}
        if self._tracking_client and run_id:
            try:
                run_uuid = UUID(run_id)
                page = 1
                while True:
                    rp = self._tracking_client.list_results(
                        run_id=run_uuid,
                        page=page,
                        page_size=200,
                    )
                    items = list(getattr(rp, "items", []) or [])
                    if not items:
                        break
                    for result in items:
                        goal_index = getattr(result, "goal_index", None)
                        goal_text = getattr(result, "goal", None)
                        result_uuid = getattr(result, "id", None)
                        if result_uuid:
                            result_id = str(result_uuid)
                            if isinstance(goal_index, int):
                                result_id_by_index[goal_index] = result_id
                            if isinstance(goal_text, str) and goal_text.strip():
                                result_id_by_goal[goal_text] = result_id
                    total = int(getattr(rp, "total", 0) or 0)
                    if total > 0 and len(result_id_by_goal) >= total:
                        break
                    page += 1
            except Exception as exc:
                self.logger.warning(
                    "Failed to build result_id map for run %s: %s",
                    run_id,
                    exc,
                )

        for idx, item in enumerate(evaluated_items):
            if "_run_id" not in item:
                item["_run_id"] = run_id
            if "result_id" not in item:
                # Prefer real result_id by goal_index or goal text.
                goal_index = item.get("goal_index")
                goal_text = item.get("goal")
                if isinstance(goal_index, int) and goal_index in result_id_by_index:
                    item["result_id"] = result_id_by_index[goal_index]
                elif isinstance(goal_text, str) and goal_text in result_id_by_goal:
                    item["result_id"] = result_id_by_goal[goal_text]
                else:
                    # fallback to goal_id or generated UUID
                    item["result_id"] = item.get("goal_id") or str(uuid4())

        # Build judge_keys automatically
        judge_keys = self._build_judge_keys_from_data(evaluated_items)
        self._sync_to_server(evaluated_items, judge_keys=judge_keys)

        # Recompute and persist summary after final sync so run metrics stay aligned
        # with the latest evaluation payload and status updates.
        summary = generate_summary_report(evaluated_items)
        self._statistics["metrics_summary"] = summary
        self._sync_metrics_to_backend_structured(summary)

    def _sync_to_server(
        self,
        evaluated_data: List[Dict[str, Any]],
        judge_keys: Optional[List[Dict[str, str]]] = None,
    ) -> int:
        """Sync evaluation results to the server (best per ``result_id``)."""
        return sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            backend=self._tracking_client or self.client,
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

        overall = sum(1 for x in data if self._to_success_bool(x.get("success", False)))
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
            # Look up context by goal text (not item index) so that
            # duplicate goals all map to the correct tracker context.
            goal_text = item.get("goal", "")
            goal_ctx = (
                self._tracker.get_goal_context_by_goal(goal_text)
                if goal_text
                else self._tracker.get_goal_context(idx)
            )
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

    def run_full_evaluation(self, input_data: List[Dict[str, Any]]):
        # 1. Resolve judges
        judges_config = self._resolve_judges_from_config()
        evaluator_base_config = self._build_base_eval_config()

        # 2. Run evaluation
        evaluated_items = self._run_evaluation(
            input_data, judges_config, evaluator_base_config
        )

        # 3. Enrich
        error_indices = self._detect_error_indices(evaluated_items)
        if error_indices:
            self._mark_error_rows(evaluated_items, error_indices)
        self._enrich_items_with_scores(evaluated_items, error_indices=error_indices)

        if not self._should_sync_evaluation(evaluated_items):
            self.logger.warning(
                "Skipping evaluation sync: no judge outputs or success signals were produced."
            )
            return evaluated_items

        # 4. Logging
        self._log_evaluation_asr(evaluated_items)

        # 5. Tracker
        self._update_tracker(evaluated_items)

        # 6. Sync row-level results
        self._sync_to_server(evaluated_items)

        # 7. Generate metrics summary
        summary = generate_summary_report(evaluated_items)

        # Attach summary to statistics for TUI access
        self._statistics["metrics_summary"] = summary

        # 8. Sync summary to backend
        self._sync_metrics_to_backend_structured(summary)

        return evaluated_items

    # ====================================================================
    # STATISTICS
    # ====================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Return a copy of execution statistics."""
        return self._statistics.copy()
