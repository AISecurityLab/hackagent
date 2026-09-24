---
sidebar_label: response
title: hackagent.attacks._lib.response
---

Response helpers for attack modules.

Prefer :class:`~hackagent.core.contracts.Completion` properties
(`text`, `ok`, `blocked`, `guardrail_info`). These helpers keep
legacy envelope/dict and OpenAI-style objects working until every
technique calls `LLM.complete`.

#### extract\_response\_content

```python
def extract_response_content(
        response: Any,
        logger: Optional[logging.Logger] = None) -> Optional[str]
```

Extract text content from a Completion or legacy LLM response.

#### is\_guardrail\_response

```python
def is_guardrail_response(response: Any) -> bool
```

Return True if *response* is a guardrail-blocked response.

#### get\_guardrail\_info

```python
def get_guardrail_info(response: Any) -> Dict[str, Any]
```

Extract guardrail metadata from a blocked response.

