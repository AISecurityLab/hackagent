---
sidebar_label: guardrail
title: hackagent.attacks.shared.guardrail
---

Guardrail infrastructure for attack pipelines.

This module provides the abstract ``BaseGuardrail`` class and its default
LLM-backed implementation ``LLMGuardrail``, together with the
``create_guardrail_from_config`` factory that mirrors the ``create_router``
pattern used throughout the attacks package.

Guardrails intercept text **before** it is sent to the target model
(``before_guardrail``) and/or **after** a response is received
(``after_guardrail``).  They are configured on the ``HackAgent`` at
initialisation time, using the same field semantics as ``attacker`` and
``judges``:

    agent = HackAgent(
        name=&quot;llama3&quot;,
        endpoint=&quot;http://localhost:11434&quot;,
        agent_type=&quot;ollama&quot;,
        before_guardrail={
            &quot;identifier&quot;: &quot;openai/gpt-oss-safeguard-20b&quot;,
            &quot;endpoint&quot;: &quot;https://openrouter.ai/api/v1&quot;,
            &quot;api_key&quot;: &quot;OPENROUTER_API_KEY&quot;,   # env-var name or literal
            &quot;agent_type&quot;: &quot;OPENAI_SDK&quot;,
            &quot;temperature&quot;: 0.0,
            &quot;max_tokens&quot;: 200,
        },
        after_guardrail={ ... },
    )

The ``HackAgent.__init__`` wires guardrail instances onto the target router
so they apply transparently to every ``route_request`` call for all attacks.
Attack implementations call the helpers exposed by ``BaseAttack`` — see
``attacks/base.py``.

## GuardrailResult Objects

```python
@dataclass(frozen=True)
class GuardrailResult()
```

Outcome of a single guardrail check.

**Attributes**:

- `is_safe` - ``True`` if the text passed the guardrail check.
- `explanation` - Human-readable reason from the guardrail model.
- `categories` - List of harm categories flagged (empty when safe).
- `raw_response` - Raw text returned by the guardrail model, if available.

## BaseGuardrail Objects

```python
class BaseGuardrail(ABC)
```

Abstract interface for all guardrail implementations.

Concrete subclasses must implement ``check(text) -&gt; GuardrailResult``.

#### check

```python
@abstractmethod
def check(text: str) -> GuardrailResult
```

Check whether *text* is safe.

**Arguments**:

- `text` - The prompt or model response to inspect.
  

**Returns**:

  A :class:`GuardrailResult` with ``is_safe=True`` when the text
  passes and ``is_safe=False`` when it is flagged.

## LLMGuardrail Objects

```python
class LLMGuardrail(BaseGuardrail)
```

Guardrail that delegates the safety check to an LLM via the router.

The guardrail model is configured with the same dict fields accepted by
``create_router`` (``identifier``, ``endpoint``, ``api_key``,
``agent_type``, ``temperature``, ``max_tokens``, ``timeout``).

An optional ``system_prompt`` key in the config overrides the default
classifier prompt shown above.

**Arguments**:

- `config` - Guardrail model configuration dict.
- `backend` - ``StorageBackend`` instance (forwarded to ``create_router``).

#### check

```python
def check(text: str) -> GuardrailResult
```

Send *text* to the guardrail model and parse its verdict.

**Returns**:

  :class:`GuardrailResult` with structured safety information.
  On any router error the guardrail **fails open** (``is_safe=True``)
  and logs a warning so that a misconfigured guardrail does not
  silently block all traffic.

#### create\_guardrail\_from\_config

```python
def create_guardrail_from_config(config: Dict[str, Any],
                                 backend: Any) -> BaseGuardrail
```

Build a :class:`BaseGuardrail` from a configuration dictionary.

Currently only :class:`LLMGuardrail` is supported.

**Arguments**:

- `config` - Guardrail config dict (same fields as router config plus
  optional ``system_prompt``).
- `backend` - ``StorageBackend`` instance forwarded to the guardrail.
  

**Returns**:

  A ready-to-use :class:`BaseGuardrail` instance.

