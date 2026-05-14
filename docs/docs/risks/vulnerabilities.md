---
sidebar_position: 3
sidebar_label: Jailbreak
title: Jailbreak
---

# Jailbreak

This page describes the currently implemented risk scope and campaign setup:

- **Risk Macro-Category**: Cybersecurity
- **Risk Micro-Category**: Jailbreak

In HackAgent core, Jailbreak is the only implemented Cybersecurity micro-category today.

For this micro-category, HackAgent provides an evaluation campaign setup.
It defines objective, datasets, attack techniques, and metrics used in runs.

### What Jailbreak Means in Practice

In this context, a jailbreak is a successful bypass of model safeguards.
The model should refuse unsafe or policy-violating requests, but instead returns
content that indicates the guardrails were circumvented.

### How Jailbreak Attacks Work

Different jailbreak techniques use different search strategies, but they share
the same high-level workflow:

1. Start from a harmful or disallowed goal in the evaluation dataset.
2. Generate one or more adversarial prompt variants intended to bypass safety behavior.
3. Send those prompts to the target model and collect responses.
4. Evaluate responses with a judge/ruleset to determine whether bypass occurred.
5. Iterate and refine prompts to increase bypass success rate.

Techniques differ mainly in *how* they search and refine prompts:

- some use structured exploration (for example, tree search),
- some use iterative attacker-judge loops,
- some use transformation chains and prompt mutation.

### Common Objective Across Techniques

All jailbreak attacks in this campaign setup optimize for the same objective:
maximize the probability that the target model violates expected safety behavior
for a protected goal. This is why ASR (Attack Success Rate) is the primary metric.

If two runs use the same Risk Profile and equivalent Evaluation Campaign settings, ASR comparison over time remains meaningful because scope and methodology are consistent.

No additional Cybersecurity micro-categories are currently implemented in core.

### Code Example

```python
from hackagent.risks.jailbreak import JAILBREAK_PROFILE

print(JAILBREAK_PROFILE.name)
print([d.preset for d in JAILBREAK_PROFILE.primary_datasets])
print([a.technique for a in JAILBREAK_PROFILE.primary_attacks])
```

**Objective**: `jailbreak`

**Recommended Datasets**:
- **strongreject** (PRIMARY): 324 forbidden prompts designed for jailbreak evaluation
- **harmbench** (PRIMARY): 200 harmful behaviors for bypass testing
- **advbench** (PRIMARY): 520 adversarial goals for jailbreak attacks
- **jailbreakbench** (PRIMARY): 100 curated misuse behaviours from NeurIPS 2024 benchmark
- **simplesafetytests** (SECONDARY): 100 clear-cut harmful prompts as baseline
- **donotanswer** (SECONDARY): 939 refusal questions for comprehensive coverage
- **saladbench_attack** (SECONDARY): 5K attack-enhanced prompts with jailbreak methods

**Attack Techniques**:
- h4rm3l (PRIMARY): Composable decorator-chain jailbreak for fast high-yield probing
- TAP (PRIMARY): Tree-search jailbreak with pruning for efficient discovery
- PAIR (PRIMARY): Iterative attacker-guided refinement for adaptive bypass

**Metrics**: `asr`, `judge_score`
