---
sidebar_position: 7
---

# Third-Party Management (TPM)

**Code:** `TPM` · **Enum:** `RiskCategory.THIRD_PARTY_MANAGEMENT` · **Vulnerabilities:** 2

Covers threats arising from intellectual property violations and anti-competitive behavior in AI outputs.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **IntellectualProperty** | Copyright violations, trademark infringement, imitation | copyright, trademark, imitation, trade_secret |
| **Competition** | Competitor denigration, market manipulation, strategy leaks | denigration, market_manipulation, strategy_leak |

## Recommended Datasets

:::note
Both IntellectualProperty and Competition currently have **no standard public dataset** and require custom goals for evaluation.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.THIRD_PARTY_MANAGEMENT)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
