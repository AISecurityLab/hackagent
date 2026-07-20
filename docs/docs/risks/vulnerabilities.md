---
sidebar_position: 3
sidebar_label: Vulnerabilities
title: Vulnerabilities
---

# Vulnerabilities

HackAgent ships with **13 built-in vulnerability classes** covering the input, model, data, and agent layers of an AI system. Each one extends `BaseVulnerability` (`hackagent.risks.base`), defines an `Enum` of testable sub-types, and has a matching [threat profile](./threat-profiles.md) with recommended datasets, attack techniques, and metrics.

See [Vulnerability Categories](./risk-categories.mdx) for how these 13 classes map onto attack-surface layers.

## Reference

| Vulnerability | Description |
|---|---|
| [Jailbreak](./vulnerabilities/jailbreak.md) | Tests whether the LLM can be manipulated into bypassing its safety filters through roleplay, encoding, multi-turn, hypothetical, or authority-manipulation techniques. |
| [Prompt Injection](./vulnerabilities/prompt-injection.md) | Tests whether the LLM executes attacker-supplied instructions that override or bypass the system prompt. |
| [System Prompt Leakage](./vulnerabilities/system-prompt-leakage.md) | Tests whether the LLM reveals sensitive details from its system prompt, such as credentials, internal instructions, or guardrails. |
| [Input Manipulation Attack](./vulnerabilities/input-manipulation-attack.md) | Tests whether encoding bypasses, format string attacks, or Unicode manipulation can evade input validation and safety filters. |
| [Model Evasion](./vulnerabilities/model-evasion.md) | Tests whether adversarial examples, feature manipulation, or boundary exploitation can evade the model's safety mechanisms. |
| [Craft Adversarial Data](./vulnerabilities/craft-adversarial-data.md) | Tests whether adversarially crafted data — perturbations, poisoned examples, or augmentation abuse — can compromise model behaviour. |
| [Sensitive Information Disclosure](./vulnerabilities/sensitive-information-disclosure.md) | Tests for training-data extraction, architecture disclosure, and configuration leakage. |
| [Misinformation](./vulnerabilities/misinformation.md) | Tests whether the LLM produces factual fabrications, invented sources, or misrepresented expertise. |
| [Excessive Agency](./vulnerabilities/excessive-agency.md) | Tests whether the LLM performs actions or grants permissions exceeding its intended scope without oversight. |
| [Malicious Tool Invocation](./vulnerabilities/malicious-tool-invocation.md) | Tests for risks from untrusted tool execution, data exfiltration through tool interactions, and tool privilege escalation. |
| [Credential Exposure](./vulnerabilities/credential-exposure.md) | Tests for hardcoded credentials, token leakage, and misconfigured access controls in AI systems. |
| [Public-Facing Application Exploitation](./vulnerabilities/public-facing-application-exploitation.md) | Tests whether publicly exposed AI APIs, web interfaces, or endpoints can be abused or exploited beyond intended use. |
| [Vector and Embedding Weaknesses Exploit](./vulnerabilities/vector-embedding-weaknesses-exploit.md) | Tests for embedding inversion, vector database poisoning, and similarity search manipulation in RAG pipelines. |

## Using a Vulnerability

```python
from hackagent.risks import Jailbreak
from hackagent.risks.jailbreak.types import JailbreakType

# Use all sub-types
vuln = Jailbreak()

# Or specify particular sub-types
vuln = Jailbreak(types=[
    JailbreakType.ROLEPLAY.value,
    JailbreakType.MULTI_TURN.value,
])
```

Don't see a category that fits your use case? See [Custom Vulnerabilities](./custom-vulnerabilities.md) to define your own.

## Learn More

- **[Threat Profiles](./threat-profiles.md)** — Recommended datasets, attacks, and metrics for each vulnerability
- **[Evaluation Campaigns](./evaluation-campaigns.md)** — Build complete evaluation workflows
- **[Indirect Injection](./indirect-prompt-injection.md)** — Dedicated RAG context-poisoning scenario
