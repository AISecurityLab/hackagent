---
sidebar_position: 2
---

# Data Privacy (DP)

**Code:** `DP` · **Enum:** `RiskCategory.DATA_PRIVACY` · **Vulnerabilities:** 3

Covers threats related to the unauthorized exposure, retention, or mishandling of personal and sensitive data.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **PIILeakage** | Direct PII disclosure, session leaks, social manipulation | direct_disclosure, session_leak, social_manipulation |
| **DataRetention** | Excessive retention, unlawful storage, failed deletion | excessive_retention, unlawful_storage, failed_deletion |
| **DataProtection** | Unencrypted transmission, weak anonymisation, access control failures | unencrypted, weak_anonymisation, access_control |

## Recommended Datasets

| Preset | Relevance | Description |
|--------|:---------:|-------------|
| **donotanswer** | Secondary | 939 refusal questions including privacy-sensitive topics |
| **beavertails** | Secondary | 330K+ QA pairs — includes "Privacy Violation" category |

:::note
DataRetention and DataProtection currently have **no standard public dataset** and require custom goals for evaluation. PIILeakage can be tested with **donotanswer** and **beavertails** datasets.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.DATA_PRIVACY)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
