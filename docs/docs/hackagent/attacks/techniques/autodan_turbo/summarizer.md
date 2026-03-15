---
sidebar_label: summarizer
title: hackagent.attacks.techniques.autodan_turbo.summarizer
---

Strategy summarizer — mirrors original summarizer.py (summarize + wrapper).

#### summarize\_strategy

```python
def summarize_strategy(router,
                       key,
                       request,
                       weak_prompt,
                       strong_prompt,
                       library,
                       logger,
                       max_retries=5,
                       summarizer_max_tokens=512,
                       role_label="summarizer")
```

Summarize why a stronger prompt outperforms a weaker one.

Paper mapping: this is the Summarizer LLM component. It compares
weak/strong prompt pairs and extracts a reusable jailbreak strategy via a
second wrapper pass that enforces structured JSON output.

**Arguments**:

- `router` - Router bound to summarizer model.
- `key` - Registration key for summarizer route.
- `request` - Original attack goal used for prompt context.
- `weak_prompt` - Lower-scoring prompt candidate.
- `strong_prompt` - Higher-scoring prompt candidate.
- `library` - Existing strategy pool for duplicate-aware summarization.
- `logger` - Logger for summarization diagnostics.
- `max_retries` - Maximum attempts for valid strategy extraction.
- `role_label` - Log role label.
  

**Returns**:

  Dictionary with at least ``Strategy`` and ``Definition`` on success,
  else ``None`` when extraction fails.

