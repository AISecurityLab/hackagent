---
sidebar_label: openai
title: hackagent.router.adapters.openai
---

## OpenAIConfigurationError Objects

```python
class OpenAIConfigurationError(AdapterConfigurationError)
```

Custom exception for OpenAI adapter configuration issues.

#### logger

Module-level logger

## OpenAIAgent Objects

```python
class OpenAIAgent(ChatCompletionsAgent)
```

Adapter for interacting with AI agents built using the OpenAI SDK.

This adapter supports OpenAI&#x27;s chat completions API, including support for
function calling and tool use, which are common patterns in agent implementations.

#### DEFAULT\_TEMPERATURE

OpenAI default

#### \_\_init\_\_

```python
def __init__(id: str, config: Dict[str, Any])
```

Initializes the OpenAIAgent.

**Arguments**:

- `id` - The unique identifier for this OpenAI agent instance.
- `config` - Configuration dictionary for the OpenAI agent.
  Expected keys:
  - &#x27;name&#x27;: Model name (e.g., &quot;gpt-4&quot;, &quot;gpt-3.5-turbo&quot;).
  - &#x27;endpoint&#x27; (optional): Base URL for the API (for custom endpoints).
  - &#x27;api_key&#x27; (optional): Name of the environment variable holding the API key,
  or the API key itself. Defaults to OPENAI_API_KEY env var.
  - &#x27;max_tokens&#x27; (optional): Default max tokens for generation.
  - &#x27;temperature&#x27; (optional): Default temperature (defaults to 1.0).
  - &#x27;tools&#x27; (optional): List of tool/function definitions for function calling.
  - &#x27;tool_choice&#x27; (optional): Controls which tools the model can call.

