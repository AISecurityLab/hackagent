---
sidebar_label: goals
title: hackagent.datasets.goals
---

Resolve attack goal sources into typed ``Goal`` values.

#### resolve\_goals

```python
def resolve_goals(*,
                  goals: Optional[Any] = None,
                  dataset: Optional[Any] = None,
                  intents: Optional[Any] = None) -> list[Goal]
```

Resolve explicit goals, intents, or a dataset into typed ``Goal`` values.

Precedence is ``goals`` &gt; ``intents`` &gt; ``dataset``. When more than one
source is provided, a single warning names the ignored sources and the
winner is used.

