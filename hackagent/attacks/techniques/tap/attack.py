# Copyright 2025 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TAP (Tree of Attacks with Pruning) attack implementation.

Implements the TAP algorithm from:
    Mehrotra et al., "Tree of Attacks with Pruning: Efficient
    Adversarial Prompting of Large Language Models" (2023)
    https://arxiv.org/abs/2312.02119

Algorithm overview
------------------
TAP performs a bounded tree search where each node represents an
attacker-generated prompt candidate:

1. **Branching** — an attacker LLM generates ``branching_factor``
   refinements of the current prompt in parallel ``n_streams`` streams.
2. **On-topic pruning** — a judge (or the main judge) discards branches
   whose prompts have drifted off-topic (``min_on_topic_score`` threshold).
3. **Target query** — surviving prompts are sent to the victim model.
4. **Score pruning** — only the top-``width`` branches by jailbreak score
   are kept for the next depth level.
5. **Termination** — search stops when ``depth`` levels are exhausted or
   a branch exceeds ``success_score_threshold``.

Key parameters (``tap_params`` in config)
-----------------------------------------
depth
    Maximum tree depth (number of refinement rounds per stream).
width
    Maximum branches kept after scoring at each depth level.
branching_factor
    Prompt refinements generated per active branch at each step.
n_streams
    Number of independent root-to-leaf searches run in parallel.
keep_last_n
    Conversation history window per stream (controls attacker context size).
early_stop_on_success
    Stop all streams as soon as one branch crosses the success threshold.
min_on_topic_score
    Minimum on-topic score (0 or 1) to retain a branch after on-topic pruning.
success_score_threshold
    Judge score that signals a successful jailbreak (default 1 for binary judges).
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.attacks.shared.tui import with_tui_logging
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.client import AuthenticatedClient
from hackagent.router.router import AgentRouter

from . import evaluation, generation
from .config import DEFAULT_TAP_CONFIG


def _recursive_update(target_dict: Dict[str, Any], source_dict: Dict[str, Any]) -> None:
    """
    Recursively update a target dict with a source dict.

    Args:
        target_dict: Dictionary to be updated in-place.
        source_dict: Dictionary providing updates.

    Returns:
        None. The target_dict is updated in-place.
    """
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        else:
            if isinstance(key, str) and key.startswith("_"):
                target_dict[key] = source_value
            else:
                target_dict[key] = copy.deepcopy(source_value)


class TAPAttack(BaseAttack):
    """
    TAP (Tree of Attacks with Pruning) attack.

    Orchestrates the TAP tree search by delegating to
    :mod:`~hackagent.attacks.techniques.tap.generation` (attacker loop
    and target queries) and
    :mod:`~hackagent.attacks.techniques.tap.evaluation` (judge scoring).

    The attack expects three collaborating models configured via
    ``config``:

    * **Attacker** (``config["attacker"]``) — LLM that proposes prompt
      refinements from conversation history.
    * **Target** — the victim model reached via ``agent_router``.
    * **Judge** (``config["judge"]``) — LLM that rates jailbreak success
      0–10 (or 0/1 for binary judges such as HarmBench).
    * **On-topic judge** (``config["on_topic_judge"]``, optional) —
      separate evaluator that checks whether a prompt stays on-topic.
      When ``None``, the configured judge is reused with the on-topic
      evaluation type.

    The :meth:`run` method manages the full pipeline via
    :class:`~hackagent.router.tracking.TrackingCoordinator`:
    a coordinator handles per-goal :class:`~hackagent.router.tracking.Tracker`
    lifecycle and pipeline-level :class:`~hackagent.router.tracking.StepTracker`
    checkpointing.

    Attributes:
        config: Merged TAP configuration dictionary.
        client: Authenticated HackAgent API client.
        agent_router: Router for the victim model.
        logger: Hierarchical logger at ``hackagent.attacks.tap``.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize TAP with configuration and routers.

        Args:
            config: Optional config overrides merged into
                :data:`~hackagent.attacks.techniques.tap.config.DEFAULT_TAP_CONFIG`.
                Keys from ``config`` win over defaults; nested dicts are
                deep-merged via :func:`_recursive_update`.
            client: Authenticated API client.
            agent_router: Router for the victim model.

        Raises:
            ValueError: If ``client`` or ``agent_router`` is ``None``.
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to TAPAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to TAPAttack."
            )

        current_config = copy.deepcopy(DEFAULT_TAP_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.tap")

        super().__init__(current_config, client, agent_router)

    def _validate_config(self) -> None:
        """
        Validate TAP-specific configuration.

        Checks that the required top-level keys are present **and** that
        the numeric ``tap_params`` values satisfy the algorithm constraints
        (all of ``depth``, ``width``, ``branching_factor``, ``n_streams``
        must be ≥ 1).

        Raises:
            ValueError: If any required key is missing or a ``tap_params``
                integer is less than 1.
        """
        super()._validate_config()

        required_keys = ["attack_type", "tap_params", "output_dir"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        tap_params = self.config.get("tap_params", {})
        for key in ["depth", "width", "branching_factor", "n_streams"]:
            value = tap_params.get(key)
            if value is None or value < 1:
                raise ValueError(f"tap_params.{key} must be >= 1")

    def _get_pipeline_steps(self) -> List[Dict]:
        """
        Define the two TAP pipeline stages.

        Stage 1 — **Generation** (:func:`~hackagent.attacks.techniques.tap.generation.execute`):
            Runs the full tree-of-attacks-with-pruning search and collects
            the best adversarial prompt found per goal.

        Stage 2 — **Evaluation** (:func:`~hackagent.attacks.techniques.tap.evaluation.execute`):
            Runs all configured judges on the generation output and computes
            ``best_score`` / ``success`` columns.

        Returns:
            List of pipeline-step configuration dicts compatible with
            :meth:`~hackagent.attacks.techniques.base.BaseAttack._execute_pipeline`.
        """
        return [
            {
                "name": "Generation: TAP search",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "tap_params",
                    "attacker",
                    "judges",
                    "judge",
                    "on_topic_judge",
                    "target_str",
                    "max_new_tokens",
                    "temperature",
                    "top_p",
                    "request_timeout",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                    "judge_request_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                    "organization_id",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config", "client"],
            },
            {
                "name": "Evaluation: TAP scoring",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "tap_params",
                    "judges",
                    "judge",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                    "judge_request_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                    "organization_id",
                    "_tracker",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "client"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict[str, Any]]:
        """
        Run TAP end-to-end with unified tracking and pipeline steps.

        Args:
            goals: List of goal strings to attack.

        Returns:
            List of per-goal result dicts produced by the pipeline.
        """
        if not goals:
            return []

        tap_params = self.config.get("tap_params", {})
        depth = tap_params.get("depth", 3)
        width = tap_params.get("width", 4)
        branching_factor = tap_params.get("branching_factor", 3)
        n_streams = tap_params.get("n_streams", 4)

        coordinator = self._initialize_coordinator(
            attack_type="tap",
            goals=goals,
            initial_metadata={
                "depth": depth,
                "width": width,
                "branching_factor": branching_factor,
                "n_streams": n_streams,
            },
        )

        if coordinator.has_goal_tracking:
            self.logger.info("Using TrackingCoordinator for per-goal tracking")

        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        start_step = self.config.get("start_step", 1) - 1

        try:
            results = self._execute_pipeline(
                self._get_pipeline_steps(), goals, start_step
            )

            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception as exc:
            self.logger.error(f"TAP attack failed: {exc}", exc_info=True)
            coordinator.finalize_on_error("TAP attack failed with exception")
            raise
