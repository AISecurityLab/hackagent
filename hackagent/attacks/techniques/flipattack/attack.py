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
FlipAttack implementation.

Character-level adversarial attack that flips characters, words, or sentences
to bypass LLM safety measures.

Based on: https://arxiv.org/abs/2410.02832

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker. The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation, evaluation
from .config import DEFAULT_FLIPATTACK_CONFIG


def _recursive_update(target_dict, source_dict):
    """
    Recursively updates a target dictionary with values from a source dictionary.
    Nested dictionaries are merged; other values are overwritten with a deep copy.
    Special internal keys (starting with '_') are passed by reference without copying.
    """
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


class FlipAttack(BaseAttack):
    """
    Attack class implementing FlipAttack using character-level transformations.

    Inherits from BaseAttack and adapts the FlipAttack process.
    Expects configuration as a standard Python dictionary.

    Supports 4 flip modes:
    - FWO: Flip Word Order
    - FCW: Flip Chars in Word
    - FCS: Flip Chars in Sentence
    - FMM: Fool Model Mode (FCS + reverse instruction)

    Optional enhancements:
    - CoT: Chain-of-thought reasoning
    - LangGPT: Structured prompting format
    - Few-shot: Task-oriented demonstrations
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize FlipAttack with configuration.

        Args:
            config: Optional dictionary containing parameters to override defaults.
            client: AuthenticatedClient instance passed from the strategy.
            agent_router: AgentRouter instance for the target model.
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to FlipAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to FlipAttack."
            )

        # Merge config with defaults
        current_config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)
        if config:
            _recursive_update(current_config, config)

        # Set logger name for hierarchical logging (TUI support)
        self.logger = logging.getLogger("hackagent.attacks.flipattack")

        # Call parent - handles run_id, run_dir, validation, setup
        super().__init__(current_config, client, agent_router)

    def _validate_config(self):
        """Validate the provided configuration dictionary."""
        super()._validate_config()

        required_keys = [
            "attack_type",
            "flipattack_params",
            "goals",
            "output_dir",
        ]

        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        # Validate flip_mode
        fa_params = self.config.get("flipattack_params", {})
        valid_modes = ["FWO", "FCW", "FCS", "FMM"]
        flip_mode = fa_params.get("flip_mode", "FCS")

        if flip_mode not in valid_modes:
            raise ValueError(
                f"flip_mode must be one of {valid_modes}, got '{flip_mode}'"
            )

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the attack pipeline configuration."""
        return [
            {
                "name": "Generation: Generate and Execute FlipAttack Prompts",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "flipattack_params",
                    "_run_id",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Evaluate Responses with Dict + LLM Judge",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "flipattack_params",
                    "_run_id",
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
        Execute the full FlipAttack pipeline.

        Uses TrackingCoordinator to manage both pipeline-level and
        per-goal result tracking through a single unified interface.

        Args:
            goals: A list of goal strings to test.

        Returns:
            List of dictionaries containing evaluation results,
            or empty list if no goals provided.
        """
        if not goals:
            return []

        # Initialize unified coordinator (replaces separate StepTracker + Tracker)
        coordinator = self._initialize_coordinator(
            attack_type="flipattack",
            goals=goals,
            initial_metadata={
                "flip_mode": self.config.get("flipattack_params", {}).get(
                    "flip_mode", "FCS"
                ),
                "cot": self.config.get("flipattack_params", {}).get("cot", False),
                "lang_gpt": self.config.get("flipattack_params", {}).get(
                    "lang_gpt", False
                ),
                "few_shot": self.config.get("flipattack_params", {}).get(
                    "few_shot", False
                ),
                "judge": self.config.get("flipattack_params", {}).get(
                    "judge", "gpt-4-0613"
                ),
            },
        )

        if coordinator.has_goal_tracking:
            self.logger.info("📊 Using TrackingCoordinator for per-goal tracking")

        # Pass goal_tracker through config for sub-modules that still need it
        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        # Execute pipeline using base class method
        start_step = self.config.get("start_step", 1) - 1

        try:
            results = self._execute_pipeline(
                self._get_pipeline_steps(), goals, start_step
            )

            # Finalize goal results via coordinator
            coordinator.finalize_all_goals(results)

            # Log summary
            coordinator.log_summary()

            # Finalize pipeline-level tracking
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            # Crash-safe: mark all unfinalized goals as failed
            coordinator.finalize_on_error("FlipAttack pipeline failed with exception")
            raise
