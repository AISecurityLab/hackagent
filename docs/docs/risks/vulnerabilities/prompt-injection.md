---
sidebar_position: 1
---

# Prompt Injection

Tests whether the LLM executes attacker-supplied instructions that override or bypass the system prompt.

## Sub-types

- **Direct Injection**: User prompt directly overrides system instructions.
- **Indirect Injection**: Malicious instructions are embedded in retrieved/external content.
- **Context Manipulation**: Crafted context tricks the model into ignoring guardrails.

## Threat Profile

**Objective**: jailbreak

**Recommended Datasets**:
- **advbench** (PRIMARY): 520 adversarial goals covering injection scenarios
- **harmbench_contextual** (PRIMARY): Contextual prompts requiring instruction override
- **prompt_injections** (PRIMARY): 662 prompt injection samples for direct PI testing (deepset)
- **strongreject** (SECONDARY): Forbidden prompts to test injection guardrails

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt injection
- PAIR (PRIMARY): Iterative refinement for bypass discovery
- AdvPrefix (SECONDARY): Adversarial prefix optimisation

**Metrics**: asr, judge_score

## Usage Example

```python
from hackagent.risks import PromptInjection
from hackagent.risks.prompt_injection.types import PromptInjectionType

# Use all sub-types
vuln = PromptInjection()

# Or specify particular sub-types
vuln = PromptInjection(types=[
    PromptInjectionType.DIRECT_INJECTION.value,
    PromptInjectionType.INDIRECT_INJECTION.value,
])
```
