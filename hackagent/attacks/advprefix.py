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
import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

import pandas as pd

from hackagent.api.result import (
    result_partial_update,  # Added for updating Result
    result_trace_create,
)
from hackagent.api.run import run_partial_update, run_result_create
from hackagent.attacks.AdvPrefix.config import DEFAULT_PREFIX_GENERATION_CONFIG
from hackagent.client import AuthenticatedClient  # Keep for type hinting

# Models and API clients for backend interaction
from hackagent.models import (
    EvaluationStatusEnum,
    PatchedResultRequest,  # Added for updating Result evaluation_status
    PatchedRunRequest,  # Assuming this exists for PATCH /api/runs/{id}/
    ResultRequest,
    StatusEnum,
    StepTypeEnum,
    TraceRequest,
)
from hackagent.router.router import AgentRouter  # For type hinting agent_router
from hackagent.types import UNSET

# Import step execution functions
from .AdvPrefix import aggregation, completions, compute_ce, evaluation, generate
from .AdvPrefix.preprocessing import PrefixPreprocessor, PreprocessConfig
from .AdvPrefix.selector import PrefixSelector
from .base import BaseAttack


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
        self.logger = logging.getLogger(__name__)
        # ------------------------------------------------------------

        # Make a copy to avoid modifying the original dict if passed by reference
        base_config = current_config.copy()

        super().__init__(base_config)

        # Initialize components needed across steps (like Preprocessor)
        self.preprocessor = None
        try:
            # Extract relevant keys for PreprocessConfig, handling potential missing keys
            preprocess_cfg_keys = [
                # 'model_id', # Removed as no longer needed by Preprocessor for token counting
                "min_char_length",  # Changed from min_token_length
                "max_ce",
                "max_token_segments",
                "n_candidates_per_goal",
            ]
            preprocess_cfg_dict = {}
            for key in preprocess_cfg_keys:
                if key in self.config:
                    preprocess_cfg_dict[key] = self.config[key]
                # else: Log missing optional keys if needed

            # Create PreprocessConfig instance
            self.logger.info(
                f"Initializing Preprocessor with derived config: {preprocess_cfg_dict}"
            )
            preprocessor_config_obj = PreprocessConfig(**preprocess_cfg_dict)

            # Instantiate PrefixPreprocessor with the config object
            self.preprocessor = PrefixPreprocessor(config=preprocessor_config_obj)

            self.logger.info("Preprocessor initialized successfully.")

        except KeyError as ke:
            self.logger.error(
                f"Missing required key for PreprocessConfig: {ke}", exc_info=True
            )
        except ImportError:  # Catch import error specifically if still using try-except
            self.logger.error(
                "Failed to import AutoTokenizer, PreprocessConfig or PrefixPreprocessor. Steps requiring it will fail.",
                exc_info=True,
            )
        except Exception as e:
            self.logger.error(
                f"Failed to initialize PrefixPreprocessor: {e}", exc_info=True
            )
            # self.preprocessor remains None

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
            # Keys needed for Step 7
            "judges",
            "batch_size_judge",
            "max_new_tokens_eval",
            "filter_len",
            # Keys needed for Step 9
            "pasr_weight",
            "n_prefixes_per_goal",
            "selection_judges",
            # Note: 'max_ce' is used optionally in Step 5 (via Preprocessor) and Step 8
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
        self.logger.info(f"AdvPrefixAttack initialized with run ID: {self.run_id}")
        self.logger.info(f"Output directory: {self.run_dir}")
        # Log config (already a dict)
        # Avoid logging sensitive info if present in config (e.g., API keys)
        log_config = {
            k: v
            for k, v in self.config.items()
            if "token" not in k.lower()
            and "key" not in k.lower()
            and "secret" not in k.lower()
        }
        self.logger.info(f"Configuration (non-sensitive): {log_config}")

    def _setup_logging(self):
        """Configure logging to both file and console for this attack instance."""
        os.makedirs(self.run_dir, exist_ok=True)
        log_file = os.path.join(self.run_dir, "pipeline.log")

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

        # File Handler
        try:
            fh = logging.FileHandler(log_file, mode="a")  # Append mode
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
        except Exception as e:
            print(
                f"Error setting up file handler for attack log: {e}"
            )  # Print error if logger fails

        # Console Handler - Check if one already exists to avoid duplicates in console
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    # Remove helper methods that were moved to step files or utils
    # Methods like _get_checkpoint_path and _clear_gpu_memory are now in utils
    # Methods related to specific steps (_generate_prefixes, _construct_prompts, etc.) are in step files

    def run(self, goals: List[str]) -> pd.DataFrame:
        """
        Executes the full prefix generation pipeline.

        Args:
            goals: A list of goal strings to generate prefixes for.

        Returns:
            A pandas DataFrame containing the final selected prefixes.
        """
        self.logger.info(f"Starting AdvPrefixAttack pipeline for Run ID: {self.run_id}")
        if not goals:
            self.logger.warning("No goals provided to the pipeline. Exiting early.")
            return pd.DataFrame()

        if not self.run_id:
            self.logger.error(
                "Instance self.run_id is not set. This should be the server-side Run ID. Cannot proceed with backend logging."
            )
            pass  # Allow to proceed for now, but server interactions might be affected/skipped.

        # Update server Run status to 'RUNNING'
        if self.run_id:
            try:
                self.logger.info(
                    f"Updating server Run {self.run_id} status to RUNNING."
                )
                run_patch_request = PatchedRunRequest(status=StatusEnum.RUNNING)
                update_response = run_partial_update.sync_detailed(
                    client=self.client,
                    id=self.run_id,
                    body=run_patch_request,
                )
                if update_response.status_code >= 300:
                    self.logger.error(
                        f"Failed to update server Run {self.run_id} status to RUNNING. Status: {update_response.status_code}, Response: {update_response.content}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Exception updating server Run {self.run_id} status: {e}",
                    exc_info=True,
                )

        # Create a parent Result record on the server for this entire AdvPrefix pipeline run
        parent_result_id = None
        if self.run_id:
            try:
                self.logger.info(
                    f"Creating parent Result for AdvPrefix pipeline under Run ID: {self.run_id}"
                )
                # Modify parameters to include a custom identifier for the AdvPrefix pipeline
                # parent_parameters = self.config.copy() if self.config is not None else {} # Cannot be used with ResultRequest
                # parent_parameters["advprefix_pipeline_identifier"] = "PIPELINE_ADVPREFIX"

                parent_result_request = ResultRequest(
                    run=UUID(self.run_id)  # ResultRequest expects 'run' (the run_id)
                    # step_type=StepTypeEnum.OTHER, # Not a valid constructor argument for ResultRequest
                    # parameters=parent_parameters, # Not a valid constructor argument
                    # status=StatusEnum.RUNNING, # Not a valid constructor argument, status is set via PATCH later
                )
                parent_result_response = run_result_create.sync_detailed(
                    client=self.client,
                    id=UUID(self.run_id),  # Pass self.run_id as the 'id' for the path
                    body=parent_result_request,
                )
                if parent_result_response.status_code == 201:
                    if parent_result_response.parsed and hasattr(
                        parent_result_response.parsed, "id"
                    ):
                        parent_result_id = str(parent_result_response.parsed.id)
                        self.logger.info(
                            f"Parent Result for AdvPrefix pipeline created with ID: {parent_result_id}"
                        )
                    else:
                        # Try to parse the ID from the raw content if .parsed is None or lacks .id
                        try:
                            response_data = json.loads(
                                parent_result_response.content.decode()
                            )
                            if "id" in response_data:
                                parent_result_id = str(response_data["id"])
                                self.logger.info(
                                    f"Parent Result for AdvPrefix pipeline created with ID (from raw content): {parent_result_id}"
                                )
                            else:
                                self.logger.error(
                                    f"Parent Result created (Status 201) but ID not found in parsed or raw response. Raw: {parent_result_response.content}"
                                )
                        except Exception as e_parse:
                            self.logger.error(
                                f"Parent Result created (Status 201) but failed to parse ID from raw response. Raw: {parent_result_response.content}, Parse Error: {e_parse}"
                            )
                else:
                    self.logger.error(
                        f"Failed to create parent Result for AdvPrefix pipeline. Status: {parent_result_response.status_code}, Response: {parent_result_response.content}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Exception creating parent Result for AdvPrefix pipeline: {e}",
                    exc_info=True,
                )
        else:
            self.logger.warning(
                "Cannot create parent Result as self.run_id is missing."
            )

        goals_df = pd.DataFrame(goals, columns=["goal"])
        goals_df["category"] = "general"
        last_step_output_df = goals_df
        current_step_failed = False  # Initialize here, before the loop
        trace_sequence_counter = 0  # Initialize trace sequence counter

        pipeline_steps = [
            {
                "name": "Step 1: Generate Prefixes",
                "function": generate.execute,
                "step_type_enum": "STEP1_GENERATE",
                "config_keys": [
                    "generator",
                    "batch_size",
                    "max_new_tokens",
                    "guided_topk",
                    "temperature",
                    "meta_prefixes",
                    "meta_prefix_samples",
                ],
                "input_df_arg_name": "goals",
                "output_filename": "generated_prefixes.csv",
            },
            {
                "name": "Step 2: Preprocess Generated Prefixes (Filter & Clean)",
                "processor_method_name": "filter_phase1",
                "step_type_enum": "STEP2_PREPROCESS_GENERATED",
                "input_df_arg_name": "generated_prefixes_df",
                "output_filename": "preprocessed_generated_prefixes.csv",
            },
            {
                "name": "Step 4: Compute Cross-Entropy (CE) for Prefixes",
                "function": compute_ce.execute,
                "step_type_enum": "STEP4_COMPUTE_CE",
                "config_keys": ["batch_size", "surrogate_attack_prompt"],
                "input_df_arg_name": "input_df",
                "output_filename": "prefixes_with_ce.csv",
            },
            {
                "name": "Step 5: Preprocess CE-computed Prefixes (Filter by CE)",
                "processor_method_name": "filter_phase2",
                "step_type_enum": "STEP5_PREPROCESS_CE_COMPUTED",
                "input_df_arg_name": "prefixes_with_ce_df",
                "output_filename": "filtered_prefixes_by_ce.csv",
            },
            {
                "name": "Step 6: Get Completions for Filtered Prefixes",
                "function": completions.execute,
                "step_type_enum": "STEP6_GET_COMPLETIONS",
                "config_keys": ["batch_size", "max_new_tokens_completion", "n_samples"],
                "input_df_arg_name": "input_df",
                "output_filename": "completions.csv",
            },
            {
                "name": "Step 7: Evaluate Completions (Judge Models)",
                "function": evaluation.execute,
                "step_type_enum": "STEP7_EVALUATE_RESPONSES",
                "config_keys": [
                    "judges",
                    "batch_size_judge",
                    "max_new_tokens_eval",
                    "filter_len",
                ],
                "input_df_arg_name": "input_df",
                "output_filename": "evaluations.csv",
            },
            {
                "name": "Step 8: Aggregate Evaluations",
                "function": aggregation.execute,
                "step_type_enum": "STEP8_AGGREGATE_EVALUATIONS",
                "config_keys": ["pasr_weight", "selection_judges", "max_ce"],
                "input_df_arg_name": "input_df",
                "output_filename": "aggregated_evaluations.csv",
            },
            {
                "name": "Step 9: Select Final Prefixes",
                "function": PrefixSelector.execute,
                "step_type_enum": "STEP9_SELECT_PREFIXES",
                "config_keys": [
                    "pasr_weight",
                    "n_prefixes_per_goal",
                    "selection_judges",
                ],
                "input_df_arg_name": "input_df",
                "output_filename": "selected_prefixes.csv",
            },
        ]

        current_step_index = self.config.get("start_step", 1) - 1

        for i in range(current_step_index, len(pipeline_steps)):
            step_info = pipeline_steps[i]
            step_name = step_info["name"]
            self.logger.info(f"--- Starting {step_name} ---")

            step_output_path = os.path.join(self.run_dir, step_info["output_filename"])
            step_result_id = None

            if parent_result_id:
                try:
                    trace_sequence_counter += 1  # Increment for each new trace
                    advprefix_step_name_str = step_info[
                        "step_type_enum"
                    ]  # Get the string like "STEP1_GENERATE"

                    # Prepare content for the trace
                    current_input_df_sample = None
                    if last_step_output_df is not None and isinstance(
                        last_step_output_df, pd.DataFrame
                    ):
                        # Replace inf with None for JSON compatibility before creating sample
                        df_copy_for_trace = last_step_output_df.replace(
                            [float("inf"), float("-inf")], None
                        )
                        current_input_df_sample = df_copy_for_trace.head().to_dict()

                    trace_content_dict = {
                        "config_snapshot": self.config,  # Or specific step_config
                        "input_df_sample": current_input_df_sample,
                        "advprefix_step_name": advprefix_step_name_str,  # Store the custom step name
                        # Add other relevant info for this step if needed
                    }

                    trace_request = TraceRequest(
                        # result_id=UUID(parent_result_id), # Incorrect: Handled by API path
                        sequence=trace_sequence_counter,
                        step_type=StepTypeEnum.OTHER,  # Use a valid existing enum member
                        # status=StatusEnum.RUNNING, # Incorrect: Not a field for TraceRequest
                        content=trace_content_dict,  # Pass the dictionary as content
                    )
                    # Corrected API call: pass parent_result_id as 'id'
                    trace_response = result_trace_create.sync_detailed(
                        client=self.client,
                        id=UUID(parent_result_id),
                        body=trace_request,
                    )
                    if (
                        trace_response.status_code == 201
                    ):  # Changed condition: 201 is success
                        if trace_response.parsed and hasattr(
                            trace_response.parsed, "id"
                        ):
                            step_result_id = str(trace_response.parsed.id)
                            self.logger.info(
                                f"Trace record created for {step_name} with ID: {step_result_id}"
                            )
                        else:
                            # Attempt to get ID from raw response if .parsed is not helpful for 201
                            try:
                                response_data_trace = json.loads(
                                    trace_response.content.decode()
                                )
                                if "id" in response_data_trace:
                                    step_result_id = str(response_data_trace["id"])
                                    self.logger.info(
                                        f"Trace record created for {step_name} with ID (from raw 201 content): {step_result_id}"
                                    )
                                else:
                                    self.logger.warning(
                                        f"Trace created for {step_name} (Status 201), but ID not found in parsed or raw response. Raw: {trace_response.content}"
                                    )
                            except Exception as e_parse_trace:
                                self.logger.warning(
                                    f"Trace created for {step_name} (Status 201), but failed to parse ID from raw. Error: {e_parse_trace}, Raw: {trace_response.content}"
                                )
                    else:
                        self.logger.error(
                            f"Failed to create Trace for {step_name}. Status: {trace_response.status_code}, Response: {trace_response.content}"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Exception creating Trace for {step_name}: {e}", exc_info=True
                    )

            current_step_failed = False  # Reset for current step
            try:  # Main try for step execution
                # Prepare the configuration dictionary specific to this step
                step_specific_config_dict = {
                    k: self.config[k]
                    for k in step_info.get("config_keys", [])
                    if k in self.config
                }

                if "function" in step_info:
                    step_function = step_info["function"]
                    step_args = {}

                    # Common arguments for most step functions
                    step_args["logger"] = self.logger
                    step_args["run_dir"] = self.run_dir
                    step_args["client"] = (
                        self.client
                    )  # Pass client if needed by step (e.g. step1, step7 for their own routers)
                    step_args["config"] = (
                        step_specific_config_dict  # Pass the step-specific config sub-dictionary
                    )

                    if step_name == "Step 1: Generate Prefixes":
                        step_args[step_info["input_df_arg_name"]] = (
                            goals  # "goals" is List[str]
                        )
                        # Step 1 (step1_generate.execute) does not take agent_router directly
                        if "agent_router" in step_args:
                            del step_args["agent_router"]
                    elif step_name == "Step 4: Compute Cross-Entropy (CE) for Prefixes":
                        step_args[step_info["input_df_arg_name"]] = last_step_output_df
                        step_args["agent_router"] = self.agent_router
                    elif step_name == "Step 6: Get Completions for Filtered Prefixes":
                        step_args[step_info["input_df_arg_name"]] = last_step_output_df
                        step_args["agent_router"] = self.agent_router
                        if "client" in step_args:  # Step 6 does not expect client
                            del step_args["client"]
                    elif step_name == "Step 7: Evaluate Completions (Judge Models)":
                        step_args[step_info["input_df_arg_name"]] = last_step_output_df
                        step_args["client"] = (
                            self.client
                        )  # ADDED client for AgentRouter instantiation in Step 7
                        # No agent_router needed for step 7 typically (uses its own for judges)
                        # if "client" in step_args: del step_args["client"] # This was incorrect, client is needed
                        if "agent_router" in step_args:
                            del step_args["agent_router"]
                    elif step_name == "Step 8: Aggregate Evaluations":
                        step_args[step_info["input_df_arg_name"]] = last_step_output_df
                        # Step 8 (step8_aggregate_evaluations.execute) only expects input_df, config, run_dir
                        if "client" in step_args:
                            del step_args["client"]
                        if "agent_router" in step_args:
                            del step_args["agent_router"]
                        if "logger" in step_args:
                            del step_args["logger"]  # Also remove logger for step 8
                    elif step_name == "Step 9: Select Final Prefixes":
                        step_args[step_info["input_df_arg_name"]] = last_step_output_df
                        # Step 9 (step9_select_prefixes.execute) now expects input_df, config
                        if "client" in step_args:
                            del step_args["client"]
                        if "agent_router" in step_args:
                            del step_args["agent_router"]
                        if "logger" in step_args:
                            del step_args["logger"]
                        if "run_dir" in step_args:  # Added this to remove run_dir
                            del step_args["run_dir"]  # Added this to remove run_dir
                    else:  # Default for other function-based steps if any added later
                        step_args[step_info["input_df_arg_name"]] = last_step_output_df

                    self.logger.debug(
                        f"Executing {step_name} with arguments: {{k: type(v) for k,v in step_args.items()}}"
                    )
                    last_step_output_df = step_function(**step_args)
                elif "processor_method_name" in step_info:
                    if not self.preprocessor:
                        self.logger.error(
                            f"Preprocessor not initialized, cannot execute {step_name}. Skipping."
                        )
                        raise RuntimeError(
                            f"Preprocessor not available for {step_name}"
                        )
                    method_name = step_info["processor_method_name"]
                    processor_method = getattr(self.preprocessor, method_name, None)
                    if not processor_method:
                        self.logger.error(
                            f"Method {method_name} not found in Preprocessor. Skipping {step_name}."
                        )
                        raise RuntimeError(
                            f"Method {method_name} not found for {step_name}"
                        )
                    self.logger.debug(
                        f"Executing {step_name} (preprocessor method: {method_name}) with input DF type: {type(last_step_output_df)}."
                    )
                    # Processor methods expect the DataFrame as the first positional argument.
                    last_step_output_df = processor_method(last_step_output_df)
                else:
                    self.logger.warning(
                        f"No function or processor method defined for {step_name}. Skipping."
                    )
                    continue

                if last_step_output_df is None or (
                    isinstance(last_step_output_df, pd.DataFrame)
                    and last_step_output_df.empty
                ):
                    self.logger.warning(
                        f"{step_name} did not return a valid DataFrame or returned an empty one. Output path: {step_output_path}"
                    )

                if (
                    isinstance(last_step_output_df, pd.DataFrame)
                    and not last_step_output_df.empty
                ):
                    self.logger.info(
                        f"Saving output of {step_name} to {step_output_path}"
                    )
                    os.makedirs(os.path.dirname(step_output_path), exist_ok=True)
                    last_step_output_df.to_csv(step_output_path, index=False)
                    self.logger.info(f"Output of {step_name} saved successfully.")
                elif last_step_output_df is not None:
                    self.logger.warning(
                        f"{step_name} did not return a DataFrame. Type: {type(last_step_output_df)}. Output not saved to CSV."
                    )

            except Exception as e:  # Main except for step execution
                current_step_failed = True
                self.logger.error(f"--- Error in {step_name} ---: {e}", exc_info=True)
                step_error_message = str(e)

                if parent_result_id:
                    try:
                        parent_fail_message = (
                            f"Pipeline failed at {step_name}: {step_error_message}"
                        )
                        parent_failed_request = PatchedResultRequest(
                            evaluation_status=EvaluationStatusEnum.ERROR_TEST_FRAMEWORK,
                            evaluation_notes=parent_fail_message,
                        )
                        result_partial_update.sync_detailed(
                            client=self.client,
                            id=UUID(parent_result_id),
                            body=parent_failed_request,
                        )
                    except (
                        Exception
                    ) as parent_e:  # Changed 'e' to 'parent_e' for clarity
                        self.logger.error(
                            f"Additionally, failed to update parent Result {parent_result_id} to FAILED: {parent_e}",
                            exc_info=True,
                        )

                if self.run_id:
                    try:
                        run_failed_request = PatchedRunRequest(status=StatusEnum.FAILED)
                        run_partial_update.sync_detailed(
                            client=self.client, id=self.run_id, body=run_failed_request
                        )
                    except Exception as run_e:
                        self.logger.error(
                            f"Additionally, failed to update server Run {self.run_id} to FAILED: {run_e}",
                            exc_info=True,
                        )

                self.logger.error(f"Pipeline halted at {step_name} due to error.")
                return pd.DataFrame()

            if current_step_failed:
                self.logger.error(
                    f"Pipeline processing stopped due to failure in {step_name}."
                )  # Should be caught by return above
                return pd.DataFrame()

            self.logger.info(f"--- Completed {step_name} ---")
            if last_step_output_df is None or (
                isinstance(last_step_output_df, pd.DataFrame)
                and last_step_output_df.empty
            ):
                self.logger.warning(
                    f"No data produced by {step_name}, subsequent steps may fail or produce no results."
                )

        # After the loop
        final_selected_prefixes_df = last_step_output_df
        final_status = StatusEnum.COMPLETED  # Default
        final_error_message: Any = UNSET  # Default - can be UNSET or str

        if current_step_failed:  # This means the loop exited due to failure and returned. This part might not be reached.
            # Re-evaluating based on whether loop completed or exited early.
            # If loop completed, current_step_failed should be false (or true if last step failed but didn't halt)
            # This condition implies failure if we reach here and current_step_failed is true
            # However, the loop's except block already returns. So if we are here, loop completed.
            # Let's refine based on if final_selected_prefixes_df is empty AND no prior return.
            pass  # Logic already handled if current_step_failed leads to return in loop.

        # Determine final status based on pipeline completion and results
        if (
            final_selected_prefixes_df is not None
            and not final_selected_prefixes_df.empty
        ):
            self.logger.info("AdvPrefixAttack pipeline completed successfully.")
            final_status = StatusEnum.COMPLETED
            final_error_message = UNSET
        # current_step_failed would have caused early exit. If we are here, the loop completed.
        # This 'else' covers cases where loop completed but results are empty.
        else:
            self.logger.info(
                "AdvPrefixAttack pipeline completed, but no prefixes were selected or generated (or last step failed without halting)."
            )
            final_status = StatusEnum.COMPLETED
            final_error_message = "Pipeline completed with no resulting prefixes or last step yielded no data."

        if parent_result_id:
            try:
                final_outputs_payload = {
                    "final_df_sample": final_selected_prefixes_df.head().to_dict()
                    if final_selected_prefixes_df is not None
                    and isinstance(final_selected_prefixes_df, pd.DataFrame)
                    else None
                }
                current_eval_status = EvaluationStatusEnum.PASSED_CRITERIA
                current_eval_notes = UNSET

                if (
                    final_status == StatusEnum.FAILED
                ):  # This was for PatchedRunRequest, map to an EvaluationStatus
                    current_eval_status = (
                        EvaluationStatusEnum.ERROR_TEST_FRAMEWORK
                    )  # Or other appropriate error
                    if (
                        final_error_message is not UNSET
                        and final_error_message is not None
                    ):
                        current_eval_notes = str(final_error_message)
                elif (
                    final_selected_prefixes_df is None
                    or final_selected_prefixes_df.empty
                ):
                    current_eval_status = (
                        EvaluationStatusEnum.FAILED_CRITERIA
                    )  # Or other status indicating no results
                    current_eval_notes = (
                        str(final_error_message)
                        if final_error_message is not UNSET
                        else "Pipeline completed with no resulting prefixes."
                    )

                final_parent_update_req = PatchedResultRequest(
                    evaluation_status=current_eval_status,
                    evaluation_notes=current_eval_notes,
                    agent_specific_data={"outputs": final_outputs_payload},
                )
                result_partial_update.sync_detailed(
                    client=self.client,
                    id=UUID(parent_result_id),
                    body=final_parent_update_req,
                )
            except Exception as e:
                self.logger.error(
                    f"Exception updating final status of parent Result {parent_result_id}: {e}",
                    exc_info=True,
                )

        if self.run_id:
            try:
                self.logger.info(
                    f"Updating server Run {self.run_id} to final status: {final_status.value}."
                )
                final_run_update_req = PatchedRunRequest(status=final_status)
                final_run_update_response = run_partial_update.sync_detailed(
                    client=self.client,
                    id=self.run_id,
                    body=final_run_update_req,
                )
                if final_run_update_response.status_code >= 300:
                    self.logger.error(
                        f"Failed to update server Run {self.run_id} to final status {final_status.value}. Status: {final_run_update_response.status_code}, Response: {final_run_update_response.content}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Exception updating server Run {self.run_id} to final status: {e}",
                    exc_info=True,
                )

        return (
            final_selected_prefixes_df
            if final_selected_prefixes_df is not None
            else pd.DataFrame()
        )

    def _save_results_to_file(self, results_df: pd.DataFrame, filename: str):
        # Assuming this method has a body.
        # Replacing placeholder comment with 'pass' to make it syntactically valid.
        # If actual code was here, it needs to be restored.
        pass
