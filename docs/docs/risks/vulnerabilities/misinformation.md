---
sidebar_position: 8
---

# Misinformation

Tests whether the LLM produces factual fabrications, invented sources, or misrepresented expertise.

## Sub-types

- **Factual Fabrication**: Model fabricates facts, statistics, or events that never occurred.
- **Source Fabrication**: Model invents citations, references, or sources that do not exist.
- **Expertise Misrepresentation**: Model presents itself as having expertise or authority it lacks.

## Threat Profile

**Objective**: `harmful_behavior`

### Recommended Datasets

**Primary**
- **truthfulqa**: TruthfulQA for evaluating factual accuracy and misinformation

**Secondary**
- **saladbench**: SaladBench for broader misinformation coverage

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt construction

### Metrics

- truthfulness_score
- accuracy_score

## Usage

### Instantiate the Vulnerability

```python
from hackagent.risks import Misinformation
from hackagent.risks.misinformation.types import MisinformationType

# Use all sub-types
vuln = Misinformation()

# Or specify particular sub-types
vuln = Misinformation(types=[
    MisinformationType.FACTUAL_FABRICATION.value,
    MisinformationType.SOURCE_FABRICATION.value,
])
```

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.misinformation import MISINFORMATION_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Use profile recommendations
for attack in MISINFORMATION_PROFILE.primary_attacks:
    for dataset in MISINFORMATION_PROFILE.primary_datasets:
        attack_config = {
            "attack_type": "static_template",  # attack.technique is "StaticTemplate"
            "objective": MISINFORMATION_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
