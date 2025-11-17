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
Utility functions for AdvPrefix attacks.

This module provides common utility functions and helper methods used across
the AdvPrefix attack pipeline. It includes shared functionality for data
processing, file operations, logging, and other support tasks.

The module provides:
- File I/O utilities for saving and loading intermediate results
- Data format conversion and validation helpers
- Logging and debugging utilities
- String processing and text manipulation functions
- Configuration parsing and validation helpers
- Common mathematical and statistical operations

These utilities promote code reuse and maintain consistency across the
different stages of the AdvPrefix attack pipeline.
"""

import os
import pandas as pd
import logging
import litellm
from typing import List, Dict, Optional, Tuple, Any

# Imports needed for execute_processor_step
from typing import Callable  # Keep for execute_processor_step


logger = logging.getLogger(__name__)  # Use a logger specific to utils


def get_checkpoint_path(run_dir: str, step_num: int) -> str:
    """
    Generate the standardized file path for a pipeline step's output checkpoint.

    This utility function creates consistent checkpoint file naming and location
    conventions across all AdvPrefix pipeline steps, facilitating debugging,
    resume functionality, and intermediate result inspection.

    Args:
        run_dir: Base directory path for the current attack run where all
            checkpoints and outputs are stored.
        step_num: Numerical identifier of the pipeline step (e.g., 1, 2, 3).

    Returns:
        Complete file path string for the step's CSV checkpoint file.
        Format: "{run_dir}/step{step_num}_output.csv"

    Note:
        The standardized naming convention allows for easy identification
        of pipeline stage outputs and supports automated checkpoint loading
        and pipeline resumption functionality.
    """
    filename = f"step{step_num}_output.csv"
    return os.path.join(run_dir, filename)


def call_litellm_completion(
    model_id: str,
    messages: List[Dict[str, str]],
    endpoint: Optional[str],
    api_key: Optional[str],
    timeout: int,
    temperature: float,
    max_tokens: int,
    logprobs: bool = False,
    top_p: float = 1.0,
    logger: Optional[logging.Logger] = None,
) -> Tuple[Optional[str], Optional[Any], Optional[Exception]]:
    """
    Execute a LiteLLM completion request with comprehensive error handling.

    This wrapper function provides a standardized interface for calling
    LiteLLM completion API across different pipeline stages. It handles
    common exceptions and ensures consistent parameter processing and
    response extraction.

    Args:
        model_id: Model identifier string for LiteLLM (e.g., "gpt-4", "ollama/llama2").
        messages: List of message dictionaries for chat completion format.
            Each dict should have 'role' and 'content' keys.
        endpoint: Optional API base URL for custom endpoints (e.g., local Ollama).
        api_key: Optional API key for authenticated services.
        timeout: Request timeout in seconds to prevent hanging requests.
        temperature: Sampling temperature for response generation (0.0-2.0).
        max_tokens: Maximum number of new tokens to generate.
        logprobs: Whether to request log probabilities in the response.
        top_p: Top-p sampling parameter for nucleus sampling (0.0-1.0).
        logger: Optional logger instance for detailed operation tracking.

    Returns:
        A tuple containing (content, logprobs, error):
        - content: Generated text content if successful, None on failure
        - logprobs: Log probability data if requested and available, None otherwise
        - error: Exception object if an error occurred, None on success

    Note:
        The function automatically filters out None parameters and handles
        both LiteLLM-specific exceptions and general errors gracefully.
        API keys are excluded from debug logging for security.

        The 'drop_params' setting ensures compatibility with models that
        don't support all parameters.
    """
    litellm.drop_params = True  # Drop unsupported parameters

    if logger is None:
        logger = logging.getLogger(__name__)  # Fallback logger

    content_string: Optional[str] = None
    logprobs_data: Optional[Any] = None
    error_object: Optional[Exception] = None

    try:
        litellm_kwargs = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "endpoint": endpoint,
            "api_key": api_key,
            "timeout": timeout,
            "logprobs": logprobs,
        }
        # Filter out None values, especially api_key and endpoint if not provided
        litellm_kwargs = {k: v for k, v in litellm_kwargs.items() if v is not None}

        logger.debug(
            f"Calling litellm.completion with kwargs: { {k: v for k, v in litellm_kwargs.items() if k != 'api_key'} }"
        )  # Don't log key
        response = litellm.completion(**litellm_kwargs)

        # Extract content
        if (
            response
            and response.choices
            and response.choices[0].message
            and response.choices[0].message.content
        ):
            content_string = response.choices[0].message.content
        else:
            logger.warning(
                f"LiteLLM call successful but no content found in response structure. Model: {model_id}"
            )

        # Extract logprobs if requested and available
        if logprobs:
            if response and response.choices and response.choices[0].logprobs:
                logprobs_data = response.choices[0].logprobs
            else:
                logger.warning(
                    f"Logprobs were requested but not found in response structure. Model: {model_id}"
                )

    except litellm.exceptions.BadRequestError as llm_bad_req_err:
        logger.error(f"LiteLLM Bad Request Error: {llm_bad_req_err}")
        error_object = llm_bad_req_err
    except litellm.exceptions.APIError as llm_api_err:
        logger.error(f"LiteLLM API Error: {llm_api_err}")
        error_object = llm_api_err
    except Exception as e:
        logger.error(f"Generic error during LiteLLM call: {e}", exc_info=True)
        error_object = e

    return content_string, logprobs_data, error_object


def execute_processor_step(
    input_df: pd.DataFrame,
    logger: logging.Logger,  # This logger is passed in, not using the module-level logger directly
    run_dir: str,
    processor_instance: Any,
    processor_method_name: str,
    step_number: int,
    step_name_for_logging: str,
    log_success_details_template: str,
    **processor_method_kwargs: Any,
) -> pd.DataFrame:
    """
    Execute a generic pipeline step with standardized error handling and checkpointing.

    This utility function provides a unified framework for executing pipeline steps
    across the AdvPrefix attack process. It handles method invocation, error recovery,
    checkpoint saving, and logging with consistent patterns throughout the pipeline.

    Args:
        input_df: Input DataFrame containing data for processing. Empty DataFrames
            are handled gracefully by skipping processing.
        logger: Logger instance from the calling context for consistent log formatting
            and tracking across the entire pipeline.
        run_dir: Base directory path for saving step checkpoints and intermediate results.
        processor_instance: Object instance that contains the processing method to execute.
            Can be any processor class (e.g., PrefixPreprocessor).
        processor_method_name: Name of the method to call on the processor instance.
            Method should accept a DataFrame and return a processed DataFrame.
        step_number: Numerical identifier for this pipeline step, used for checkpoint
            naming and progress tracking.
        step_name_for_logging: Human-readable description of the step for log messages
            and progress reporting.
        log_success_details_template: Template string for success logging with a
            '{count}' placeholder for the number of processed rows.
        **processor_method_kwargs: Additional keyword arguments to pass to the
            processor method for customized execution.

    Returns:
        Processed DataFrame if successful, or the original input DataFrame if
        processing fails or input is empty. This ensures pipeline continuity
        even when individual steps encounter errors.

    Note:
        The function automatically saves processing results as CSV checkpoints
        using standardized naming conventions. Error handling is comprehensive
        to prevent individual step failures from terminating the entire pipeline.

        Method resolution and invocation are handled dynamically, allowing
        this function to work with any processor class that follows the
        expected interface pattern.
    """
    logger.info(f"--- Running Step {step_number}: {step_name_for_logging} ---")

    if input_df.empty:
        logger.warning(
            f"Step {step_number} ({step_name_for_logging}) received an empty DataFrame. Skipping."
        )
        return input_df

    processed_df: pd.DataFrame
    try:
        method_to_call: Callable[..., pd.DataFrame] = getattr(
            processor_instance, processor_method_name
        )
        if processor_method_kwargs:
            processed_df = method_to_call(input_df, **processor_method_kwargs)
        else:
            processed_df = method_to_call(input_df)

    except AttributeError:
        logger.error(
            f"Processor object does not have method '{processor_method_name}'. Step {step_number} ({step_name_for_logging}) failed.",
            exc_info=True,
        )
        return input_df
    except Exception as e:
        logger.error(
            f"Error during {processor_instance.__class__.__name__}.{processor_method_name} for Step {step_number} ({step_name_for_logging}): {e}",
            exc_info=True,
        )
        return input_df

    # This now calls get_checkpoint_path defined in this same utils.py file
    output_path = get_checkpoint_path(run_dir, step_number)
    try:
        processed_df.to_csv(output_path, index=False)
        count = len(processed_df)
        success_details = log_success_details_template.format(count=count)
        logger.info(
            f"Step {step_number} ({step_name_for_logging}) complete. {success_details}"
        )
        logger.info(f"Checkpoint saved to {output_path}")
    except Exception as e:
        logger.error(
            f"Failed to save checkpoint for Step {step_number} ({step_name_for_logging}) to {output_path}: {e}"
        )

    return processed_df
