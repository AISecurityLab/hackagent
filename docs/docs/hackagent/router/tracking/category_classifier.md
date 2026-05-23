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

