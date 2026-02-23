# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Baseline attack implementation.

Uses predefined prompt templates to attempt jailbreaks by combining
templates with harmful goals.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation, evaluation
from .config import DEFAULT_TEMPLATE_CONFIG


class BaselineAttack(BaseAttack):
    """
    Baseline attack using predefined prompt patterns.

    Combines templates with goals to generate jailbreak attempts,
    then evaluates responses using objective-based criteria.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize baseline attack.

        Args:
            config: Configuration dictionary
            client: Authenticated client for API calls
            agent_router: Target agent router
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided")
        if agent_router is None:
            raise ValueError("AgentRouter must be provided")

        # Merge config with defaults
        current_config = copy.deepcopy(DEFAULT_TEMPLATE_CONFIG)
        if config:
            current_config.update(config)

        # Set logger name for hierarchical logging
        self.logger = logging.getLogger("hackagent.attacks.baseline")

        # Call parent - handles all setup
        super().__init__(current_config, client, agent_router)

    def _validate_config(self):
        """Validate configuration."""
        super()._validate_config()

        required_keys = [
            "output_dir",
            "template_categories",
            "templates_per_category",
            "max_new_tokens",
            "objective",
        ]

        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")

        # Validate objective exists
        from hackagent.attacks.objectives import OBJECTIVES

        objective = self.config.get("objective")
        if objective not in OBJECTIVES:
            raise ValueError(
                f"Unknown objective: {objective}. Available: {list(OBJECTIVES.keys())}"
            )

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define attack pipeline."""
        return [
            {
                "name": "Generation: Generate and Execute Baseline Prompts",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "template_categories",
                    "templates_per_category",
                    "max_new_tokens",
                    "temperature",
                    "n_samples_per_template",
                    "_run_id",  # For real-time result tracking
                    "_client",  # For real-time result tracking
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Evaluate Responses and Aggregate Results",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "objective",
                    "evaluator_type",
                    "min_response_length",
                    "_run_id",  # For real-time result tracking
                    "_client",  # For real-time result tracking
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> Dict[str, Any]:
        """
        Execute baseline attack.

        Uses TrackingCoordinator for unified pipeline and goal tracking.

        Args:
            goals: List of harmful goals to test

        Returns:
            Dictionary with 'evaluated' and 'summary' DataFrames
        """
        if not goals:
            return {"evaluated": [], "summary": []}

        # Initialize unified coordinator
        coordinator = self._initialize_coordinator(
            attack_type="baseline",
            goals=goals,
            initial_metadata={"objective": self.config.get("objective")},
        )

        try:
            # Execute pipeline using base class
            results = self._execute_pipeline(self._get_pipeline_steps(), goals)

            # Custom success check for baseline (checks dict structure)
            def success_check(output):
                return output and isinstance(output, dict)

            # Finalize pipeline-level tracking via coordinator
            coordinator.finalize_pipeline(results, success_check)

            return results if results else {"evaluated": [], "summary": []}

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            # Crash-safe: finalize all tracking on error
            coordinator.finalize_on_error("Baseline pipeline failed with exception")
            raise
