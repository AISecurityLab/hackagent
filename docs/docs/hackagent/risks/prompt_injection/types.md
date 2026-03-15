---
sidebar_label: types
title: hackagent.risks.prompt_injection.types
---

Prompt Injection sub-types.

## PromptInjectionType Objects

```python
class PromptInjectionType(Enum)
```

Sub-types for Prompt Injection.

#### DIRECT\_INJECTION

User prompt directly overrides system instructions.

#### INDIRECT\_INJECTION

Malicious instructions are embedded in retrieved/external content.

#### CONTEXT\_MANIPULATION

Crafted context tricks the model into ignoring guardrails.

