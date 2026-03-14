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
    AdvPrefix attack — adversarial prefix generation pipeline.

    Implements a multi-stage pipeline that:

    1. **Generation** — uses an uncensored generator LLM to produce
       candidate adversarial prefixes for each harmless meta-prompt.
       Prefixes are filtered by cross-entropy (``max_ce``) and token
       segment count before being passed downstream.
    2. **Execution** — appends each surviving prefix to the target model
       prompt and collects completions (``n_samples`` per prefix).
    3. **Evaluation** — LLM judges (e.g. HarmBench) rate each completion;
       the top-``n_prefixes_per_goal`` prefixes per goal are selected and
       returned.

    The class delegates stage logic to dedicated sub-modules:

    * :mod:`~hackagent.attacks.techniques.advprefix.generate`
      (:class:`PrefixGenerationPipeline`) for steps 1 and internal
      filtering.
    * :mod:`~hackagent.attacks.techniques.advprefix.completions` for
      step 2.
    * :mod:`~hackagent.attacks.techniques.advprefix.evaluation`
      (:class:`EvaluationPipeline`) for step 3.

    Tracking is managed by
    :class:`~hackagent.router.tracking.TrackingCoordinator`; goal
    :class:`~hackagent.router.tracking.Tracker` instances and a pipeline
    :class:`~hackagent.router.tracking.StepTracker` are created upfront so
    the dashboard shows all goals from the moment the run starts.

    Attributes:
        config: Merged AdvPrefix configuration dictionary.
        client: Authenticated HackAgent API client.
        agent_router: Router for the victim model.
        logger: Hierarchical logger at ``hackagent.attacks.advprefix``.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize the AdvPrefix attack pipeline.

        Args:
            config: Optional dictionary of parameter overrides merged into
                :data:`~hackagent.attacks.techniques.advprefix.config.DEFAULT_PREFIX_GENERATION_CONFIG`
                using a deep-merge strategy (nested dicts are merged;
                internal keys starting with ``_`` are passed by reference).
            client: Authenticated HackAgent API client.
            agent_router: Router for the victim model.

        Raises:
            ValueError: If ``client`` or ``agent_router`` is ``None``.
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
        Validate the AdvPrefix configuration dictionary.

        Checks type (must be ``dict``) and presence of all keys required
        across the three pipeline stages.  Also enforces that
        ``meta_prefixes`` and ``judges`` are lists.

        Raises:
            ValueError: If any required key is absent from ``self.config``.
            TypeError: If ``meta_prefixes`` or ``judges`` are not lists.
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
        """
        Define the three AdvPrefix pipeline stage descriptors.

        Stage 1 — **Generation** (:class:`PrefixGenerationPipeline`):
            Produces candidate adversarial prefixes via the generator LLM,
            applies CE and token-segment filters, and returns one row per
            (goal, candidate_prefix) pair.

        Stage 2 — **Execution** (:func:`~hackagent.attacks.techniques.advprefix.completions.execute`):
            Appends each prefix to the target-model prompt and collects
            ``n_samples`` completions per prefix.

        Stage 3 — **Evaluation** (:class:`EvaluationPipeline`):
            Runs LLM judges, merges scores, aggregates by NLL, and
            selects the top ``n_prefixes_per_goal`` per goal.

        Returns:
            List of pipeline-step configuration dicts compatible with
            :meth:`~hackagent.attacks.techniques.base.BaseAttack._execute_pipeline`.
        """
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
                    "_tracker",  # For per-goal prefix generation traces
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
                    "_tracker",  # For per-goal result tracking via Tracker
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "agent_router"],
            },
            {
                "name": "Evaluation: Judge, Aggregate, and Select Best Prefixes",
                "function": lambda input_data, config, logger, client: (
                    EvaluationPipeline(
                        config=config, logger=logger, client=client
                    ).execute(input_data=input_data)
                ),
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "judges",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                    "n_prefixes_per_goal",
                    "max_ce",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "client", "config"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """
        Executes the full prefix generation pipeline.

        Goal Results are created upfront (before any pipeline step) so the
        dashboard shows all goals from the moment the run starts.  Goals that
        are filtered out during Generation are marked with an explanatory note
        during finalization rather than simply having no record.

        Args:
            goals: A list of goal strings to generate prefixes for.

        Returns:
            List of dictionaries containing the final selected prefixes,
            or empty list if no prefixes were generated.
        """
        if not goals:
            return []

        # Phase 1: Create coordinator AND goal Results immediately so the
        # dashboard shows all goals from the moment the run starts.
        # Goals filtered out during Generation are marked as such during
        # finalization rather than simply having no record.
        goal_metadata = {
            "n_candidates_per_goal": self.config.get("n_candidates_per_goal", 5),
            "n_prefixes_per_goal": self.config.get("n_prefixes_per_goal", 2),
        }
        coordinator = self._initialize_coordinator(
            attack_type="advprefix",
            goals=goals,
            initial_metadata=goal_metadata,
        )

        # Make the goal_tracker available to all pipeline steps via config
        # so Execution and Evaluation can attach per-goal traces.
        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        try:
            # Phase 2: Run Generation step.
            # Goal Results and the StepTracker are fully linked, so the
            # Generation start/summary traces land on goal[0]'s Result.
            generation_output = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step, end_step=start_step + 1
            )

            if not generation_output:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            if coordinator.has_goal_tracking:
                self.logger.info("📊 Using TrackingCoordinator for per-goal tracking")

            # Phase 3: Run Execution + Evaluation steps.
            results = self._execute_pipeline(
                pipeline_steps, generation_output, start_step=start_step + 1
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
