# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Prefix generation pipeline attack based on the BaseAttack class.

This module implements a complete pipeline for generating, filtering, and selecting prefixes
using uncensored and target language models, adapted as an attack module.

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

# Import step execution functions from same package
from . import completions
from .config import DEFAULT_PREFIX_GENERATION_CONFIG
from .evaluation import EvaluationPipeline
from .generate import PrefixGenerationPipeline


# Helper function for deep merging dictionaries
def _recursive_update(target_dict, source_dict):
    """
    Recursively updates a target dictionary with values from a source dictionary.
    Nested dictionaries are merged; other values are overwritten with a deep copy.
    Special internal keys (starting with '_') are passed by reference without copying.
    """
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            # If both current_value and update_value are dicts, recurse
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            # Internal keys (like _client, _run_id) are passed by reference
            # Don't deepcopy as they may contain unpicklable objects (locks, etc.)
            target_dict[key] = source_value
        else:
            # Otherwise, overwrite target_dict[key] with a deepcopy of source_value
            target_dict[key] = copy.deepcopy(source_value)


class AdvPrefixAttack(BaseAttack):
    """
    Attack class implementing the prefix generation pipeline by orchestrating step modules.

    Inherits from BaseAttack and adapts the multi-step prefix generation process.
    Expects configuration as a standard Python dictionary.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize the pipeline with configuration.

        Args:
            config: An optional dictionary containing pipeline parameters to override defaults.
            client: An AuthenticatedClient instance passed from the strategy.
            agent_router: An AgentRouter instance passed from the strategy.
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to AdvPrefixAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to AdvPrefixAttack."
            )

        # Merge config with defaults
        current_config = copy.deepcopy(DEFAULT_PREFIX_GENERATION_CONFIG)
        if config:
            _recursive_update(current_config, config)

        # Set logger name for hierarchical logging (TUI support)
        self.logger = logging.getLogger("hackagent.attacks.advprefix")

        # Call parent - handles run_id, run_dir, validation, setup
        super().__init__(current_config, client, agent_router)

    def _validate_config(self):
        """
        Validates the provided configuration dictionary.
        (Checks are now done on self.config which is a dict).
        """
        super()._validate_config()  # Base validation (checks if it's a dict)

        # Define required keys, noting that some steps might have optional dependencies
        # 'input_csv' removed as goals are passed to run()
        required_keys = [
            "output_dir",
            "start_step",
            # Keys needed for Preprocessor init
            "min_char_length",
            "max_token_segments",
            "n_candidates_per_goal",
            # Keys needed for Step 1
            "meta_prefixes",
            "meta_prefix_samples",
            "batch_size",
            "max_new_tokens",
            "guided_topk",
            "temperature",
            # Keys needed for Step 4
            "surrogate_attack_prompt",
            # Keys needed for Step 6
            "max_new_tokens_completion",
            "n_samples",
            # Keys needed for Step 7: Evaluation (includes judge evaluation, aggregation, and selection)
            "judges",
            "batch_size_judge",
            "max_new_tokens_eval",
            "filter_len",
            "n_prefixes_per_goal",
            "max_ce",  # Used in Step 5 (Preprocessor) and Step 7 (NLL filtering in aggregation)
        ]
        missing_keys = [k for k in required_keys if k not in self.config]
        if missing_keys:
            # Provide more context in the error message
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing_keys)}"
            )

        # Example type checks using .get()
        if not isinstance(self.config.get("meta_prefixes"), list):
            raise TypeError("Config key 'meta_prefixes' must be a list.")
        if not isinstance(self.config.get("judges"), list):
            raise TypeError("Config key 'judges' must be a list.")
        # Add more specific type/value checks as needed (e.g., check types within lists)

    def _get_pipeline_steps(self):
        """Define the attack pipeline configuration."""
        return [
            {
                "name": "Generation: Generate and Filter Adversarial Prefixes",
                "function": lambda **kwargs: PrefixGenerationPipeline(
                    logger=kwargs["logger"],
                    client=kwargs["client"],
                    agent_router=kwargs["agent_router"],
                    config=kwargs["config"],
                ).execute(goals=kwargs["goals"]),
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "generator",
                    "batch_size",
                    "max_new_tokens",
                    "guided_topk",
                    "temperature",
                    "meta_prefixes",
                    "meta_prefix_samples",
                    "min_char_length",
                    "max_ce",
                    "max_token_segments",
                    "n_candidates_per_goal",
                    "surrogate_attack_prompt",
                    "_run_id",  # For real-time result tracking
                    "_client",  # For real-time result tracking
                    "_tracker",  # For per-goal result tracking via Tracker
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "client", "config", "agent_router"],
            },
            {
                "name": "Execution: Get Completions from Target Model",
                "function": completions.execute,
                "step_type_enum": "EXECUTION",
                "config_keys": [
                    "batch_size",
                    "max_new_tokens_completion",
                    "n_samples",
                    "_run_id",
                    "_client",
                    "_tracker",  # For per-goal result tracking via Tracker
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "agent_router"],
            },
            {
                "name": "Evaluation: Judge, Aggregate, and Select Best Prefixes",
                "function": lambda input_data,
                config,
                logger,
                client: EvaluationPipeline(
                    config=config, logger=logger, client=client
                ).execute(input_data=input_data),
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "judges",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                    "n_prefixes_per_goal",
                    "max_ce",
                    "_run_id",  # For real-time result tracking
                    "_client",  # For real-time result tracking
                    "_tracker",  # For per-goal result tracking via Tracker
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "client", "config"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """
        Executes the full prefix generation pipeline.

        Uses TrackingCoordinator to manage both pipeline-level and
        per-goal result tracking through a single unified interface.

        Args:
            goals: A list of goal strings to generate prefixes for.

        Returns:
            List of dictionaries containing the final selected prefixes,
            or empty list if no prefixes were generated.
        """
        if not goals:
            return []

        # Initialize unified coordinator (replaces separate StepTracker + Tracker)
        coordinator = self._initialize_coordinator(
            attack_type="advprefix",
            goals=goals,
            initial_metadata={
                "n_candidates_per_goal": self.config.get("n_candidates_per_goal", 5),
                "n_prefixes_per_goal": self.config.get("n_prefixes_per_goal", 2),
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
            coordinator.finalize_on_error("AdvPrefix pipeline failed with exception")
            raise
