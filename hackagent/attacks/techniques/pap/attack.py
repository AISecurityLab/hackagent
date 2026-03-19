# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
PAP (Persuasive Adversarial Prompts) attack implementation.

Uses a taxonomy of 40 persuasion techniques to paraphrase harmful prompts
into persuasive variants.  An attacker LLM performs the paraphrasing via
in-context learning, and the resulting prompts are sent to the target model.
A multi-judge evaluation determines attack success.

The attack runs in two pipeline stages:
1. **Generation** — for each goal, iterate over selected persuasion
   techniques.  The attacker LLM paraphrases the goal, the persuasive
   prompt is sent to the target, and a judge evaluates the response.
   If a jailbreak is confirmed, remaining techniques are skipped.
2. **Evaluation** — post-processing: server sync, tracker, ASR logging.

Based on: https://arxiv.org/abs/2401.06373
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.server.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation, evaluation
from .config import DEFAULT_PAP_CONFIG


def _recursive_update(target_dict, source_dict):
    """Recursively merge *source_dict* into *target_dict*.

    Nested dictionaries are merged recursively.  Internal keys (starting
    with ``_``) are passed by reference; all other values are deep-copied.
    """
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


class PAPAttack(BaseAttack):
    """Persuasive Adversarial Prompts (PAP) — taxonomy-guided persuasion attack.

    Implements the PAP technique from:
        Zeng et al., "How Johnny Can Persuade LLMs to Jailbreak Them:
        Rethinking Persuasion to Challenge AI Safety by Humanizing LLMs" (2024)
        https://arxiv.org/abs/2401.06373

    For each goal the attack iterates over selected persuasion techniques.
    For each technique, the attacker LLM paraphrases the goal into a
    persuasive variant, which is sent to the target model.  A judge
    evaluates the response and if a jailbreak is confirmed, the remaining
    techniques are skipped (early stop).

    Pipeline:
        1. Generation — persuasive paraphrasing + target query + inline judge
        2. Evaluation — post-processing (server sync, tracker, ASR)
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to PAPAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to PAPAttack."
            )

        current_config = copy.deepcopy(DEFAULT_PAP_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.pap")
        super().__init__(current_config, client, agent_router)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_config(self):
        super()._validate_config()

        required_keys = ["attack_type", "pap_params"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        pap_params = self.config.get("pap_params", {})
        techniques = pap_params.get("techniques", "top5")
        if isinstance(techniques, str) and techniques not in ("top5", "all"):
            raise ValueError(
                f"pap_params.techniques must be 'top5', 'all', or a list; got '{techniques}'"
            )

    # ------------------------------------------------------------------
    # Pipeline definition
    # ------------------------------------------------------------------

    def _get_pipeline_steps(self) -> List[Dict]:
        return [
            {
                "name": "Generation: PAP Persuasive Paraphrasing + Judge",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "pap_params",
                    "attacker",
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
                    "max_new_tokens",
                    "temperature",
                    "request_timeout",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation Post-processing: Server Sync, Tracker & ASR Logging",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "pap_params",
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

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """Execute the full PAP attack pipeline.

        Args:
            goals: A list of goal strings to test.

        Returns:
            List of result dictionaries.
        """
        if not goals:
            return []

        coordinator = self._initialize_coordinator(attack_type="pap")

        pap_params = self.config.get("pap_params", {})
        goal_metadata = {
            "techniques": pap_params.get("techniques", "top5"),
            "max_techniques_per_goal": pap_params.get("max_techniques_per_goal", 0),
        }
        coordinator.initialize_goals(goals=goals, initial_metadata=goal_metadata)

        if coordinator.has_goal_tracking:
            self.logger.info("📊 Using TrackingCoordinator for per-goal tracking")

        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        try:
            # Generation step (includes inline judge evaluation)
            generation_output = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step, end_step=start_step + 1
            )

            if not generation_output:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            # Evaluation post-processing
            results = self._execute_pipeline(
                pipeline_steps, generation_output, start_step=start_step + 1
            )

            coordinator.finalize_all_goals(
                results,
                include_evaluation_trace=False,
            )
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            coordinator.finalize_on_error("PAP pipeline failed with exception")
            raise
