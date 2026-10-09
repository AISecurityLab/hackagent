---
sidebar_label: litellm
title: hackagent.models.completions.litellm
---

Model implementation backed directly by LiteLLM.

#### KNOWN\_LITELLM\_PROVIDER\_PREFIXES

LiteLLM provider prefixes a model string may already carry.

#### resolve\_litellm\_model

```python
def resolve_litellm_model(raw_model: str,
                          *,
                          provider_prefix: Optional[str] = None) -> str
```

Return the model string to pass to `litellm.completion`.

Honors a caller-supplied `provider_prefix` while leaving names that
already carry an explicit LiteLLM provider prefix untouched.

#### normalise\_ollama\_endpoint

```python
def normalise_ollama_endpoint(endpoint: Optional[str]) -> str
```

Resolve and normalise an Ollama endpoint URL to its base form.

## LiteLLMModel Objects

```python
class LiteLLMModel(Model)
```

Execute synchronous and asynchronous LiteLLM completions.

#### complete

```python
def complete(messages: Sequence[Mapping[str, Any]],
             **overrides: Any) -> ModelResponse
```

Run a synchronous LiteLLM completion.

#### acomplete

```python
async def acomplete(messages: Sequence[Mapping[str, Any]],
                    **overrides: Any) -> ModelResponse
```

Run an asynchronous LiteLLM completion.

