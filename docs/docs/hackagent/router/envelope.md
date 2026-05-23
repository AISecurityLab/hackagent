---
sidebar_label: envelope
title: hackagent.router.envelope
---

Envelope helpers — pure functions that translate between LiteLLM&#x27;s
``ModelResponse`` and HackAgent&#x27;s standardized response dict.

This module exists as the Phase A landing zone of the
``LITELLM_ROUTER_REFACTOR_PLAN.md`` plan: extract the response-shaping
logic out of the adapter classes so it can be reused by
``AgentRouter`` once the call path is hoisted in Phase C.

The functions here are intentionally:
- pure: no I/O, no logging side effects, no LiteLLM imports at module
  level. Any LiteLLM import lives behind a lazy helper.
- agnostic of agent identity: the caller supplies ``agent_id`` and
  ``adapter_type`` as keyword arguments.
- byte-compatible with the previous adapter envelope, so downstream
  consumers (``StepTracker``, attacks, evaluators, dashboard) keep
  seeing exactly the same dict shape.

#### strip\_think\_prefix

```python
def strip_think_prefix(text: str) -> str
```

Strip hidden reasoning prefix up to and including ``&lt;/think&gt;`` if present.

#### extract\_text\_from\_response

```python
def extract_text_from_response(response: Any, *, model_name: str = "") -> str
```

Pull the assistant text out of a LiteLLM ``ModelResponse``.

Falls back to ``reasoning_content`` / ``reasoning`` when ``content``
is empty so reasoning-only models still produce output. Returns a
sentinel ``[GENERATION_ERROR: ...]`` string when the response is
structurally unusable, mirroring the previous adapter behaviour.

#### extract\_tool\_calls

```python
def extract_tool_calls(response: Any) -> Optional[List[Dict[str, Any]]]
```

Return OpenAI-style ``tool_calls`` from a ``ModelResponse``, or ``None``.

#### resolve\_litellm\_model

```python
def resolve_litellm_model(raw_model: str,
                          *,
                          provider_prefix: Optional[str] = None) -> str
```

Return the model string to pass to ``litellm.completion``.

Honors a caller-supplied ``provider_prefix`` while leaving names that
already carry an explicit LiteLLM provider prefix untouched.

#### build\_litellm\_kwargs

```python
def build_litellm_kwargs(
        *,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        tools: Optional[Any] = None,
        tool_choice: Optional[Any] = None,
        extra_body: Optional[Any] = None,
        thinking_payload: Optional[Dict[str, Any]] = None,
        extra_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
```

Build the kwargs dict for ``litellm.completion``.

``thinking_payload`` is the *already-translated* per-provider dict
(e.g. ``{&quot;reasoning_effort&quot;: &quot;medium&quot;}`` or ``{&quot;think&quot;: True}``);
the caller is responsible for converting the unified ``thinking``
knob into the provider-specific shape before passing it in here.
Anything in ``extra_kwargs`` is splat-merged last and wins on
collision, matching the previous adapter behaviour.

#### build\_success\_envelope

```python
def build_success_envelope(*,
                           agent_id: str,
                           adapter_type: str,
                           processed_response: Optional[str],
                           raw_request: Optional[Dict[str, Any]] = None,
                           raw_response_body: Optional[Any] = None,
                           raw_response_headers: Optional[Dict[str,
                                                               str]] = None,
                           agent_specific_data: Optional[Dict[str,
                                                              Any]] = None,
                           model_name: Optional[str] = None,
                           status_code: int = 200) -> Dict[str, Any]
```

Construct HackAgent&#x27;s standardised success-response dict.

#### build\_error\_envelope

```python
def build_error_envelope(*,
                         agent_id: str,
                         adapter_type: str,
                         error_message: str,
                         status_code: Optional[int] = None,
                         raw_request: Optional[Dict[str, Any]] = None,
                         raw_response_body: Optional[Any] = None,
                         raw_response_headers: Optional[Dict[str, str]] = None,
                         agent_specific_data: Optional[Dict[str, Any]] = None,
                         model_name: Optional[str] = None) -> Dict[str, Any]
```

Construct HackAgent&#x27;s standardised error-response dict.

#### build\_agent\_specific\_data

```python
def build_agent_specific_data(
        *,
        model_name: Optional[str],
        invoked_parameters: Dict[str, Any],
        completion_result: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
```

Build the standard ``agent_specific_data`` block shared by adapters.

#### extract\_response\_cost

```python
def extract_response_cost(response: Any) -> Optional[float]
```

Pull ``response_cost`` off a LiteLLM ``ModelResponse`` if present.

LiteLLM exposes the per-call cost (when the model is in its pricing
catalogue) via the ``_hidden_params`` attribute. Returns ``None``
when unavailable rather than raising, since cost tracking is
best-effort.

#### extract\_litellm\_call\_id

```python
def extract_litellm_call_id(response: Any) -> Optional[str]
```

Pull ``litellm_call_id`` (or ``x-litellm-call-id``) off a response.

