---
sidebar_label: completer
title: hackagent.attacks.AdvPrefix.completer
---

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

## CompletionConfig Objects

```python
@dataclass
class CompletionConfig()
```

Configuration for generating completions using an Agent via AgentRouter.

**Attributes**:

- `agent_name` - A descriptive name for this agent configuration.
- `agent_type` - The type of agent (e.g., ADK, LiteLLM) to use.
- `organization_id` - The organization ID for backend agent registration.
- `model_id` - A general model identifier (e.g., &quot;claude-2&quot;, &quot;gpt-4&quot;).
- `agent_endpoint` - The API endpoint for the agent service.
- `agent_metadata` - Optional dictionary for agent-specific metadata.
  For ADK: e.g., {&#x27;adk_app_name&#x27;: &#x27;my_app&#x27;}.
  For LiteLLM: e.g., {&#x27;name&#x27;: &#x27;litellm_model_string&#x27;, &#x27;api_key&#x27;: &#x27;ENV_VAR_NAME&#x27;}.
- `batch_size` - The number of requests to batch if supported by the underlying adapter (currently informational).
- `max_new_tokens` - The maximum number of new tokens to generate for each completion.
- `temperature` - The temperature setting for token generation.
- `n_samples` - The number of completion samples to generate for each input prefix.
- `agent_type`0 - An optional prompt to prepend for surrogate attacks, typically used with LiteLLM agents.
- `agent_type`1 - The timeout in seconds for each completion request.

## PrefixCompleter Objects

```python
class PrefixCompleter()
```

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

**Attributes**:

- `client` - AuthenticatedClient for API communications
- `config` - CompletionConfig with all completion parameters
- `logger` - Logger instance for operation tracking
- `api_key` - API key for LiteLLM models (if applicable)
- `agent_router` - AgentRouter instance for model interactions
- `agent_registration_key` - Registration key for the configured agent

#### \_\_init\_\_

```python
def __init__(client: AuthenticatedClient, config: CompletionConfig)
```

Initialize the PrefixCompleter with client and configuration.

Sets up the AgentRouter, handles API key configuration for LiteLLM models,
and prepares the completer for generating completions. The initialization
process includes agent registration and adapter configuration.

**Arguments**:

- `client` - AuthenticatedClient instance for API communication with
  the HackAgent backend and target models.
- `config` - CompletionConfig object containing all completion parameters
  including agent type, model settings, and generation parameters.
  

**Raises**:

- `RuntimeError` - If the AgentRouter fails to register an agent during
  initialization, indicating configuration or connectivity issues.
  

**Notes**:

  For LiteLLM agents, API keys are automatically loaded from environment
  variables specified in the agent metadata. The initialization process
  includes comprehensive adapter configuration based on the agent type.

#### expand\_dataframe

```python
def expand_dataframe(df: pd.DataFrame) -> pd.DataFrame
```

Expand DataFrame to create multiple samples for each adversarial prefix.

This method prepares the input DataFrame for completion generation by
creating multiple rows for each original prefix based on the configured
number of samples. This allows for statistical analysis of completion
variability and improves attack success rate estimation.

**Arguments**:

- `df` - Input DataFrame containing adversarial prefixes. Each row
  represents a unique prefix to be expanded for sampling.
  

**Returns**:

  Expanded DataFrame where each original row is duplicated n_samples
  times. New columns added:
  - sample_id: Integer identifier for each sample (0 to n_samples-1)
  - completion: Empty string placeholder for generated completions
  

**Notes**:

  Progress tracking is provided for the expansion process. The expansion
  maintains all original columns while adding sample-specific metadata.
  This structure facilitates parallel processing and result aggregation
  in downstream pipeline stages.

#### get\_completions

```python
def get_completions(df: pd.DataFrame) -> pd.DataFrame
```

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

**Arguments**:

- `df` - DataFrame containing adversarial prefixes to complete. Must
  include &#x27;goal&#x27; and either &#x27;prefix&#x27; or &#x27;target&#x27; columns.
  Additional columns are preserved in the output.
  

**Returns**:

  Expanded DataFrame with generated completions and metadata:
  - generated_text_only: The actual completion text from the model
  - request_payload: Request data sent to the agent
  - response_status_code: HTTP status code from the response
  - response_headers: Response headers from the agent interaction
  - response_body_raw: Raw response body for debugging
  - adk_events_list: ADK-specific event data (for ADK agents)
  - completion_error_message: Error messages if completion failed
  

**Raises**:

- `ValueError` - If the input DataFrame is missing required columns
  (&#x27;goal&#x27; and &#x27;prefix&#x27;/&#x27;target&#x27;).
  

**Notes**:

  Progress tracking is provided for completion generation. For ADK
  agents, unique session and user IDs are generated to ensure
  proper session isolation. All errors are captured gracefully
  to allow batch processing to continue.

