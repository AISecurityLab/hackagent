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

When the target system uses retrieval, add an indirect prompt injection campaign to measure exposure to poisoned knowledge-base content:

- Recommended technique: `rag`
- Focus metric: `asr` with retrieval-hit diagnostics
- Suggested tuning baseline: `chunk_size=1400`, `chunk_overlap=250`, `top_k=5`

## Threat Profile

**Objective**: `jailbreak`

### Recommended Datasets

**Primary**
- **advbench**: 520 adversarial goals covering injection scenarios
- **harmbench_contextual**: Contextual prompts requiring instruction override
- **prompt_injections**: 662 prompt injection samples for direct PI testing (deepset)

**Secondary**
- **strongreject**: Forbidden prompts to test injection guardrails

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery
- **RAG Attack**: Indirect Injection through document poisoning in RAG pipelines

**Secondary**
- **AdvPrefix**: Adversarial prefix optimisation

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

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

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.prompt_injection import PROMPT_INJECTION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in PROMPT_INJECTION_PROFILE.primary_attacks:
    for dataset in PROMPT_INJECTION_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": PROMPT_INJECTION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
