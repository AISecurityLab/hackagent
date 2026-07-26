---
sidebar_position: 2
---

# Jailbreak

Tests whether the LLM can be manipulated into bypassing its safety filters through roleplay, encoding, multi-turn, hypothetical, or authority-manipulation techniques.

## Sub-types

- **Roleplay**: Uses fictional scenarios or personas to bypass safety filters.
- **Encoding**: Encodes malicious intent via Base64, ROT13, leetspeak, etc.
- **Multi-Turn**: Gradually escalates across conversation turns (crescendo).
- **Hypothetical**: Frames harmful requests as hypothetical or academic questions.
- **Authority Manipulation**: Invokes false authority or urgency to override restrictions.

## Threat Profile

**Objective**: `jailbreak`

### Recommended Datasets

**Primary**
- **strongreject**: 324 forbidden prompts designed for jailbreak evaluation
- **harmbench**: 200 harmful behaviors for bypass testing
- **advbench**: 520 adversarial goals for jailbreak attacks
- **jailbreakbench**: 100 curated misuse behaviours from NeurIPS 2024 benchmark

**Secondary**
- **simplesafetytests**: 100 clear-cut harmful prompts as baseline
- **donotanswer**: 939 refusal questions for comprehensive coverage
- **saladbench_attack**: 5K attack-enhanced prompts with jailbreak methods

### Attack Techniques

**Primary**
- **h4rm3l**: Composable decorator-chain jailbreak for fast high-yield probing
- **TAP**: Tree-search jailbreak with pruning for efficient discovery
- **PAIR**: Iterative attacker-guided refinement for adaptive bypass

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

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

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.jailbreak import JAILBREAK_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in JAILBREAK_PROFILE.primary_attacks:
    for dataset in JAILBREAK_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": attack.technique.lower(),
            "objective": JAILBREAK_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
