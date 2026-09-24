# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Baseline attack implementation.

Sends goals directly to the target model without any transformation,
serving as a control condition for measuring default refusal rates.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Sequence, Union

from hackagent.attacks._lib.llm_router import LLMRouter
from hackagent.attacks._lib.objectives import OBJECTIVES
from hackagent.attacks.config import AttackConfig
from hackagent.attacks.ports import RunContext
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.types import AttackResult, rows_to_attack_results
from hackagent.core.contracts import Goal
from hackagent.attacks._lib.legacy_seams import Store

from . import generation
from .config import DEFAULT_BASELINE_CONFIG


class BaselineAttack(BaseAttack):
    """Baseline attack that sends goals directly to the target.

    Construct with ``(config, ctx)``. ``config`` is an
    :class:`~hackagent.attacks.config.AttackConfig` or a dict merged into
    :data:`~hackagent.attacks.techniques.static.baseline.config.DEFAULT_BASELINE_CONFIG`.
    ``ctx`` is a :class:`~hackagent.attacks.ports.RunContext`, passed
    positionally or as ``ctx=``. Tests build it with ``make_ctx()``
    (``tests.fakes.context``).

    The pipeline is generation-only. ``run()`` returns rows without a
    verdict; ``HackAgent.hack`` scores them in the shared evaluator.

    The legacy constructor ``(config_dict, client, agent_router)`` is
    obsolete for new code. ``hackagent.orchestrator.execution.runner`` constructs
    ``(config, ctx)``.
    """

    def __init__(
        self,
        config: Optional[Union[AttackConfig, Dict[str, Any]]] = None,
        ctx_or_client: Any = None,
        agent_router: Optional[LLMRouter] = None,
        *,
        ctx: Optional[RunContext] = None,
        client: Optional[Store] = None,
    ):
        if ctx is None and isinstance(ctx_or_client, RunContext):
            ctx = ctx_or_client

        current_config = copy.deepcopy(DEFAULT_BASELINE_CONFIG)
        if isinstance(config, AttackConfig):
            current_config.update(config.model_dump())
        elif config:
            current_config.update(config)

        self.logger = logging.getLogger("hackagent.attacks.baseline")

        if ctx is not None:
            super().__init__(current_config, ctx)
            return

        resolved_client = client if client is not None else ctx_or_client
        if resolved_client is None:
            raise ValueError("A storage backend must be provided")
        if agent_router is None:
            raise ValueError("LLMRouter must be provided")

        super().__init__(current_config, resolved_client, agent_router)

    def _validate_config(self):
        super()._validate_config()

        if self.ctx is not None and self.attack_config is not None:
            objective = self.config.get("objective")
            if objective and objective not in OBJECTIVES:
                raise ValueError(
                    f"Unknown objective: {objective}. Available: {list(OBJECTIVES.keys())}"
                )
            return

        required_keys = ["output_dir", "objective"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")

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
        # Post-hoc: generation only; orchestrator / Panel judges later.
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

    def run(
        self,
        goals: Optional[Sequence[Union[Goal, str]]] = None,
        **kwargs: Any,
    ) -> List[AttackResult]:
        goal_texts = self._goal_texts(goals)
        if not goal_texts:
            return []

        coordinator = self._initialize_coordinator(
            attack_type="Baseline",
            goals=goal_texts,
            initial_metadata={"objective": self.config.get("objective")},
        )

        self.config["_tracker"] = coordinator.goal_tracker

        try:
            results = self._execute_pipeline(self._get_pipeline_steps(), goal_texts)

            def success_check(output):
                return output and isinstance(output, (dict, list))

            coordinator.finalize_pipeline(results, success_check)
            return rows_to_attack_results(results if results else [])

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            coordinator.finalize_on_error("Baseline pipeline failed with exception")
            raise
