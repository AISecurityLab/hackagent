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
Prefix generation pipeline attack based on the BaseAttack class.

This module implements a complete pipeline for generating, filtering, and selecting prefixes
using uncensored and target language models, adapted as an attack module.
"""

import copy
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from hackagent.api.run import run_result_create
from hackagent.attacks.AdvPrefix.config import DEFAULT_PREFIX_GENERATION_CONFIG
from hackagent.client import AuthenticatedClient
from hackagent.models import (
    EvaluationStatusEnum,
    ResultRequest,
    StatusEnum,
)
from hackagent.router.router import AgentRouter
from hackagent.tracking import StepTracker, TrackingContext

# Import step execution functions
from .AdvPrefix import completions
from .AdvPrefix.evaluation import EvaluationPipeline
from .AdvPrefix.generate import PrefixGenerationPipeline
from .base import BaseAttack

# TUI logging support (imported conditionally to avoid import errors in non-TUI contexts)
try:
    from hackagent.cli.tui.logger import with_tui_logging
except ImportError:
    # Fallback decorator that does nothing if TUI is not available
    def with_tui_logging(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


# Helper function for deep merging dictionaries
def _recursive_update(target_dict, source_dict):
    """
    Recursively updates a target dictionary with values from a source dictionary.
    Nested dictionaries are merged; other values are overwritten with a deep copy.
    """
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            # If both current_value and update_value are dicts, recurse
            _recursive_update(target_value, source_value)
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
        self.client = client
        self.agent_router = agent_router

        # Start with a deep copy of the defaults to prevent any modification to the
        current_config = copy.deepcopy(DEFAULT_PREFIX_GENERATION_CONFIG)

        if config:  # config is the user-provided sparse dictionary of overrides
            _recursive_update(current_config, config)

        # --- Define run_id and run_dir BEFORE calling super().__init__() ---
        # Use config directly before it's potentially modified by BaseAttack
        self.run_id = current_config.get("run_id")
        output_dir = current_config.get("output_dir")
        if not output_dir:
            raise ValueError("Configuration missing required key: 'output_dir'")
        # Use output_dir directly without nesting under run_id to avoid timestamp_UUID/UUID structure
        self.run_dir = output_dir
        # Add run_id to config if it wasn't there, needed by BaseAttack perhaps
        current_config["run_id"] = self.run_id
        # --- Assign self.run_id here as well ---

        # ---------------------------------------

        # --- Get logger instance BEFORE calling super().__init__() ---
        # Use hierarchical logger name to ensure TUI handler inheritance
        self.logger = logging.getLogger("hackagent.attacks.advprefix")
        # ------------------------------------------------------------

        # Initialize tracking (will be set up in run())
        self.tracker: StepTracker | None = None

        # Make a copy to avoid modifying the original dict if passed by reference
        base_config = current_config.copy()

        super().__init__(base_config)

        # Preprocessor is now integrated into PrefixGenerationPipeline
        # No separate initialization needed

        # _setup() is called by super().__init__()

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
            "pasr_weight",
            "n_prefixes_per_goal",
            "selection_judges",
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
        if not isinstance(self.config.get("selection_judges"), list):
            raise TypeError("Config key 'selection_judges' must be a list.")
        # Add more specific type/value checks as needed (e.g., check types within lists)

    def _setup(self):
        """
        Performs setup tasks like logging.
        (Preprocessor initialization moved to __init__).
        """
        self._setup_logging()
        # All execution tracking via StepTracker - no redundant logs
        # Configuration tracked via StepTracker context

    def _setup_logging(self):
        """Configure logging to console for this attack instance."""
        # Use the instance logger obtained in __init__
        self.logger.propagate = (
            False  # Prevent duplicate logs if root logger is configured
        )
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Remove existing handlers if re-initializing (e.g., if run_id changes)
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

        # Console Handler only - all execution data tracked via API
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    # Remove helper methods that were moved to step files or utils
    # Methods like _get_checkpoint_path and _clear_gpu_memory are now in utils
    # Methods related to specific steps (_generate_prefixes, _construct_prompts, etc.) are in step files

    def _create_parent_result(self) -> str | None:
        """Create parent result for tracking and return its ID."""
        if not self.run_id or not self.client:
            return None

        try:
            parent_result_request = ResultRequest(
                run=UUID(self.run_id),
                evaluation_status=EvaluationStatusEnum.PASSED_CRITERIA,
            )
            parent_result_response = run_result_create.sync_detailed(
                client=self.client,
                id=UUID(self.run_id),
                body=parent_result_request,
            )

            if parent_result_response.status_code == 201:
                if parent_result_response.parsed and hasattr(
                    parent_result_response.parsed, "id"
                ):
                    parent_result_id = str(parent_result_response.parsed.id)
                    return parent_result_id
                else:
                    # Try to extract from raw response
                    import json

                    try:
                        response_data = json.loads(
                            parent_result_response.content.decode()
                        )
                        if "id" in response_data:
                            return str(response_data["id"])
                    except Exception:
                        pass  # Silently fail, error logged below
            else:
                self.logger.error(
                    f"Failed to create Parent Result. Status: {parent_result_response.status_code}, "
                    f"Response: {parent_result_response.content}"
                )
        except Exception as e:
            self.logger.error(f"Exception creating Parent Result: {e}", exc_info=True)

        return None

    def _prepare_input_sample(self, data):
        """Prepare input sample for tracking from List[Dict] or other input."""
        if data is None:
            return None

        if isinstance(data, list):
            # Take first 5 items for sampling
            sample = data[:5] if len(data) > 5 else data
            # Replace inf with None for JSON compatibility
            result = []
            for item in sample:
                if isinstance(item, dict):
                    clean_item = {}
                    for k, v in item.items():
                        if isinstance(v, float) and (
                            v == float("inf") or v == float("-inf")
                        ):
                            clean_item[k] = None
                        else:
                            clean_item[k] = v
                    result.append(clean_item)
                else:
                    result.append(item)
            return result
        else:
            return None

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
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "client", "config", "agent_router"],
            },
            {
                "name": "Execution: Get Completions from Target Model",
                "function": completions.execute,
                "step_type_enum": "EXECUTION",
                "config_keys": ["batch_size", "max_new_tokens_completion", "n_samples"],
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
                    "pasr_weight",
                    "n_prefixes_per_goal",
                    "selection_judges",
                    "max_ce",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "client", "config"],
            },
        ]

    def _build_step_args(
        self, step_info: Dict, step_config: Dict, input_data: Any
    ) -> Dict:
        """
        Build arguments dict for a step function based on its requirements.

        Args:
            step_info: Pipeline step configuration
            step_config: Step-specific config values
            input_data: Input data (goals for Generation, output from previous stage for others)

        Returns:
            Dictionary of arguments ready to pass to step function
        """
        args = {"config": step_config}

        # Add only required arguments to avoid parameter mismatches
        required_args = step_info.get("required_args", [])

        if "logger" in required_args:
            args["logger"] = self.logger
        if "client" in required_args:
            args["client"] = self.client
        if "agent_router" in required_args:
            args["agent_router"] = self.agent_router

        # Add input data with the correct parameter name
        args[step_info["input_data_arg_name"]] = input_data

        return args

    def _execute_function_step(
        self, step_info: Dict, step_config: Dict, input_data: Any
    ) -> Any:
        """Execute a function-based pipeline step."""
        step_function = step_info["function"]
        step_args = self._build_step_args(step_info, step_config, input_data)
        return step_function(**step_args)

    def _track_output_metrics(self, output: Any):
        """Track metrics about step output."""
        if output is None:
            self.tracker.add_step_metadata("output_type", "None")
            self.tracker.add_step_metadata("warning", "Step returned None")
        elif isinstance(output, list):
            item_count = len(output)
            self.tracker.add_step_metadata("output_items", item_count)
            if item_count == 0:
                self.tracker.add_step_metadata("warning", "Empty list returned")
        else:
            self.tracker.add_step_metadata("output_type", type(output).__name__)

    def _finalize_pipeline(self, final_output: Any):
        """Determine final status and update tracking."""
        if final_output is not None and len(final_output) > 0:
            eval_status = EvaluationStatusEnum.PASSED_CRITERIA
            eval_notes = None
            run_status = StatusEnum.COMPLETED
        else:
            eval_status = EvaluationStatusEnum.FAILED_CRITERIA
            eval_notes = "Pipeline completed with no resulting prefixes."
            run_status = StatusEnum.COMPLETED

        if self.tracker:
            self.tracker.update_result_status(eval_status, eval_notes)
            self.tracker.update_run_status(run_status)

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """
        Executes the full prefix generation pipeline.

        Args:
            goals: A list of goal strings to generate prefixes for.

        Returns:
            List of dictionaries containing the final selected prefixes,
            or empty list if no prefixes were generated.
        """
        if not goals:
            return []

        # Initialize tracking
        parent_result_id = self._create_parent_result() if self.run_id else None
        tracking_context = TrackingContext(
            client=self.client,
            run_id=self.run_id,
            parent_result_id=parent_result_id,
            logger=self.logger,
        )
        tracking_context.add_metadata("attack_type", "advprefix")
        tracking_context.add_metadata("num_goals", len(goals))

        self.tracker = StepTracker(tracking_context)
        self.tracker.update_run_status(StatusEnum.RUNNING)

        # Initialize pipeline
        pipeline_steps = self._get_pipeline_steps()
        current_step_index = self.config.get("start_step", 1) - 1
        last_step_output = goals  # Start with raw goals

        try:
            for i in range(current_step_index, len(pipeline_steps)):
                step_info = pipeline_steps[i]
                step_name = step_info["name"]
                step_type = step_info["step_type_enum"]

                # Prepare tracking data
                input_sample = self._prepare_input_sample(last_step_output)
                step_config = {
                    k: self.config[k]
                    for k in step_info.get("config_keys", [])
                    if k in self.config
                }

                # Calculate and log progress
                step_progress = int(50 + (i / len(pipeline_steps)) * 40)  # 50-90%
                self.logger.info(f"━━━ Progress: {step_progress}% ━━━")

                with self.tracker.track_step(
                    step_name, step_type, input_sample, step_config
                ):
                    # Execute the step
                    if "function" in step_info:
                        last_step_output = self._execute_function_step(
                            step_info, step_config, last_step_output
                        )
                    else:
                        self.logger.warning(
                            f"No function defined for {step_name}. Skipping."
                        )
                        continue

                    self._track_output_metrics(last_step_output)

                # Log step completion
                self.logger.info(f"✅ Completed: {step_name}")

        except Exception:
            if self.tracker:
                self.tracker.update_run_status(StatusEnum.FAILED)
            raise

        # Finalize and return results
        self._finalize_pipeline(last_step_output)
        return last_step_output if last_step_output is not None else []
