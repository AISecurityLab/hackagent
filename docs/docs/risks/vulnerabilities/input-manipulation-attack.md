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

**Objective**: jailbreak

**Recommended Datasets**:
- **wmdp_cyber** (SECONDARY): Cybersecurity knowledge covering SQL injection and command injection techniques

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt injection
- PAIR (PRIMARY): Iterative refinement for bypass discovery
- AdvPrefix (SECONDARY): Adversarial prefix optimisation

**Metrics**: asr, judge_score

## Usage Example

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
