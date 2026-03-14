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

**Objective**: harmful_behavior

**Recommended Datasets**:
- **truthfulqa** (PRIMARY): TruthfulQA for evaluating factual accuracy and misinformation
- **saladbench** (SECONDARY): SaladBench for broader misinformation coverage

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt construction

**Metrics**: truthfulness_score, accuracy_score

## Usage Example

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
