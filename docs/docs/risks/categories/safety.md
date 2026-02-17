---
sidebar_position: 5
---

# Safety (S)

**Code:** `S` · **Enum:** `RiskCategory.SAFETY` · **Vulnerabilities:** 4

Covers threats where AI systems generate content that could cause real-world harm — from criminal planning to graphic violence.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **IllegalActivity** | Criminal planning, weapons, drug production, fraud/scam | criminal_planning, weapons, drugs, fraud |
| **GraphicContent** | Violence, sexual content, self-harm generation | violence, sexual, self_harm |
| **PersonalSafety** | Dangerous instructions, stalking/harassment, child exploitation | dangerous_instructions, stalking, child_exploitation |
| **AutonomousOversight** | Missing human override, unmonitored actions, cascading failures | missing_override, unmonitored, cascading |

## Recommended Datasets

| Preset | Relevance | Description |
|--------|:---------:|-------------|
| **harmbench** | Primary | 200 harmful behaviour prompts (criminal, graphic, safety) |
| **strongreject** | Primary | 324 forbidden prompts (illegal content, violence) |
| **beavertails** | Primary | 330K+ QA pairs — 14 harm categories incl. violence, drugs |
| **saladbench** | Primary | 21K questions — hierarchical safety taxonomy |
| **simplesafetytests** | Primary/Secondary | 100 clear-cut harmful prompts for safety baseline |
| **wmdp_bio** | Primary | Biosecurity hazardous knowledge |
| **wmdp_chem** | Primary | Chemistry hazardous knowledge |
| **agentharm** | Primary | 176+ harmful agentic tasks (autonomous oversight) |
| **harmfulqa** | Secondary | 1,960 harmful questions across 10 domains |
| **advbench** | Secondary | 520 broad adversarial goals including illegal scenarios |
| **toxicchat** | Secondary | 10K real user prompts with toxicity annotations |

:::info Dataset Coverage
Safety has the richest dataset coverage of any risk category. **IllegalActivity** alone maps to 9 recommended datasets.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.SAFETY)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
