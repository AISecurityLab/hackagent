# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Static template attack implementation.

Uses predefined prompt templates to attempt jailbreaks by combining
templates with harmful goals.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.server.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging

from . import generation, static_eval as evaluation
from .config import DEFAULT_TEMPLATE_CONFIG


class StaticTemplateAttack(BaseAttack):
    """
    Static template attack using predefined prompt templates.

    Combines a library of prompt templates across several jailbreak
    categories with each goal string to produce attack prompts, sends
    them to the target model, and evaluates responses using a
    LLM judge pipeline.

    Pipeline stages
    ---------------
    1. **Generation** (:func:`~hackagent.attacks.techniques.static_template.generation.execute`) —
       selects up to ``templates_per_category`` templates from each
       category in ``template_categories``, injects each goal, and
       collects target-model responses.
     2. **Evaluation** (:func:`~hackagent.attacks.techniques.static_template.evaluation.execute`) —
         scores responses for jailbreak success using configured LLM judge(s).

    This attack is useful as a **sanity-check** with explicit LLM judging,
    surfacing naive template weaknesses in the target model.

    Attributes:
        config: Merged static template configuration dictionary.
        client: Authenticated HackAgent API client.
        agent_router: Router for the victim model.
        logger: Hierarchical logger at ``hackagent.attacks.static_template``.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize static template attack.

        Args:
            config: Configuration override dictionary merged into
                :data:`~hackagent.attacks.techniques.static_template.config.DEFAULT_TEMPLATE_CONFIG`.
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
        self.logger = logging.getLogger("hackagent.attacks.static_template")

        # Call parent - handles all setup
        super().__init__(current_config, client, agent_router)

    def _validate_config(self):
        """
        Validate static-template-specific configuration.

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
            "max_tokens",
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

    @classmethod
    def get_effective_model_roles(
        cls,
        attack_config: Dict[str, Any],
        *,
        goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Return model roles needed by static template evaluation.

        Static template always evaluates with LLM judges.
        """
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
        """
        Define the two static template pipeline stage descriptors.

        Stage 1 — **Generation**
            (:func:`~hackagent.attacks.techniques.static_template.generation.execute`):
            Selects templates, injects goals, and collects target responses.
            Configurable via ``template_categories``, ``templates_per_category``,
            ``max_tokens``, ``temperature``, and ``n_samples_per_template``.

        Stage 2 — **Evaluation**
            (:func:`~hackagent.attacks.techniques.static_template.evaluation.execute`):
            Scores responses for jailbreak success using configured LLM
            judge(s). Short responses (``< min_response_length``
            tokens) are skipped.

        Returns:
            List of pipeline-step configuration dicts compatible with
            :meth:`~hackagent.attacks.techniques.base.BaseAttack._execute_pipeline`.
        """
        return [
            {
                "name": "Generation: Generate and Execute Static Template Prompts",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "template_categories",
                    "templates_per_category",
                    "max_tokens",
                    "temperature",
                    "n_samples_per_template",
                    "_goal_index_offset",  # Global goal index offset in batched runs
                    "_tracker",  # Shared goal tracker from coordinator
                    "_run_id",  # For real-time result tracking
                    "_backend",  # For real-time result tracking (StorageBackend)
                    "_client",  # Legacy fallback
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
                    "_goal_index_offset",  # Global goal index offset in batched runs
                    "_tracker",  # Shared goal tracker from coordinator
                    "_run_id",  # For real-time result tracking
                    "_backend",  # For real-time result tracking (StorageBackend)
                    "_client",  # Legacy fallback
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
        """Inject shared goal tracker into static template stage functions."""
        args = super()._build_step_args(step_info, step_config, input_data)
        if self.coordinator and self.coordinator.goal_tracker:
            args["goal_tracker"] = self.coordinator.goal_tracker
            args["config"]["_tracker"] = self.coordinator.goal_tracker
        return args

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> Dict[str, Any]:
        """
        Execute static template attack.

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
            attack_type="static_template",
            goals=goals,
            initial_metadata={"objective": self.config.get("objective")},
        )

        # Keep tracker in attack config for compatibility paths that still read config.
        self.config["_tracker"] = coordinator.goal_tracker

        try:
            # Execute pipeline using base class
            results = self._execute_pipeline(self._get_pipeline_steps(), goals)

            # Custom success check for static_template (checks dict structure)
            def success_check(output):
                return output and isinstance(output, dict)

            # Finalize pipeline-level tracking via coordinator
            coordinator.finalize_pipeline(results, success_check)

            return results if results else {"evaluated": [], "summary": []}

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            # Crash-safe: finalize all tracking on error
            coordinator.finalize_on_error(
                "Static template pipeline failed with exception"
            )
            raise
