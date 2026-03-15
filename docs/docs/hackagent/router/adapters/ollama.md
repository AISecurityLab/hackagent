---
sidebar_label: ollama
title: hackagent.router.adapters.ollama
---

Ollama Agent Adapter

This adapter provides direct integration with Ollama for running local LLMs.
It uses Ollama&#x27;s native HTTP API for efficient communication.

## OllamaConfigurationError Objects

```python
class OllamaConfigurationError(AdapterConfigurationError)
```

Custom exception for Ollama adapter configuration issues.

## OllamaConnectionError Objects

```python
class OllamaConnectionError(AdapterInteractionError)
```

Custom exception for Ollama connection issues.

## OllamaAgent Objects

```python
class OllamaAgent(Agent)
```

Adapter for interacting with Ollama&#x27;s native HTTP API.

This adapter provides direct integration with Ollama for running local LLMs,
bypassing LiteLLM for more efficient and direct communication.

Ollama API Endpoints:
- /api/generate: Generate completions (used for text generation)
- /api/chat: Chat completions (used for chat-based models)
- /api/tags: List available models
- /api/show: Show model information

Configuration:
- &#x27;name&#x27;: Model name (e.g., &quot;llama3&quot;, &quot;mistral&quot;, &quot;codellama&quot;)
- &#x27;endpoint&#x27;: Ollama API base URL (default: &quot;http://localhost:11434&quot;)
- &#x27;max_new_tokens&#x27;: Maximum tokens to generate (default: 100)
- &#x27;temperature&#x27;: Sampling temperature (default: 0.8)
- &#x27;top_p&#x27;: Top-p sampling parameter (default: 0.95)
- &#x27;top_k&#x27;: Top-k sampling parameter (optional)
- &#x27;num_ctx&#x27;: Context window size (optional)
- &#x27;stream&#x27;: Whether to stream responses (default: False)

#### \_\_init\_\_

```python
def __init__(id: str, config: Dict[str, Any])
```

Initializes the OllamaAgent.

**Arguments**:

- `id` - The unique identifier for this Ollama agent instance.
- `config` - Configuration dictionary for the Ollama agent.
  Expected keys:
  - &#x27;name&#x27;: Model name (required, e.g., &quot;llama3&quot;, &quot;mistral&quot;)
  - &#x27;endpoint&#x27; (optional): Ollama API base URL (default: http://localhost:11434)
  - &#x27;max_new_tokens&#x27; (optional): Default max tokens for generation (default: 100)
  - &#x27;temperature&#x27; (optional): Default temperature (default: 0.8)
  - &#x27;top_p&#x27; (optional): Default top_p (default: 0.95)
  - &#x27;top_k&#x27; (optional): Default top_k sampling
  - &#x27;num_ctx&#x27; (optional): Context window size
  - &#x27;stream&#x27; (optional): Enable streaming (default: False)

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Processes an incoming request using Ollama&#x27;s API.

This method handles both &#x27;prompt&#x27; (for /api/generate) and &#x27;messages&#x27;
(for /api/chat) formats, automatically selecting the appropriate endpoint.

**Arguments**:

- `request_data` - The data for the agent to process. Expected keys:
  - &#x27;prompt&#x27; or &#x27;messages&#x27;: The input for generation
  - &#x27;max_new_tokens&#x27; or &#x27;max_tokens&#x27; (optional): Override default max tokens
  - &#x27;temperature&#x27; (optional): Override default temperature
  - &#x27;top_p&#x27; (optional): Override default top_p
  - &#x27;top_k&#x27; (optional): Override default top_k
  - &#x27;system&#x27; (optional): System prompt for generate endpoint
  - &#x27;stream&#x27; (optional): Enable streaming
  

**Returns**:

  A dictionary containing:
  - &#x27;status_code&#x27;: HTTP-like status code
  - &#x27;raw_request&#x27;: The original request data
  - &#x27;raw_response&#x27;: The raw Ollama response
  - &#x27;processed_response&#x27;: The generated text
  - &#x27;error_message&#x27;: Error message if any
  - &#x27;agent_specific_data&#x27;: Ollama-specific metadata

#### list\_models

```python
def list_models() -> List[Dict[str, Any]]
```

List available models from Ollama.

**Returns**:

  List of model information dictionaries

#### model\_info

```python
def model_info() -> Dict[str, Any]
```

Get information about the current model.

**Returns**:

  Dictionary with model information

#### is\_available

```python
def is_available() -> bool
```

Check if Ollama is available and the model is loaded.

**Returns**:

  True if Ollama is reachable and the model exists

