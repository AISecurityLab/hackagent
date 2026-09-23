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

from hackagent.storage.store import Store
from hackagent.attacks._lib.llm_router import LLMRouter
from hackagent.attacks.ports import RunContext
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.types import AttackResult, rows_to_attack_results

from . import generation
from .config import DEFAULT_TEMPLATE_CONFIG, validate_template_config
from hackagent.attacks.techniques.static_template.config import TemplateAttackConfig


class StaticTemplateAttack(BaseAttack):
    """
    Static template attack using predefined prompt templates.

    Combines a library of prompt templates across several jailbreak
    categories with each goal string to produce attack prompts and sends
    them to the target model. Scoring is not an embedded pipeline step;
    ``HackAgent.hack`` runs the shared evaluator afterward.

    Construct with ``(config, ctx)``. ``config`` is a dict merged into
    :data:`~hackagent.attacks.techniques.static_template.config.DEFAULT_TEMPLATE_CONFIG`.
    ``ctx`` is a :class:`~hackagent.attacks.ports.RunContext`, passed
    positionally or as ``ctx=``. Tests build it with ``make_ctx()``
    (``tests.fakes.context``). The legacy constructor
    ``(config_dict, client, agent_router)`` is obsolete for new code;
    the orchestrator still calls it. Typed defaults still live on
    :class:`~hackagent.attacks.techniques.static_template.config.TemplateAttackConfig`,
    a :class:`~hackagent.attacks.techniques.config.ConfigBase` subclass.

    Pipeline stages
    ---------------
    1. **Generation** (:func:`~hackagent.attacks.techniques.static_template.generation.execute`) —
       selects up to ``templates_per_category`` templates from each
       category in ``template_categories``, injects each goal, and
       collects target-model responses.

    Attributes:
        config: Merged static template configuration dictionary.
        ctx: RunContext on the new seam, otherwise None.
        logger: Hierarchical logger at ``hackagent.attacks.static_template``.
    """

    config_model = TemplateAttackConfig

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        ctx_or_client: Any = None,
        agent_router: Optional[LLMRouter] = None,
        *,
        ctx: Optional[RunContext] = None,
        client: Optional[Store] = None,
    ):
        """
        Initialize static template attack.

        Args:
            config: Configuration override dictionary merged into
                :data:`~hackagent.attacks.techniques.static_template.config.DEFAULT_TEMPLATE_CONFIG`.
            ctx: :class:`~hackagent.attacks.ports.RunContext`. Positional
                or ``ctx=``. Tests use ``make_ctx()``.
            client: Obsolete. Storage backend on the orchestrator path.
            agent_router: Obsolete. Target router on the orchestrator path.

        Raises:
            ValueError: On the legacy path, if ``client`` or
                ``agent_router`` is ``None``.
        """
        if ctx is None and isinstance(ctx_or_client, RunContext):
            ctx = ctx_or_client
        resolved_client = (
            client
            if client is not None
            else (None if isinstance(ctx_or_client, RunContext) else ctx_or_client)
        )
        if ctx is None:
            if resolved_client is None:
                raise ValueError("A storage backend must be provided")
            if agent_router is None:
                raise ValueError("LLMRouter must be provided")
            client = resolved_client

        # Merge config with defaults
        current_config = copy.deepcopy(DEFAULT_TEMPLATE_CONFIG)
        if config:
            current_config.update(config)

        # Set logger name for hierarchical logging
        self.logger = logging.getLogger("hackagent.attacks.static_template")

        # Call parent - handles all setup
        if ctx is not None:
            super().__init__(current_config, ctx)
        else:
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

        validate_template_config(self.config)

        # Validate objective exists
        from hackagent.attacks._lib.objectives import OBJECTIVES

        objective = self.config.get("objective")
        if objective not in OBJECTIVES:
            raise ValueError(
                f"Unknown objective: {objective}. Available: {list(OBJECTIVES.keys())}"
            )

    def _get_pipeline_steps(self) -> List[Dict]:
        """
        Define the static template pipeline.

        **Generation**
            (:func:`~hackagent.attacks.techniques.static_template.generation.execute`):
            Selects templates, injects goals, and collects target responses.
            Configurable via ``template_categories``, ``templates_per_category``,
            ``max_tokens``, ``temperature``, and ``n_samples_per_template``.
            The embedded evaluation step is gone; ``run()`` returns rows
            without a verdict.

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
                    "template_parameters",
                    "batch_size",
                    "max_tokens",
                    "temperature",
                    "n_samples_per_template",
                    "_goal_index_offset",  # Global goal index offset in batched runs
                    "_tracker",  # Shared goal tracker from coordinator
                    "_run_id",  # For real-time result tracking
                    "_backend",  # For real-time result tracking (Store)
                    "_client",  # Legacy fallback
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            }
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

    def run(self, goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]:
        """
        Execute static template attack.

        Uses TrackingCoordinator for unified pipeline and goal tracking.

        Args:
            goals: List of harmful goals to test

        Returns:
            A list of :class:`~hackagent.attacks.types.AttackResult` instances.
        """
        goals = goals or []
        if not goals:
            return []

        validate_template_config(self.config)

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
                return bool(output) and isinstance(output, (dict, list))

            # Finalize pipeline-level tracking via coordinator
            coordinator.finalize_pipeline(results, success_check)

            return rows_to_attack_results(results if results else [])

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            # Crash-safe: finalize all tracking on error
            coordinator.finalize_on_error(
                "Static template pipeline failed with exception"
            )
            raise
