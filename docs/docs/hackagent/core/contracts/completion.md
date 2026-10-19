---
sidebar_label: completion
title: hackagent.core.contracts.completion
---

The result of one model call, and why a call failed.

## RawExchange Objects

```python
class RawExchange(BaseModel)
```

The provider-level request and response, for callers that need them.

## LLMError Objects

```python
class LLMError(BaseModel)
```

Why a call failed. Calls return errors as values.

## GuardrailInfo Objects

```python
class GuardrailInfo(BaseModel)
```

A guardrail blocked the prompt (`before`) or the response (`after`).

## Completion Objects

```python
class Completion(BaseModel)
```

The result of one model call.

Replaces the response dict: `generated_text` / `processed_response`
become `text`; `error_message` / `error_category` become `error`;
`agent_specific_data` usage, finish reason, model and invoked
parameters become typed fields; `raw_response_*` and `raw_request`
become `raw`; a guardrail envelope becomes `guardrail`.

#### ok

```python
@property
def ok() -> bool
```

True when the call produced a usable response.

#### blocked

```python
@property
def blocked() -> bool
```

True when a guardrail blocked or censored the call.

#### guardrail\_info

```python
@property
def guardrail_info() -> Dict[str, Any]
```

Guardrail metadata as a plain dict (empty when not blocked).

