---
sidebar_label: utils
title: hackagent.attacks.AdvPrefix.utils
---

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

#### logger

Use a logger specific to utils

#### get\_checkpoint\_path

```python
def get_checkpoint_path(run_dir: str, step_num: int) -> str
```

Generate the standardized file path for a pipeline step&#x27;s output checkpoint.

This utility function creates consistent checkpoint file naming and location
conventions across all AdvPrefix pipeline steps, facilitating debugging,
resume functionality, and intermediate result inspection.

**Arguments**:

- `run_dir` - Base directory path for the current attack run where all
  checkpoints and outputs are stored.
- `step_num` - Numerical identifier of the pipeline step (e.g., 1, 2, 3).
  

**Returns**:

  Complete file path string for the step&#x27;s CSV checkpoint file.
- `Format` - &quot;{run_dir}/step{step_num}_output.csv&quot;
  

**Notes**:

  The standardized naming convention allows for easy identification
  of pipeline stage outputs and supports automated checkpoint loading
  and pipeline resumption functionality.

#### call\_litellm\_completion

```python
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
    logger: Optional[logging.Logger] = None
) -> Tuple[Optional[str], Optional[Any], Optional[Exception]]
```

Execute a LiteLLM completion request with comprehensive error handling.

This wrapper function provides a standardized interface for calling
LiteLLM completion API across different pipeline stages. It handles
common exceptions and ensures consistent parameter processing and
response extraction.

**Arguments**:

- `model_id` - Model identifier string for LiteLLM (e.g., &quot;gpt-4&quot;, &quot;ollama/llama2&quot;).
- `messages` - List of message dictionaries for chat completion format.
  Each dict should have &#x27;role&#x27; and &#x27;content&#x27; keys.
- `endpoint` - Optional API base URL for custom endpoints (e.g., local Ollama).
- `api_key` - Optional API key for authenticated services.
- `timeout` - Request timeout in seconds to prevent hanging requests.
- `temperature` - Sampling temperature for response generation (0.0-2.0).
- `max_tokens` - Maximum number of new tokens to generate.
- `logprobs` - Whether to request log probabilities in the response.
- `top_p` - Top-p sampling parameter for nucleus sampling (0.0-1.0).
- `logger` - Optional logger instance for detailed operation tracking.
  

**Returns**:

  A tuple containing (content, logprobs, error):
  - content: Generated text content if successful, None on failure
  - logprobs: Log probability data if requested and available, None otherwise
  - error: Exception object if an error occurred, None on success
  

**Notes**:

  The function automatically filters out None parameters and handles
  both LiteLLM-specific exceptions and general errors gracefully.
  API keys are excluded from debug logging for security.
  
  The &#x27;drop_params&#x27; setting ensures compatibility with models that
  don&#x27;t support all parameters.

#### execute\_processor\_step

```python
def execute_processor_step(input_df: pd.DataFrame, logger: logging.Logger,
                           run_dir: str, processor_instance: Any,
                           processor_method_name: str, step_number: int,
                           step_name_for_logging: str,
                           log_success_details_template: str,
                           **processor_method_kwargs: Any) -> pd.DataFrame
```

Execute a generic pipeline step with standardized error handling and checkpointing.

This utility function provides a unified framework for executing pipeline steps
across the AdvPrefix attack process. It handles method invocation, error recovery,
checkpoint saving, and logging with consistent patterns throughout the pipeline.

**Arguments**:

- `input_df` - Input DataFrame containing data for processing. Empty DataFrames
  are handled gracefully by skipping processing.
- `logger` - Logger instance from the calling context for consistent log formatting
  and tracking across the entire pipeline.
- `run_dir` - Base directory path for saving step checkpoints and intermediate results.
- `processor_instance` - Object instance that contains the processing method to execute.
  Can be any processor class (e.g., PrefixPreprocessor).
- `processor_method_name` - Name of the method to call on the processor instance.
  Method should accept a DataFrame and return a processed DataFrame.
- `step_number` - Numerical identifier for this pipeline step, used for checkpoint
  naming and progress tracking.
- `step_name_for_logging` - Human-readable description of the step for log messages
  and progress reporting.
- `log_success_details_template` - Template string for success logging with a
  &#x27;{count}&#x27; placeholder for the number of processed rows.
- `**processor_method_kwargs` - Additional keyword arguments to pass to the
  processor method for customized execution.
  

**Returns**:

  Processed DataFrame if successful, or the original input DataFrame if
  processing fails or input is empty. This ensures pipeline continuity
  even when individual steps encounter errors.
  

**Notes**:

  The function automatically saves processing results as CSV checkpoints
  using standardized naming conventions. Error handling is comprehensive
  to prevent individual step failures from terminating the entire pipeline.
  
  Method resolution and invocation are handled dynamically, allowing
  this function to work with any processor class that follows the
  expected interface pattern.

