---
sidebar_label: prompt_parser
title: hackagent.attacks.shared.prompt_parser
---

Helpers for parsing attacker outputs into prompt data.

#### extract\_prompt\_and\_improvement

```python
def extract_prompt_and_improvement(content: str) -> Optional[Dict[str, str]]
```

Extract a prompt (+ optional improvement) from attacker output.

Supports direct JSON, JSON code blocks, regex extraction, and a
plain-text fallback when no JSON structure is present.

#### extract\_prompt

```python
def extract_prompt(content: str) -> Optional[str]
```

Extract just the prompt string from attacker output.

