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
    Baseline attack using predefined prompt templates.

    Combines a library of prompt templates across several jailbreak
    categories with each goal string to produce attack prompts, sends
    them to the target model, and evaluates responses using a
    configurable evaluator (pattern-matching, keyword, or LLM judge).

    Pipeline stages
    ---------------
    1. **Generation** (:func:`~hackagent.attacks.techniques.baseline.generation.execute`) —
       selects up to ``templates_per_category`` templates from each
       category in ``template_categories``, injects each goal, and
       collects target-model responses.
    2. **Evaluation** (:func:`~hackagent.attacks.techniques.baseline.evaluation.execute`) —
       scores responses for jailbreak success using the configured
       ``evaluator_type`` (``"pattern"``, ``"keyword"``, or ``"llm_judge"``).

    This attack is useful as a **sanity-check baseline**: it requires no
    additional LLM (unlike PAIR/TAP/AdvPrefix) and surfaces naive template
    weaknesses in the target model.

    Attributes:
        config: Merged baseline configuration dictionary.
        client: Authenticated HackAgent API client.
        agent_router: Router for the victim model.
        logger: Hierarchical logger at ``hackagent.attacks.baseline``.
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
            config: Configuration override dictionary merged into
                :data:`~hackagent.attacks.techniques.baseline.config.DEFAULT_TEMPLATE_CONFIG`.
            client: Authenticated HackAgent API client.
            agent_router: Router for the victim model.

        Raises:
            ValueError: If ``client`` or ``agent_router`` is ``None``.
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
        """
        Validate baseline-specific configuration.

        Checks presence of all required top-level keys and verifies that
        the configured ``objective`` exists in the
        :data:`~hackagent.attacks.objectives.OBJECTIVES` registry.

        Raises:
            ValueError: If any required key is missing or the ``objective``
                is not a registered objective name.
        """
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
        """
        Define the two baseline pipeline stage descriptors.

        Stage 1 — **Generation**
            (:func:`~hackagent.attacks.techniques.baseline.generation.execute`):
            Selects templates, injects goals, and collects target responses.
            Configurable via ``template_categories``, ``templates_per_category``,
            ``max_new_tokens``, ``temperature``, and ``n_samples_per_template``.

        Stage 2 — **Evaluation**
            (:func:`~hackagent.attacks.techniques.baseline.evaluation.execute`):
            Scores responses for jailbreak success using the configured
            ``evaluator_type``.  Short responses (``< min_response_length``
            tokens) are skipped.

        Returns:
            List of pipeline-step configuration dicts compatible with
            :meth:`~hackagent.attacks.techniques.base.BaseAttack._execute_pipeline`.
        """
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
