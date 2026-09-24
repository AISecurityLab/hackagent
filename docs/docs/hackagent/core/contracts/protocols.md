---
sidebar_label: protocols
title: hackagent.core.contracts.protocols
---

Protocols for callable models.

## LLM Objects

```python
@runtime_checkable
class LLM(Protocol)
```

A callable model. Calls never raise for provider errors.

## LLMFactory Objects

```python
@runtime_checkable
class LLMFactory(Protocol)
```

Builds the LLM for a role model.

