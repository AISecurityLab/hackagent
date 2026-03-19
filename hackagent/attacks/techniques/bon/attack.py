# Copyright 2026 - AI4I. All rights reserved.
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
Best-of-N (BoN) Jailbreaking attack implementation.

Stochastic black-box attack that generates N randomly augmented versions of a
harmful prompt — using word scrambling, random capitalization, and ASCII
perturbation — and picks the best candidate that elicits a harmful response
from the target model.

The attack runs in two pipeline stages:
1. **Generation** — multi-step search with K parallel candidates per step.
2. **Evaluation** — multi-judge scoring via BaseEvaluationStep.

Based on: https://arxiv.org/abs/2412.03556

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker.  The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.server.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation, evaluation
from .config import DEFAULT_BON_CONFIG


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


class BoNAttack(BaseAttack):
    """Best-of-N (BoN) Jailbreaking — stochastic text augmentation attack.

    Implements the Best-of-N technique from:
        Hughes et al., "Best-of-N Jailbreaking" (2024)
        https://arxiv.org/abs/2412.03556

    For each goal the attack runs ``n_steps`` sequential search steps.
    Within each step, ``num_concurrent_k`` independently-seeded augmented
    candidates are generated and sent to the target model in parallel.
    The best candidate is selected by response length (as a proxy for
    non-refusal), and a final multi-judge evaluation scores the result.

    Pipeline:
        1. Generation — multi-step BoN search with text augmentations
        2. Evaluation — multi-judge scoring via BaseEvaluationStep
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """Initialise BoNAttack with configuration.

        Args:
            config: Optional dictionary overriding
                :data:`~hackagent.attacks.techniques.bon.config.DEFAULT_BON_CONFIG`.
            client: AuthenticatedClient instance from the orchestrator.
            agent_router: AgentRouter instance for the target model.

        Raises:
            ValueError: If *client* or *agent_router* is ``None``.
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to BoNAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to BoNAttack."
            )

        # Merge user config with defaults
        current_config = copy.deepcopy(DEFAULT_BON_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.bon")
        super().__init__(current_config, client, agent_router)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_config(self):
        """Validate the provided configuration dictionary."""
        super()._validate_config()

        required_keys = ["attack_type", "bon_params"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        bon_params = self.config.get("bon_params", {})
        if bon_params.get("n_steps", 0) < 1:
            raise ValueError("bon_params.n_steps must be >= 1")
        if bon_params.get("num_concurrent_k", 0) < 1:
            raise ValueError("bon_params.num_concurrent_k must be >= 1")
        sigma = bon_params.get("sigma", 0.4)
        if not (0.0 < sigma <= 1.0):
            raise ValueError(f"bon_params.sigma must be in (0, 1], got {sigma}")

    # ------------------------------------------------------------------
    # Pipeline definition
    # ------------------------------------------------------------------

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the attack pipeline.

        The Generation step now includes inline judge evaluation (early-stop
        on jailbreak).  The Evaluation step is a lightweight post-processing
        pass that syncs results to the server and logs ASR.
        """
        return [
            {
                "name": "Generation: BoN Multi-Step Augmentation Search + Judge",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "bon_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                    # Judge config keys — used by inline _StepJudge
                    "judges",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                    "judge_request_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation Post-processing: Server Sync, Tracker & ASR Logging",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "bon_params",
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
        """Execute the full BoN attack pipeline.

        The generation step performs the multi-step BoN search **and** inline
        judge evaluation.  If a judge confirms a jailbreak at any step the
        search terminates early.  A lightweight post-processing step then
        syncs results to the server and logs ASR.

        Args:
            goals: A list of goal strings to test.

        Returns:
            List of result dictionaries, or empty list if no goals provided.
        """
        if not goals:
            return []

        # Phase 1: Create coordinator
        coordinator = self._initialize_coordinator(attack_type="bon")

        # Initialize per-goal tracking upfront so Generation can emit
        # candidate-level traces visible in dashboard.
        bon_params = self.config.get("bon_params", {})
        goal_metadata = {
            "n_steps": bon_params.get("n_steps", 4),
            "num_concurrent_k": bon_params.get("num_concurrent_k", 5),
            "sigma": bon_params.get("sigma", 0.4),
            "word_scrambling": bon_params.get("word_scrambling", True),
            "random_capitalization": bon_params.get("random_capitalization", True),
            "ascii_perturbation": bon_params.get("ascii_perturbation", True),
        }
        coordinator.initialize_goals(goals=goals, initial_metadata=goal_metadata)

        if coordinator.has_goal_tracking:
            self.logger.info("📊 Using TrackingCoordinator for per-goal tracking")

        # Make goal tracker available to Generation
        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        try:
            # Phase 2: Run Generation step (includes inline judge evaluation)
            generation_output = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step, end_step=start_step + 1
            )

            if not generation_output:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            # Phase 3: Run post-processing (server sync, tracker, ASR)
            results = self._execute_pipeline(
                pipeline_steps, generation_output, start_step=start_step + 1
            )

            # Finalize
            coordinator.finalize_all_goals(
                results,
                include_evaluation_trace=False,
            )
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            coordinator.finalize_on_error("BoN pipeline failed with exception")

            raise
