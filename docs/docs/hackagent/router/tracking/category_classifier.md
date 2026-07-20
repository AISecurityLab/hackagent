---
sidebar_label: category_classifier
title: hackagent.router.tracking.category_classifier
---

Goal-level category classification utilities for Tracker.

## GoalCategoryClassifier Objects

```python
class GoalCategoryClassifier()
```

Classifies a goal into (category, subcategory) using a configured LLM.

#### classify\_goal

```python
def classify_goal(goal: str) -> Dict[str, str]
```

Return normalized category labels for a single goal.

#### classify\_goals

```python
def classify_goals(goals: List[str]) -> Dict[int, Dict[str, str]]
```

Classify many goals using as few LLM calls as possible.

Returns a ``{index: {&quot;category&quot;, &quot;subcategory&quot;}}`` map covering every
index in ``range(len(goals))``. Goals resolved by the deterministic
heuristic cost nothing; the remainder are sent to the LLM in chunks
(one request per ``_BATCH_CHUNK_SIZE`` goals) instead of one per goal.
Any goal that cannot be classified falls back to the UNKNOWN labels.

