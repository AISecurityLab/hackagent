---
sidebar_label: base
title: hackagent.evaluation.base
---

Parse results shared by the judge types.

## AssertionResult Objects

```python
@dataclass(frozen=True)
class AssertionResult()
```

A parsed judge reply.

``is_confident`` is false when the parser had to guess. Callers may
retry once in that case.

