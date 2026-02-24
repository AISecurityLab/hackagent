"""TAP (Tree of Attacks with Pruning) implementation."""

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
    TAP (Tree of Attacks with Pruning).

    Uses an attacker LLM to generate candidate prompts, prunes off-topic
    prompts, queries the target, and prunes to the top-scoring branches.
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
            config: Optional config overrides merged into defaults.
            client: Authenticated API client.
            agent_router: Router for the victim model.

        Raises:
            ValueError: If required dependencies are missing.
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
        Validate TAP parameters needed by the search algorithm.

        Raises:
            ValueError: If required keys or parameter constraints are missing.
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
        Describe the TAP pipeline: generation/search then evaluation.

        Returns:
            Pipeline step list compatible with BaseAttack._execute_pipeline.
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
