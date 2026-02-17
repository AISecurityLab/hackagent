---
sidebar_position: 3
---

# Fairness (F)

**Code:** `F` · **Enum:** `RiskCategory.FAIRNESS` · **Vulnerabilities:** 3

Covers threats where AI systems produce discriminatory, biased, or toxic outputs that harm specific groups.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **Bias** | Racial, gender, religious, and political bias | race, gender, religion, politics |
| **Fairness** | Stereotyping, subgroup impact, bias drift | stereotyping, subgroup_impact, bias_drift, inconsistent_treatment |
| **Toxicity** | Insults, profanity, threats, and mockery | insults, profanity, threats, mockery |

## Recommended Datasets

| Preset | Relevance | Description |
|--------|:---------:|-------------|
| **discrim_eval** | Primary | 9.4K decision prompts testing discrimination (Anthropic) |
| **donotanswer** | Primary/Secondary | 939 refusal questions including bias / toxicity triggers |
| **toxicchat** | Primary | 10K real user prompts with toxicity annotations (lmsys) |
| **beavertails** | Secondary | 330K+ QA pairs — includes Discrimination/Stereotype category |
| **coconot** | Secondary | Context-conditioned prompts useful for bias detection |
| **strongreject** | Secondary | Forbidden prompts that may trigger toxic responses |

:::info Key Datasets
**discrim_eval** (9.4K Anthropic decision prompts) is the primary dataset for bias and fairness testing. **toxicchat** (10K real user prompts) and **donotanswer** are primary for toxicity.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.FAIRNESS)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
