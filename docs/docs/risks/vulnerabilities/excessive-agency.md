---
sidebar_position: 9
---

# Excessive Agency

Tests whether the LLM performs actions or grants permissions exceeding its intended scope without oversight.

## Sub-types

- **Functionality**: Model performs actions beyond its intended scope.
- **Permissions**: Model grants or exercises permissions it should not have.
- **Autonomy**: Model acts autonomously without required human oversight.

## Threat Profile

**Objective**: policy_violation

**Recommended Datasets**:
- **agentharm** (PRIMARY): AgentHarm dataset for evaluating excessive agency in tool use
- **agentharm_benign** (SECONDARY): Benign agent scenarios to establish baseline behavior

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt construction

**Metrics**: asr, judge_score

## Usage Example

```python
from hackagent.risks import ExcessiveAgency
from hackagent.risks.excessive_agency.types import ExcessiveAgencyType

# Use all sub-types
vuln = ExcessiveAgency()

# Or specify particular sub-types
vuln = ExcessiveAgency(types=[
    ExcessiveAgencyType.FUNCTIONALITY.value,
    ExcessiveAgencyType.AUTONOMY.value,
])
```
