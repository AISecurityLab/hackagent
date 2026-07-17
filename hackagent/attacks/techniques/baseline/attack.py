# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Baseline attack implementation.

Sends goals directly to the target model without any transformation,
serving as a control condition for measuring default refusal rates.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.server.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation
from .config import DEFAULT_BASELINE_CONFIG

# Reuse evaluation from static_template (same interface)
from hackagent.attacks.techniques.static_template import static_eval as evaluation


class BaselineAttack(BaseAttack):
    """
    Baseline attack that sends goals directly to the target.

    No prompt transformation is applied — goals are sent as-is.
    This provides a control condition to compare against actual
    attack techniques (PAIR, TAP, DrAttack, etc.).

    Pipeline stages
    ---------------
    1. **Generation** — sends each goal verbatim to the target model.
    2. **Evaluation** — scores responses using the configured evaluator.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        if client is None:
            raise ValueError("AuthenticatedClient must be provided")
        if agent_router is None:
            raise ValueError("AgentRouter must be provided")

        current_config = copy.deepcopy(DEFAULT_BASELINE_CONFIG)
        if config:
            current_config.update(config)

        self.logger = logging.getLogger("hackagent.attacks.baseline")

        super().__init__(current_config, client, agent_router)

    def _validate_config(self):
        super()._validate_config()

        required_keys = ["output_dir", "objective"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")

        from hackagent.attacks.objectives import OBJECTIVES

        objective = self.config.get("objective")
        if objective not in OBJECTIVES:
            raise ValueError(
                f"Unknown objective: {objective}. Available: {list(OBJECTIVES.keys())}"
            )

    @classmethod
    def get_effective_model_roles(
        cls,
        attack_config: Dict[str, Any],
        *,
        goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Baseline always needs judge models for LLM-judge evaluation."""
        _ = goal_labels_by_index

        judges = attack_config.get("judges")
        if isinstance(judges, list) and judges:
            return [{"role": "judge", "config": judge} for judge in judges]

        judge = attack_config.get("judge")
        if isinstance(judge, dict):
            return [{"role": "judge", "config": judge}]

        judge_config = attack_config.get("judge_config")
        if isinstance(judge_config, dict):
            return [{"role": "judge", "config": judge_config}]

        return []

    def _get_pipeline_steps(self) -> List[Dict]:
        return [
            {
                "name": "Generation: Send Goals Directly to Target",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "max_tokens",
                    "temperature",
                    "batch_size",
                    "_goal_index_offset",
                    "_tracker",
                    "_run_id",
                    "_backend",
                    "_client",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Evaluate Responses",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "objective",
                    "judges",
                    "judge",
                    "judge_config",
                    "min_response_length",
                    "batch_size_judge",
                    "judge_parallelism",
                    "max_tokens_eval",
                    "judge_timeout",
                    "judge_request_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                    "organization_id",
                    "_goal_index_offset",
                    "_tracker",
                    "_run_id",
                    "_backend",
                    "_client",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "client"],
            },
        ]

    def _build_step_args(
        self,
        step_info: Dict,
        step_config: Dict,
        input_data: Any,
    ) -> Dict:
        """Inject shared goal tracker into stage functions."""
        args = super()._build_step_args(step_info, step_config, input_data)
        if self.coordinator and self.coordinator.goal_tracker:
            args["goal_tracker"] = self.coordinator.goal_tracker
            args["config"]["_tracker"] = self.coordinator.goal_tracker
        return args

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> Dict[str, Any]:
        """
        Execute baseline attack (direct goal submission).

        Args:
            goals: List of goal strings to send directly.

        Returns:
            Dictionary with 'evaluated' and 'summary' DataFrames.
        """
        if not goals:
            return {"evaluated": [], "summary": []}

        coordinator = self._initialize_coordinator(
            attack_type="Baseline",
            goals=goals,
            initial_metadata={"objective": self.config.get("objective")},
        )

        self.config["_tracker"] = coordinator.goal_tracker

        try:
            results = self._execute_pipeline(self._get_pipeline_steps(), goals)

            def success_check(output):
                return output and isinstance(output, dict)

            coordinator.finalize_pipeline(results, success_check)
            return results if results else {"evaluated": [], "summary": []}

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            coordinator.finalize_on_error("Baseline pipeline failed with exception")
            raise
