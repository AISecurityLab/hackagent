---
sidebar_label: litellm
title: hackagent.router.adapters.litellm
---

## LiteLLMConfigurationError Objects

```python
class LiteLLMConfigurationError(AdapterConfigurationError)
```

Custom exception for LiteLLM adapter configuration issues.

#### logger

Module-level logger

## LiteLLMAgent Objects

```python
class LiteLLMAgent(ChatCompletionsAgent)
```

Adapter for interacting with LLMs via the LiteLLM library.

This adapter supports multiple LLM providers through LiteLLM&#x27;s unified interface.
For custom/self-hosted endpoints, the endpoint URL must be provided correctly:

OpenAI-Compatible Endpoints:
- Provide the base URL ending with /v1 (e.g., &quot;http://localhost:8000/v1&quot;)
- The OpenAI client will automatically append /chat/completions
- Example: endpoint=&quot;http://localhost:8000/v1&quot; → requests to http://localhost:8000/v1/chat/completions

Non-OpenAI Protocols:
- Use the appropriate agent type (LANGCHAIN, MCP, A2A) instead of routing through LiteLLM
- LANGCHAIN: Use LangServe endpoints (e.g., &quot;http://localhost:8000/invoke&quot;)
- MCP: Use Model Context Protocol adapter (not LiteLLM)
- A2A: Use Agent-to-Agent protocol adapter (not LiteLLM)

#### \_\_init\_\_

```python
def __init__(id: str, config: Dict[str, Any])
```

Initializes the LiteLLMAgent.

**Arguments**:

- `id` - The unique identifier for this LiteLLM agent instance.
- `config` - Configuration dictionary for the LiteLLM agent.
  Expected keys:
  - &#x27;name&#x27;: Model string for LiteLLM (e.g., &quot;ollama/llama3&quot;).
  - &#x27;endpoint&#x27; (optional): Base URL for the API.
  - &#x27;api_key&#x27; (optional): Name of the environment variable holding the API key.
  - &#x27;max_new_tokens&#x27; (optional): Default max tokens for generation (defaults to 100).
  - &#x27;temperature&#x27; (optional): Default temperature (defaults to 0.8).
  - &#x27;top_p&#x27; (optional): Default top_p (defaults to 0.95).

