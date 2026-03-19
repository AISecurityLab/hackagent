# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
h4rm3l attack implementation.

Composable prompt-decoration attack that chains multiple text transformations
(encoding, obfuscation, roleplaying, persuasion) to bypass LLM safety filters.

Based on: Doumbouya et al., "h4rm3l: A Dynamic Benchmark of Composable
Jailbreak Attacks for LLM Safety Assessment" (2024)
https://arxiv.org/abs/2408.04811

The attack works by applying a user-defined "program" — a chain of
PromptDecorator transforms — to each goal prompt before sending it to
the target model.  Decorators range from simple text manipulations
(base64, character corruption) to LLM-assisted rewrites (translation,
persuasion, persona injection).
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.server.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation, evaluation
from .config import DEFAULT_H4RM3L_CONFIG, PRESET_PROGRAMS


def _recursive_update(target_dict, source_dict):
    """Recursively merge source into target, deep-copying non-internal values."""
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


class H4rm3lAttack(BaseAttack):
    """
    h4rm3l — composable prompt-decoration jailbreak attack.

    Applies a chain of PromptDecorator transforms to each goal prompt,
    sends the decorated prompt to the target model, and evaluates the
    response with multi-judge scoring.

    Pipeline:
        1. **Generation** — Compile the decorator program, apply to each
           goal in parallel, query the target model.
        2. **Evaluation** — Multi-judge scoring via BaseEvaluationStep.

    The decorator program is specified via ``h4rm3l_params.program``.
    It can be:
        - A preset name from :data:`PRESET_PROGRAMS` (e.g.
          ``"base64_refusal_suppression"``)
        - A raw program string in v1 or v2 syntax (e.g.
          ``"Base64Decorator().then(RefusalSuppressionDecorator())"``).

    Attributes:
        program: The resolved decorator program string.
        syntax_version: Program syntax version (1 or 2).
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        if client is None:
            raise ValueError("AuthenticatedClient must be provided.")
        if agent_router is None:
            raise ValueError("AgentRouter must be provided.")

        current_config = copy.deepcopy(DEFAULT_H4RM3L_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.h4rm3l")
        super().__init__(current_config, client, agent_router)

    def _setup(self) -> None:
        """Standard setup plus h4rm3l-specific initialisation."""
        super()._setup()
        params = self.config.get("h4rm3l_params", {})
        self.program = params.get("program", "IdentityDecorator()")
        self.syntax_version = params.get("syntax_version", 2)

        # Resolve preset name
        if self.program in PRESET_PROGRAMS:
            self.logger.info(f"Resolved preset program: {self.program}")
        else:
            self.logger.info(
                f"Using custom program (v{self.syntax_version}): {self.program[:80]}..."
            )

    def _validate_config(self):
        super()._validate_config()
        required_keys = ["attack_type", "h4rm3l_params"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {', '.join(missing)}")

        params = self.config.get("h4rm3l_params", {})
        if not params:
            raise ValueError("h4rm3l_params must be a non-empty dict")

        syntax_version = params.get("syntax_version", 2)
        if syntax_version not in (1, 2):
            raise ValueError(f"syntax_version must be 1 or 2, got {syntax_version}")

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the two-stage attack pipeline."""
        return [
            {
                "name": "Generation: Apply h4rm3l Decorators and Query Target",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "h4rm3l_params",
                    "decorator_llm",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Multi-Judge Response Evaluation",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "h4rm3l_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                    "judges",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                    "judge_request_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "client"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """
        Execute the full h4rm3l attack pipeline.

        Args:
            goals: List of goal strings to attack.

        Returns:
            List of result dicts with evaluation scores, or ``[]`` if
            no goals provided.
        """
        if not goals:
            return []

        # Create coordinator (deferred goal-result creation)
        coordinator = self._initialize_coordinator(attack_type="h4rm3l")

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        try:
            # Phase 1: Generation
            generation_output = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step, end_step=start_step + 1
            )

            if not generation_output:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            # Phase 2: Create goal results for surviving goals
            h4rm3l_params = self.config.get("h4rm3l_params", {})
            goal_metadata = {
                "attack_type": "h4rm3l",
                "program": h4rm3l_params.get("program", ""),
                "syntax_version": h4rm3l_params.get("syntax_version", 2),
            }
            coordinator.initialize_goals_from_pipeline_data(
                pipeline_data=generation_output,
                initial_metadata=goal_metadata,
            )

            if coordinator.has_goal_tracking:
                self.logger.info("Using TrackingCoordinator for per-goal tracking")

            if coordinator.goal_tracker:
                self.config["_tracker"] = coordinator.goal_tracker

            # Phase 3: Evaluation
            results = self._execute_pipeline(
                pipeline_steps, generation_output, start_step=start_step + 1
            )

            # Finalize
            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            coordinator.finalize_on_error("h4rm3l pipeline failed with exception")
            raise
