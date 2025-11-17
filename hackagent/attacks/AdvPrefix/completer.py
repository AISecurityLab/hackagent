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
Completion handling module for AdvPrefix attacks.

This module provides utilities and interfaces for handling model completions
throughout the AdvPrefix attack pipeline. It abstracts the interaction with
different language model backends and provides consistent completion handling
across various stages of the attack process.

The module provides functionality for:
- Model completion generation and collection
- Response processing and normalization
- Error handling and retry logic for model interactions
- Batched completion processing for efficiency
- Integration with different model backends and APIs
- Completion validation and quality checking

This module ensures consistent and reliable model interaction across
the AdvPrefix attack pipeline components.
"""

import pandas as pd
import os
import logging
import uuid
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
    SpinnerColumn,
)
from hackagent.client import AuthenticatedClient
from hackagent.router.router import AgentRouter, AgentTypeEnum


@dataclass
class CompletionConfig:
    """Configuration for generating completions using an Agent via AgentRouter.

    Attributes:
        agent_name: A descriptive name for this agent configuration.
        agent_type: The type of agent (e.g., ADK, LiteLLM) to use.
        organization_id: The organization ID for backend agent registration.
        model_id: A general model identifier (e.g., "claude-2", "gpt-4").
        agent_endpoint: The API endpoint for the agent service.
        agent_metadata: Optional dictionary for agent-specific metadata.
                          For ADK: e.g., `{'adk_app_name': 'my_app'}`.
                          For LiteLLM: e.g., `{'name': 'litellm_model_string', 'api_key': 'ENV_VAR_NAME'}`.
        batch_size: The number of requests to batch if supported by the underlying adapter (currently informational).
        max_new_tokens: The maximum number of new tokens to generate for each completion.
        temperature: The temperature setting for token generation.
        n_samples: The number of completion samples to generate for each input prefix.
        surrogate_attack_prompt: An optional prompt to prepend for surrogate attacks, typically used with LiteLLM agents.
        request_timeout: The timeout in seconds for each completion request.
    """

    agent_name: str
    agent_type: AgentTypeEnum
    organization_id: int
    model_id: str
    agent_endpoint: str
    agent_metadata: Optional[Dict[str, Any]] = None
    batch_size: int = 1
    max_new_tokens: int = 256
    temperature: float = 1.0
    n_samples: int = 25
    surrogate_attack_prompt: str = ""
    request_timeout: int = 120


class PrefixCompleter:
    """
    Manages text completion generation for adversarial prefixes using target language models.

    This class provides a comprehensive interface for generating completions from
    adversarial prefixes using various model types through the AgentRouter framework.
    It handles the complete workflow from prefix expansion to completion generation
    and result consolidation.

    The completer supports multiple agent types (ADK, LiteLLM) and provides
    robust error handling, progress tracking, and comprehensive result logging.
    All interactions are managed through the AgentRouter to ensure consistent
    API usage across different model backends.

    Key Features:
    - Automatic prefix expansion for multiple samples per prefix
    - Configurable completion parameters (temperature, max tokens, etc.)
    - Comprehensive error handling and recovery
    - Progress tracking for long-running operations
    - Detailed result metadata collection
    - Support for surrogate attack prompts

    Attributes:
        client: AuthenticatedClient for API communications
        config: CompletionConfig with all completion parameters
        logger: Logger instance for operation tracking
        api_key: API key for LiteLLM models (if applicable)
        agent_router: AgentRouter instance for model interactions
        agent_registration_key: Registration key for the configured agent
    """

    def __init__(self, client: AuthenticatedClient, config: CompletionConfig):
        """
        Initialize the PrefixCompleter with client and configuration.

        Sets up the AgentRouter, handles API key configuration for LiteLLM models,
        and prepares the completer for generating completions. The initialization
        process includes agent registration and adapter configuration.

        Args:
            client: AuthenticatedClient instance for API communication with
                the HackAgent backend and target models.
            config: CompletionConfig object containing all completion parameters
                including agent type, model settings, and generation parameters.

        Raises:
            RuntimeError: If the AgentRouter fails to register an agent during
                initialization, indicating configuration or connectivity issues.

        Note:
            For LiteLLM agents, API keys are automatically loaded from environment
            variables specified in the agent metadata. The initialization process
            includes comprehensive adapter configuration based on the agent type.
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.api_key: Optional[str] = None

        if (
            self.config.agent_type == AgentTypeEnum.LITELLM
            and self.config.agent_metadata
            and "api_key" in self.config.agent_metadata
        ):
            api_key_env_var = self.config.agent_metadata["api_key"]
            self.api_key = os.environ.get(api_key_env_var)
            if not self.api_key:
                self.logger.warning(
                    f"Environment variable {api_key_env_var} for LiteLLM API key not set."
                )

        adapter_op_config: Dict[str, Any] = {}
        if self.config.agent_type == AgentTypeEnum.LITELLM:
            if self.config.agent_metadata and "name" in self.config.agent_metadata:
                adapter_op_config["name"] = self.config.agent_metadata["name"]
            else:
                adapter_op_config["name"] = self.config.model_id
                self.logger.warning(
                    f"LiteLLM 'name' (model string) not found in agent_metadata, using model_id '{self.config.model_id}'. Ensure this is correct."
                )
            if self.api_key:
                adapter_op_config["api_key"] = self.api_key
            if self.config.agent_endpoint:
                adapter_op_config["endpoint"] = self.config.agent_endpoint
            adapter_op_config["max_new_tokens"] = self.config.max_new_tokens
            adapter_op_config["temperature"] = self.config.temperature

        self.agent_router = AgentRouter(
            client=self.client,
            name=self.config.agent_name,
            agent_type=self.config.agent_type,
            endpoint=self.config.agent_endpoint,
            metadata=self.config.agent_metadata,
            adapter_operational_config=adapter_op_config,
            overwrite_metadata=True,
        )

        if not self.agent_router._agent_registry:
            raise RuntimeError(
                "AgentRouter did not register any agent upon initialization."
            )
        self.agent_registration_key = list(self.agent_router._agent_registry.keys())[0]

        self.logger.info(
            f"PrefixCompleter initialized for agent '{self.config.agent_name}' "
            f"(Type: {self.config.agent_type.value}, Backend ID: {self.agent_registration_key}) "
            f"via AgentRouter."
        )

    def expand_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Expand DataFrame to create multiple samples for each adversarial prefix.

        This method prepares the input DataFrame for completion generation by
        creating multiple rows for each original prefix based on the configured
        number of samples. This allows for statistical analysis of completion
        variability and improves attack success rate estimation.

        Args:
            df: Input DataFrame containing adversarial prefixes. Each row
                represents a unique prefix to be expanded for sampling.

        Returns:
            Expanded DataFrame where each original row is duplicated n_samples
            times. New columns added:
            - sample_id: Integer identifier for each sample (0 to n_samples-1)
            - completion: Empty string placeholder for generated completions

        Note:
            Progress tracking is provided for the expansion process. The expansion
            maintains all original columns while adding sample-specific metadata.
            This structure facilitates parallel processing and result aggregation
            in downstream pipeline stages.
        """
        expanded_rows = []
        self.logger.info(
            f"Expanding DataFrame for {self.config.n_samples} samples per prefix."
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            TimeRemainingColumn(),
        ) as progress_bar:
            task = progress_bar.add_task("[cyan]Expanding samples...", total=len(df))
            for _, row in df.iterrows():
                for sample_id in range(self.config.n_samples):
                    expanded_row = row.to_dict()
                    expanded_row["sample_id"] = sample_id
                    expanded_row["completion"] = ""
                    expanded_rows.append(expanded_row)
                progress_bar.update(task, advance=1)

        return pd.DataFrame(expanded_rows)

    def get_completions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate completions for all adversarial prefixes in the input DataFrame.

        This method orchestrates the complete completion generation process,
        from DataFrame expansion through individual completion requests to
        result consolidation. It handles different agent types, manages
        session contexts for ADK agents, and provides comprehensive error
        handling and result logging.

        The completion process:
        1. Expand DataFrame for multiple samples per prefix
        2. Set up agent-specific session context (if required)
        3. Generate completions for each prefix-sample combination
        4. Collect comprehensive result metadata
        5. Return consolidated results with detailed logging information

        Args:
            df: DataFrame containing adversarial prefixes to complete. Must
                include `'goal'` and either `'prefix'` or `'target'` columns.
                Additional columns are preserved in the output.

        Returns:
            Expanded DataFrame with generated completions and metadata:
            - generated_text_only: The actual completion text from the model
            - request_payload: Request data sent to the agent
            - response_status_code: HTTP status code from the response
            - response_headers: Response headers from the agent interaction
            - response_body_raw: Raw response body for debugging
            - adk_events_list: ADK-specific event data (for ADK agents)
            - completion_error_message: Error messages if completion failed

        Raises:
            ValueError: If the input DataFrame is missing required columns
                (`'goal'` and `'prefix'`/`'target'`).

        Note:
            Progress tracking is provided for completion generation. For ADK
            agents, unique session and user IDs are generated to ensure
            proper session isolation. All errors are captured gracefully
            to allow batch processing to continue.
        """
        self.logger.info(
            f"Starting completions for {len(df)} unique prefixes with {self.config.n_samples} samples each."
        )
        expanded_df = self.expand_dataframe(df)

        if "target" in expanded_df.columns:
            expanded_df.rename(columns={"target": "prefix"}, inplace=True)
            self.logger.debug("Renamed 'target' column to 'prefix' if it existed.")
        if "target_ce_loss" in expanded_df.columns:
            expanded_df.rename(columns={"target_ce_loss": "prefix_nll"}, inplace=True)
            self.logger.debug(
                "Renamed 'target_ce_loss' column to 'prefix_nll' if it existed."
            )

        if "prefix" not in expanded_df.columns or "goal" not in expanded_df.columns:
            raise ValueError(
                "Input DataFrame must contain 'prefix' and 'goal' columns after potential renaming."
            )

        adk_session_id: Optional[str] = None
        adk_user_id: Optional[str] = None
        if self.config.agent_type == AgentTypeEnum.GOOGLE_ADK:
            adk_session_id = str(uuid.uuid4())
            adk_user_id = f"completer_user_{adk_session_id[:8]}"
            self.logger.info(
                f"Generated ADK session_id: {adk_session_id} and user_id: {adk_user_id} for ADK requests."
            )

        detailed_completion_results: List[Dict] = []
        self.logger.info(
            f"Executing {len(expanded_df)} completion requests sequentially via AgentRouter."
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            TimeRemainingColumn(),
        ) as progress_bar:
            task_progress = progress_bar.add_task(
                "[cyan]Getting completions...", total=len(expanded_df)
            )
            for index, row in expanded_df.iterrows():
                goal = row["goal"]
                prefix_text = row["prefix"]
                try:
                    result = self._execute_completion_request(
                        goal, prefix_text, index, adk_session_id, adk_user_id
                    )
                    detailed_completion_results.append(result)
                except Exception as e:
                    self.logger.error(
                        f"Unhandled exception during completion request for original index {index}, prefix '{prefix_text[:50]}...': {e}",
                        exc_info=True,
                    )
                    detailed_completion_results.append(
                        {
                            "generated_text": f"[ERROR: Unhandled Exception in get_completions loop - {type(e).__name__}]",
                            "request_payload": None,
                            "response_status_code": None,
                            "response_headers": None,
                            "response_body_raw": None,
                            "adk_events_list": None,
                            "error_message": str(e),
                        }
                    )
                progress_bar.update(task_progress, advance=1)

        self.logger.info("All completion requests processed.")

        if len(detailed_completion_results) == len(expanded_df):
            expanded_df["generated_text_only"] = [
                res.get("generated_text") for res in detailed_completion_results
            ]
            expanded_df["request_payload"] = [
                res.get("request_payload") for res in detailed_completion_results
            ]
            expanded_df["response_status_code"] = [
                res.get("response_status_code") for res in detailed_completion_results
            ]
            expanded_df["response_headers"] = [
                res.get("response_headers") for res in detailed_completion_results
            ]
            expanded_df["response_body_raw"] = [
                res.get("response_body_raw") for res in detailed_completion_results
            ]
            expanded_df["adk_events_list"] = [
                res.get("adk_events_list") for res in detailed_completion_results
            ]
            expanded_df["completion_error_message"] = [
                res.get("error_message") for res in detailed_completion_results
            ]
        else:
            self.logger.error(
                f"Mismatch between number of detailed_completion_results ({len(detailed_completion_results)}) and DataFrame rows ({len(expanded_df)}). Padding with error indicators."
            )
            num_missing = len(expanded_df) - len(detailed_completion_results)
            error_padding_entry = {
                "generated_text": "[ERROR: Result-Row Length Mismatch]",
                "request_payload": None,
                "response_status_code": None,
                "response_headers": None,
                "response_body_raw": None,
                "adk_events_list": None,
                "error_message": "Result-Row Length Mismatch during DataFrame population",
            }
            padded_results = (
                detailed_completion_results + [error_padding_entry] * num_missing
            )

            expanded_df["generated_text_only"] = [
                res.get("generated_text") for res in padded_results
            ]
            expanded_df["request_payload"] = [
                res.get("request_payload") for res in padded_results
            ]
            expanded_df["response_status_code"] = [
                res.get("response_status_code") for res in padded_results
            ]
            expanded_df["response_headers"] = [
                res.get("response_headers") for res in padded_results
            ]
            expanded_df["response_body_raw"] = [
                res.get("response_body_raw") for res in padded_results
            ]
            expanded_df["adk_events_list"] = [
                res.get("adk_events_list") for res in padded_results
            ]
            expanded_df["completion_error_message"] = [
                res.get("error_message") for res in padded_results
            ]

        self.logger.info(
            f"Finished getting completions for {len(expanded_df)} total samples."
        )
        return expanded_df

    def _execute_completion_request(
        self,
        goal: str,
        prefix: str,
        index: int,
        adk_session_id: Optional[str],
        adk_user_id: Optional[str],
    ) -> Dict[str, Any]:
        """Executes a single completion request via the AgentRouter.

        Constructs the prompt based on the agent type and configuration. For ADK agents,
        the prefix itself is used as the prompt, and ADK session/user IDs are included.
        For LiteLLM agents, a surrogate attack prompt may be prepended to the goal and prefix.
        The method then calls the AgentRouter to get the completion and processes the response,
        extracting generated text, raw request/response details, and any errors.

        Args:
            goal: The goal associated with the prefix.
            prefix: The prefix text to be completed.
            index: The original index of the request (for logging purposes).
            adk_session_id: Optional ADK session ID, used if the agent is GOOGLE_ADK.
            adk_user_id: Optional ADK user ID, used if the agent is GOOGLE_ADK.

        Returns:
            A dictionary containing:
            - 'generated_text': The completed text from the model.
            - 'request_payload': The payload sent to the agent.
            - 'response_status_code': The HTTP status code of the agent's response.
            - 'response_headers': The headers of the agent's response.
            - 'response_body_raw': The raw body of the agent's response.
            - 'adk_events_list': A list of ADK events, if applicable.
            - 'error_message': Any error message from the agent or during processing.
        """
        request_params: Dict[str, Any] = {"timeout": self.config.request_timeout}
        prompt_to_send: str

        try:
            if self.config.agent_type == AgentTypeEnum.GOOGLE_ADK:
                prompt_to_send = prefix
                if adk_session_id:
                    request_params["adk_session_id"] = adk_session_id
                if adk_user_id:
                    request_params["adk_user_id"] = adk_user_id
            elif self.config.agent_type == AgentTypeEnum.LITELLM:
                prompt_to_send = (
                    f"{self.config.surrogate_attack_prompt} {goal} {prefix}"
                    if self.config.surrogate_attack_prompt
                    else f"{goal} {prefix}"
                )
            else:
                self.logger.warning(
                    f"Unknown agent type '{self.config.agent_type}', using default prompt format: goal + prefix."
                )
                prompt_to_send = f"{goal} {prefix}"

            request_params["prompt"] = prompt_to_send

            adapter_response = self.agent_router.route_request(
                registration_key=self.agent_registration_key,
                request_data=request_params,
            )

            generated_text = adapter_response.get("processed_response", "")
            error_message = adapter_response.get("error_message")

            if error_message:
                self.logger.warning(
                    f"Error reported by agent/adapter for prefix (idx {index}) '{prefix[:50]}...': {error_message}"
                )
                if (
                    not generated_text or "[GENERATION_ERROR" not in generated_text
                ):  # Avoid double-marking
                    generated_text = f"[ERROR_FROM_ADAPTER: {error_message}]"

            raw_request_payload = adapter_response.get("raw_request", request_params)
            response_status_code = adapter_response.get("status_code")
            response_headers = adapter_response.get("raw_response_headers")
            response_body_raw = adapter_response.get("raw_response_body")
            adk_events_list = adapter_response.get("agent_specific_data", {}).get(
                "adk_events_list"
            )

            self.logger.debug(
                f"Completed request for prefix (idx {index}): '{prefix[:50]}...' -> '{generated_text[:50]}...'"
            )
            return {
                "generated_text": generated_text,
                "request_payload": raw_request_payload,
                "response_status_code": response_status_code,
                "response_headers": response_headers,
                "response_body_raw": response_body_raw,
                "adk_events_list": adk_events_list,
                "error_message": error_message,
            }

        except Exception as e:
            self.logger.error(
                f"Critical exception in _execute_completion_request for index {index}, prefix '{prefix[:50]}...': {e}",
                exc_info=True,
            )
            return {
                "generated_text": f"[ERROR: Completer Exception - {type(e).__name__}]",
                "request_payload": request_params,  # Log what we tried to send
                "response_status_code": None,
                "response_headers": None,
                "response_body_raw": None,
                "adk_events_list": None,
                "error_message": str(e),
            }

    # _get_adk_completion and _get_litellm_completion are now removed and replaced by _execute_completion_request
    # __del__ method removed as no explicit cleanup was being done that's still relevant.
