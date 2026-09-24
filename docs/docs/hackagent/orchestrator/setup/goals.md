---
sidebar_label: goals
title: hackagent.orchestrator.setup.goals
---

Goal resolution and category labelling.

Resolution happens once, before the run. Category labelling is skipped when
the goals already carry category labels (intents do).

#### goals\_are\_labelled

```python
def goals_are_labelled(goals: Sequence[Goal]) -> bool
```

True when every goal already has category and subcategory labels.

#### resolve\_run\_goals

```python
def resolve_run_goals(*,
                      goals: Any = None,
                      dataset: Any = None,
                      intents: Any = None) -> List[Goal]
```

Resolve the run&#x27;s goal source into typed :class:`Goal` values.

#### label\_goals

```python
def label_goals(goals: Sequence[Goal],
                classifier: Optional[LLM] = None) -> List[Goal]
```

Attach category labels, once, unless intents already provided them.

Goals that already have both labels are left unchanged. Without a
classifier, unlabelled goals receive the unclassified placeholders.

#### labels\_by\_index

```python
def labels_by_index(goals: Sequence[Goal]) -> Dict[int, Dict[str, str]]
```

Index → `{category, subcategory}` for the tracker.

