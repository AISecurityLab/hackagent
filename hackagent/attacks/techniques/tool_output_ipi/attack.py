# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Tool-output indirect prompt injection (tool_output_ipi) attack.

Poisons tool / function-call *observations* so a tool-using agent may follow
a malicious goal after a benign user task (InjecAgent / OPI family).

This is distinct from ``rag``, which poisons
RAG documents — not tool return values.

Pipeline:
1. Generation — craft poisoned tool observations, query target, inline judge
2. Evaluation — post-processing (server sync, tracker, ASR)

Taxonomy: primary **adaptive**, tag **indirect** (registered defensively when ``hackagent.catalog.taxonomy`` is present; add a permanent ``ATTACK_TAXONOMY`` entry when #603 merges).
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.storage.store import Store
from hackagent.attacks._lib.llm_router import LLMRouter
from hackagent.attacks._lib.inline_judge import (
    attach_ctx_judge,
    make_postprocess_execute,
)
from hackagent.attacks.ports import RunContext
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.types import AttackResult, rows_to_attack_results

from . import generation
from .config import DEFAULT_TOOL_OUTPUT_IPI_CONFIG
from hackagent.attacks.techniques.tool_output_ipi.config import ToolOutputIPIConfig


def _recursive_update(target_dict: Dict[str, Any], source_dict: Dict[str, Any]) -> None:
    """Recursively merge *source_dict* into *target_dict*."""
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


class ToolOutputIPIAttack(BaseAttack):
    """Tool-output indirect prompt injection (InjecAgent / OPI).

    For each malicious goal the attack:
    1. Starts from a benign user message that would elicit a tool call.
    2. Appends a simulated (or live) ``role=tool`` observation containing an
       adversarial injection aimed at the goal.
    3. Re-queries the target with the full messages history.
    4. Judges whether the response or subsequent tool call follows the
       injected instructions (direct harm and/or data stealing).

    Construct with ``(config, ctx)``. Scoring uses ``ctx.judge.score``
    through :class:`~hackagent.attacks._lib.inline_judge.CtxJudgeAdapter`.
    ``InlineStepJudge`` remains the fallback when ``ctx`` is absent.
    Tests build ``ctx`` with ``make_ctx()``. The legacy constructor is
    obsolete for new code. ``ToolOutputIPIConfig`` still subclasses
    :class:`~hackagent.attacks.techniques.config.ConfigBase`.
    """

    config_model = ToolOutputIPIConfig

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        ctx_or_client: Any = None,
        agent_router: Optional[LLMRouter] = None,
        *,
        ctx: Optional[RunContext] = None,
        client: Optional[Store] = None,
    ):
        if ctx is None and isinstance(ctx_or_client, RunContext):
            ctx = ctx_or_client
        resolved_client = (
            client
            if client is not None
            else (None if isinstance(ctx_or_client, RunContext) else ctx_or_client)
        )
        if ctx is None:
            if resolved_client is None:
                raise ValueError(
                    "A storage backend must be provided to ToolOutputIPIAttack."
                )
            if agent_router is None:
                raise ValueError(
                    "Victim LLMRouter instance must be provided to ToolOutputIPIAttack."
                )
            client = resolved_client

        current_config = copy.deepcopy(DEFAULT_TOOL_OUTPUT_IPI_CONFIG)
        if config:
            _recursive_update(current_config, config)

        attach_ctx_judge(current_config, ctx)

        self.logger = logging.getLogger("hackagent.attacks.tool_output_ipi")
        if ctx is not None:
            super().__init__(current_config, ctx)
        else:
            super().__init__(current_config, client, agent_router)

    def _validate_config(self) -> None:
        super()._validate_config()

        required_keys = ["attack_type", "tool_output_ipi_params"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        params = self.config.get("tool_output_ipi_params", {})
        if not isinstance(params, dict):
            raise ValueError("tool_output_ipi_params must be a dictionary")

        mode = params.get("mode", "simulated")
        if mode not in ("simulated", "live"):
            raise ValueError(
                f"tool_output_ipi_params.mode must be 'simulated' or 'live'; got {mode!r}"
            )

        max_attempts = params.get("max_attempts", 3)
        try:
            if int(max_attempts) < 1:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "tool_output_ipi_params.max_attempts must be an integer >= 1"
            ) from exc

        if params.get("use_attacker_llm") and not (
            isinstance(self.config.get("attacker"), dict)
            and self.config["attacker"].get("identifier")
        ):
            raise ValueError(
                "use_attacker_llm=True requires attacker.identifier in the attack config"
            )

    def _get_pipeline_steps(self) -> List[Dict]:
        return [
            {
                "name": "Generation: Tool-output IPI + Judge",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "tool_output_ipi_params",
                    "attacker",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                    "_goal_index_offset",
                    "judges",
                    "_judge",
                    "judge_concurrency",
                    "max_tokens_eval",
                    "filter_len",
                    "judge_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                    "max_tokens",
                    "temperature",
                    "timeout",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation Post-processing: Server Sync, Tracker & ASR Logging",
                "function": make_postprocess_execute("tool_output_ipi"),
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "tool_output_ipi_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                    "_goal_index_offset",
                    "judges",
                    "_judge",
                    "judge_concurrency",
                    "max_tokens_eval",
                    "filter_len",
                    "judge_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "client"],
            },
        ]

    def run(self, goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]:
        """Execute the tool-output IPI pipeline.

        Args:
            goals: Malicious goals the poisoned tool observation should induce.

        Returns:
            List of :class:`~hackagent.attacks.types.AttackResult` rows.
        """
        goals = goals or []
        if not goals:
            return []

        coordinator = self._initialize_coordinator(attack_type="tool_output_ipi")

        params = self.config.get("tool_output_ipi_params", {})
        goal_metadata = {
            "mode": params.get("mode", "simulated"),
            "max_attempts": params.get("max_attempts", 3),
            "success_setting": params.get("success_setting", "both"),
            "tool_name": params.get("tool_name"),
            # Documented taxonomy until hackagent.catalog.taxonomy lands (#603).
            "category": "adaptive",
            "tags": ["indirect"],
        }
        coordinator.initialize_goals(goals=goals, initial_metadata=goal_metadata)

        if coordinator.has_goal_tracking:
            self.logger.info("Using TrackingCoordinator for per-goal tracking")

        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        try:
            generation_output = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step, end_step=start_step + 1
            )

            if not generation_output:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            results = self._execute_pipeline(
                pipeline_steps, generation_output, start_step=start_step + 1
            )

            coordinator.finalize_all_goals(
                results,
                include_evaluation_trace=False,
            )
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return rows_to_attack_results(results)

        except Exception:
            self.logger.exception("tool_output_ipi pipeline failed with exception")
            coordinator.finalize_on_error(
                "tool_output_ipi pipeline failed with exception"
            )
            raise
