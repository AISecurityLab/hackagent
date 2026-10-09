---
sidebar_label: intents
title: hackagent.datasets.intents
---

Select goals from the OmniSafeBench intents by taxonomy category.

Each selected intent becomes a goal already labelled with the category and
subcategory it is filed under, so it needs no classifier.

#### intents\_of

```python
def intents_of(subcategory: str) -> tuple[str, ...]
```

The OmniSafeBench intents filed under a taxonomy subcategory.

#### load\_goals\_from\_intents\_config

```python
def load_goals_from_intents_config(
        intents_config: Any) -> Tuple[List[str], Dict[int, Dict[str, str]]]
```

Resolve an intents selection to goals and each goal&#x27;s labels.

