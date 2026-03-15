---
sidebar_label: profile_helpers
title: hackagent.risks.profile_helpers
---

Shared shorthand helpers for building threat profiles.

These are intentionally private but shared across all threat profile modules.

#### ds

```python
def ds(preset: str,
       relevance: Relevance = PRIMARY,
       rationale: str = "") -> DatasetRecommendation
```

Create a DatasetRecommendation.

#### atk

```python
def atk(technique: str,
        relevance: Relevance = PRIMARY,
        rationale: str = "") -> AttackRecommendation
```

Create an AttackRecommendation.

