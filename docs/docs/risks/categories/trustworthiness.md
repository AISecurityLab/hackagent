---
sidebar_position: 4
---

# Trustworthiness (VAR)

**Code:** `VAR` · **Enum:** `RiskCategory.VALIDITY_ACCURACY_ROBUSTNESS` · **Vulnerabilities:** 4

Covers threats to model reliability — factual accuracy, resistance to manipulation, and appropriate levels of autonomy.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **Hallucination** | Factual fabrication, source fabrication, context hallucination | factual, source, context |
| **Misinformation** | Factual errors, unsupported claims, expertise misrepresentation | factual_errors, unsupported_claims, expertise_misrepresentation |
| **Robustness** | Input over-reliance, hijacking, adversarial perturbation | over_reliance, hijacking, perturbation |
| **ExcessiveAgency** | Excess functionality, permissions, and autonomy | excess_functionality, excess_permissions, excess_autonomy |

## Recommended Datasets

| Preset | Relevance | Description |
|--------|:---------:|-------------|
| **truthfulqa** | Primary | Questions designed to detect hallucinated / false answers |
| **xstest** | Primary | Over-refusal evaluation for robustness testing |
| **coconot** | Primary | Context-conditioned refusal for adversarial perturbation |
| **agentharm** | Primary | 176+ harmful agentic tasks testing excessive autonomy |
| **agentharm_benign** | Secondary | Benign agentic tasks for baseline comparison |
| **advbench** | Secondary | Adversarial goals for input manipulation testing |
| **saladbench** | Secondary | 21K questions — includes Misinformation Harms taxonomy |

:::info Key Datasets
**truthfulqa** is the primary benchmark for hallucination and misinformation. **xstest** and **coconot** test robustness. **agentharm** tests excessive agency in agentic systems.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.VALIDITY_ACCURACY_ROBUSTNESS)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
