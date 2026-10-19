---
sidebar_label: config
title: hackagent.evaluation.config
---

Bind legacy judge specs to models as a :class:`Panel`.

#### build\_panel

```python
def build_panel(specs: Sequence[RuntimeJudgeSpec],
                models: Callable[[RuntimeJudgeSpec], CompletionModel],
                *,
                aggregation: str = DEFAULT_JUDGE_AGGREGATION,
                threshold: float = 7.0) -> Optional[Panel]
```

Bind configured judges to models, failing rather than shrinking the panel.

