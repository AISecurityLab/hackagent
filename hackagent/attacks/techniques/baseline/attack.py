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
Baseline attack implementation.

Uses predefined prompt templates to attempt jailbreaks by combining
templates with harmful goals.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.client import AuthenticatedClient
from hackagent.models import StatusEnum
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack

from . import generation, evaluation
from .config import DEFAULT_TEMPLATE_CONFIG

# TUI logging support - lazy loaded to avoid circular imports
_with_tui_logging = None


def _get_tui_logging_decorator():
    """Lazily import the TUI logging decorator to avoid circular imports."""
    global _with_tui_logging
    if _with_tui_logging is not None:
        return _with_tui_logging

    try:
        from hackagent.cli.tui.logger import with_tui_logging

        _with_tui_logging = with_tui_logging
    except ImportError:

        def with_tui_logging(*args, **kwargs):
            def decorator(func):
                return func

            return decorator

        _with_tui_logging = with_tui_logging

    return _with_tui_logging


def with_tui_logging(*args, **kwargs):
    """Wrapper that lazily loads the actual TUI logging decorator."""
    decorator = _get_tui_logging_decorator()
    return decorator(*args, **kwargs)


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

        Args:
            goals: List of harmful goals to test

        Returns:
            Dictionary with 'evaluated' and 'summary' DataFrames
        """
        if not goals:
            return {"evaluated": [], "summary": []}

        # Initialize tracking using base class
        self.tracker = self._initialize_tracking(
            "baseline",
            goals,
            metadata={"objective": self.config.get("objective")},
        )

        try:
            # Execute pipeline using base class
            results = self._execute_pipeline(self._get_pipeline_steps(), goals)

            # Custom success check for baseline (checks dict structure)
            def success_check(output):
                return output and isinstance(output, dict)

            # Finalize using base class
            self._finalize_pipeline(results, success_check)

            return results if results else {"evaluated": [], "summary": []}

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            if self.tracker:
                self.tracker.update_run_status(StatusEnum.FAILED)
            raise
