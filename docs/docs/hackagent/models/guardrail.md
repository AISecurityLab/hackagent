---
sidebar_label: guardrail
title: hackagent.models.guardrail
---

Guardrails around a model: check prompts before, and responses after.

A guardrail classifies text as safe or unsafe. :class:`Guarded` wraps an
LLM with an optional `before` guardrail (checks the prompt; a blocked
prompt never reaches the model) and an optional `after` guardrail
(checks the response; a flagged response is withheld). Either way the call
returns a completion whose `guardrail` field says what happened.

The default :class:`LLMGuardrail` asks a classifier model for a JSON
verdict. It fails open: an unavailable or unparseable classifier lets the
text through, so a misconfigured guardrail never blocks all traffic.

## GuardrailSpec Objects

```python
class GuardrailSpec(ModelSpec)
```

A guardrail classifier model, with an optional custom system prompt.

## GuardrailResult Objects

```python
@dataclass(frozen=True)
class GuardrailResult()
```

Outcome of one guardrail check.

**Attributes**:

- `is_safe` - `True` if the text passed the check.
- `explanation` - The classifier&#x27;s reason.
- `categories` - Harm categories flagged (empty when safe).
- `raw_response` - The classifier&#x27;s raw text, if any.

## Guardrail Objects

```python
class Guardrail(Protocol)
```

Anything that can classify a piece of text.

## LLMGuardrail Objects

```python
class LLMGuardrail()
```

A guardrail that asks a classifier model for a JSON verdict.

#### describe

```python
def describe() -> ModelSpec
```

The classifier model&#x27;s spec.

#### check

```python
def check(text: str) -> GuardrailResult
```

Classify `text`; fails open when the classifier is unavailable.

#### parse\_verdict

```python
def parse_verdict(raw: str) -> GuardrailResult
```

Parse `{&quot;safe&quot;: ..., &quot;categories&quot;: [...], &quot;reasoning&quot;: ...}`.

Falls back to keyword detection when the text is not JSON.

## Guarded Objects

```python
class Guarded(EnvelopeLLM)
```

`llm` with guardrails applied to every call.

