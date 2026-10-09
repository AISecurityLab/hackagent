---
sidebar_label: response
title: hackagent.models.response
---

Normalized responses returned by model backends.

## ModelResponse Objects

```python
@dataclass
class ModelResponse()
```

Backend-independent view of a model completion response.

#### failed

```python
@classmethod
def failed(cls, error: Exception) -> "ModelResponse"
```

Represent provider failures without losing their status or category.

#### reasoning

```python
@property
def reasoning() -> Optional[str]
```

Return reasoning content using a backend-independent name.

#### from\_value

```python
@classmethod
def from_value(cls, value: Any) -> "ModelResponse"
```

Normalize common values, including LiteLLM `ModelResponse` objects.

#### from\_litellm

```python
@classmethod
def from_litellm(cls, value: Any) -> "ModelResponse"
```

Normalize a LiteLLM `ModelResponse` without discarding its metadata.

