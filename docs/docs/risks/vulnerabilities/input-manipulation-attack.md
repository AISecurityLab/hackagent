---
sidebar_position: 3
---

# Input Manipulation Attack

Tests whether encoding bypasses, format string attacks, or Unicode manipulation can evade input validation and safety filters.

## Sub-types

- **Encoding Bypass**: Using character encoding tricks to bypass input filters.
- **Format String Attack**: Exploiting format string processing in input handling.
- **Unicode Manipulation**: Using Unicode homoglyphs or special characters to evade detection.

## Threat Profile

**Objective**: `jailbreak`

:::note Objective vs. goals
The `objective` above selects the **scoring rubric** for a run — it is one of a
fixed set of built-in names, not something you write. The `goals` you pass to an
attack are separate free-text strings that you author yourself. See
[Goals vs. objective](../../attacks/index.mdx#goals-vs-objective).
:::

### Recommended Datasets

**Secondary**
- **wmdp_cyber**: Cybersecurity knowledge covering SQL injection and command injection techniques

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

**Secondary**
- **AdvPrefix**: Adversarial prefix optimisation

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

```python
from hackagent.risks import InputManipulationAttack
from hackagent.risks.input_manipulation_attack.types import InputManipulationAttackType

# Use all sub-types
vuln = InputManipulationAttack()

# Or specify particular sub-types
vuln = InputManipulationAttack(types=[
    InputManipulationAttackType.ENCODING_BYPASS.value,
    InputManipulationAttackType.UNICODE_MANIPULATION.value,
])
```

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.input_manipulation_attack import INPUT_MANIPULATION_ATTACK_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Profile techniques use display casing (e.g. "StaticTemplate");
# HackAgent.hack() expects the registered snake_case attack_type key.
ATTACK_TYPE_KEYS = {"StaticTemplate": "static_template", "PAIR": "pair"}

# Use profile recommendations
for attack in INPUT_MANIPULATION_ATTACK_PROFILE.primary_attacks:
    for dataset in INPUT_MANIPULATION_ATTACK_PROFILE.primary_datasets + INPUT_MANIPULATION_ATTACK_PROFILE.secondary_datasets:
        attack_config = {
            "attack_type": ATTACK_TYPE_KEYS[attack.technique],
            "objective": INPUT_MANIPULATION_ATTACK_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
