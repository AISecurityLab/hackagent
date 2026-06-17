---
sidebar_position: 1
---

# Prompt Injection

Tests whether the LLM executes attacker-supplied instructions that override or bypass the system prompt.

## Sub-types

- **Direct Injection**: User prompt directly overrides system instructions.
- **Indirect Injection**: Malicious instructions are embedded in retrieved/external content.
- **Context Manipulation**: Crafted context tricks the model into ignoring guardrails.

## Indirect Injection

Indirect prompt injection is especially relevant for RAG-enabled systems where the user query is benign but retrieved context is adversarial.

- Attack vector: poisoned KB documents that inject hidden instructions into retrieved chunks.
- Typical effect: the model follows malicious context instructions while appearing to answer normally.
- Why it is hard to catch: user prompts look harmless, and filtering only user input is not enough.

For an end-to-end evaluation workflow (poisoning, retrieval, judging), see [RAG Attack](../../attacks/rag.md) using `attack_type="rag"`.

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
- RAG Attack (PRIMARY): Indirect Injection through document poisoning in RAG pipelines
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
