---
sidebar_label: prompts
title: hackagent.attacks.techniques.mml.prompts
---

Prompt templates for the MML attack.

Contains the textual prompts that accompany the encoded images, instructing
the Vision-Language Model to decode and act on the visual content.

Based on the prompt templates from:
    Wang et al., &quot;Jailbreak Large Vision-Language Models Through Multi-Modal
    Linkage&quot; (2024) — https://arxiv.org/abs/2412.00473

#### get\_prompt\_template

```python
def get_prompt_template(encoding_mode: str, prompt_style: str) -> str
```

Retrieve the appropriate prompt template for the given mode and style.

**Arguments**:

- `encoding_mode` - One of &quot;word_replacement&quot;, &quot;mirror&quot;, &quot;rotate&quot;, &quot;base64&quot;, &quot;mixed&quot;.
- `prompt_style` - One of &quot;game&quot;, &quot;control&quot;.
  

**Returns**:

  The prompt template string with format placeholders.
  

**Raises**:

- `ValueError` - If the (encoding_mode, prompt_style) combination is invalid.

