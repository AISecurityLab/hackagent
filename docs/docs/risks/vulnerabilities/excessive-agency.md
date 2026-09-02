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

**Objective**: `policy_violation`

:::note Objective vs. goals
The `objective` above selects the **scoring rubric** for a run — it is one of a
fixed set of built-in names, not something you write. The `goals` you pass to an
attack are separate free-text strings that you author yourself. See
[Goals vs. objective](../../attacks/index.mdx#goals-vs-objective).
:::

### Recommended Datasets

**Primary**
- **agentharm**: AgentHarm dataset for evaluating excessive agency in tool use

**Secondary**
- **agentharm_benign**: Benign agent scenarios to establish baseline behavior

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt construction

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

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

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.excessive_agency import EXCESSIVE_AGENCY_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in EXCESSIVE_AGENCY_PROFILE.primary_attacks:
    for dataset in EXCESSIVE_AGENCY_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": "static_template",  # attack.technique is "StaticTemplate"
            "objective": EXCESSIVE_AGENCY_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
