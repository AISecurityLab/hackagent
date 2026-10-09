---
sidebar_label: build
title: hackagent.models.build
---

Build a :class:`Model` from a :class:`ModelConfig`.

## ModelCallError Objects

```python
class ModelCallError(RuntimeError)
```

A model gave no usable reply.

#### build\_model

```python
def build_model(config: ModelConfig, *, retries: int = 0) -> Model
```

Create the model client described by `config`.

No request is sent. An `api_key_env` that is not set fails here, so
configuration errors surface before a run starts.

#### as\_completion

```python
def as_completion(
        model: Model
) -> Callable[[Sequence[Mapping[str, Any]]], Awaitable[str]]
```

Expose `model` as the text-in, text-out callable attacks depend on.

#### build\_embedder

```python
def build_embedder(
    config: ModelConfig
) -> Callable[[Sequence[str]], Awaitable[list[list[float]]]]
```

Expose `config` as the texts-in, vectors-out callable retrieval needs.

The embeddings API is a different endpoint from chat, so this does not
go through :class:`Model`; it builds a LiteLLM embedding request from the
same connection fields and runs the blocking call off the event loop.

