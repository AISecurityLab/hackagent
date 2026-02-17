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

**Objective**: jailbreak

**Recommended Datasets**:
- **strongreject** (PRIMARY): 324 forbidden prompts designed for jailbreak evaluation
- **harmbench** (PRIMARY): 200 harmful behaviors for bypass testing
- **advbench** (PRIMARY): 520 adversarial goals for jailbreak attacks
- **jailbreakbench** (PRIMARY): 100 curated misuse behaviours from NeurIPS 2024 benchmark
- **simplesafetytests** (SECONDARY): 100 clear-cut harmful prompts as baseline
- **donotanswer** (SECONDARY): 939 refusal questions for comprehensive coverage
- **saladbench_attack** (SECONDARY): 5K attack-enhanced prompts with jailbreak methods

**Attack Techniques**:
- Baseline (PRIMARY): Template-based attack
- PAIR (PRIMARY): Iterative refinement
- AdvPrefix (PRIMARY): Adversarial prefix optimisation

**Metrics**: asr, judge_score

## Usage Example

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
