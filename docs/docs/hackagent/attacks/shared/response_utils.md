---
sidebar_label: response_utils
title: hackagent.attacks.shared.response_utils
---

Shared response extraction utilities for attack modules.

This module provides a unified helper for extracting text content from
LLM responses, eliminating the duplicated if/elif chains found across:

- pair/attack.py      (_query_attacker, _query_target_simple, _judge_response)
- static_template/generation.py  (execute_prompts)
- advprefix/generate.py   (_extract_generated_text — partial overlap)

All follow the same pattern: check for OpenAI-style .choices → check for
dict with generated_text/processed_response → fallback.

Usage:
    from hackagent.attacks.shared.response_utils import extract_response_content

    content = extract_response_content(response)
    if content is not None:
        # Process content
        ...

#### extract\_response\_content

```python
def extract_response_content(
        response: Any,
        logger: Optional[logging.Logger] = None) -> Optional[str]
```

Extract text content from an LLM response in various formats.

Handles the following response formats:
1. **OpenAI-style object** — ``response.choices[0].message.content``
2. **Dictionary** — ``response[&quot;generated_text&quot;]`` or
``response[&quot;processed_response&quot;]``
3. **String** — returned as-is
4. **None / empty** — returns None

**Arguments**:

- `response` - The raw response from an AgentRouter or LLM call.
  Can be an OpenAI ChatCompletion object, a dict from a
  custom adapter, a plain string, or None.
- `logger` - Optional logger for warnings. Falls back to module logger.
  

**Returns**:

  The extracted text content, or None if extraction failed.
  

**Example**:

  &gt;&gt;&gt; # OpenAI-style response
  &gt;&gt;&gt; content = extract_response_content(openai_response)
  &gt;&gt;&gt; # Dict-style response
  &gt;&gt;&gt; content = extract_response_content({&quot;generated_text&quot;: &quot;Hello!&quot;})
  &gt;&gt;&gt; # Plain string
  &gt;&gt;&gt; content = extract_response_content(&quot;Hello!&quot;)

#### is\_guardrail\_response

```python
def is_guardrail_response(response: Any) -> bool
```

Return True if *response* is a guardrail-blocked response.

Detection is based on ``adapter_type == &quot;guardrail&quot;`` which the router
sets on every blocked response.  This is the single canonical check —
all attack modules should use this instead of ad-hoc key lookups.

#### get\_guardrail\_info

```python
def get_guardrail_info(response: Dict[str, Any]) -> Dict[str, Any]
```

Extract guardrail metadata from a blocked response.

Returns a dict with ``side``, ``message``, ``categories``, and
``reasoning`` when available, or an empty dict if not a guardrail
response.

