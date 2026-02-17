---
sidebar_position: 6
---

# Transparency & Explainability (OT/EI)

**Code:** `OT` / `EI` · **Enum:** `RiskCategory.OPERABILITY_TRANSPARENCY` / `RiskCategory.EXPLAINABILITY_INTERPRETABILITY` · **Vulnerabilities:** 2

Covers threats where AI systems fail to adequately disclose their nature, reasoning, or limitations.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **Transparency** | Insufficient disclosure, missing provenance, policy violations | insufficient_disclosure, missing_provenance, hidden_limitations, no_ai_disclosure, policy_violation |
| **Explainability** | Opaque decisions, meaningless explanations, confidence erosion | opaque_decisions, meaningless_explanations, no_uncertainty, selective_explanations, confidence_erosion |

## Recommended Datasets

:::note
Both Transparency and Explainability currently have **no standard public dataset** and require custom goals for evaluation.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.OPERABILITY_TRANSPARENCY)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
