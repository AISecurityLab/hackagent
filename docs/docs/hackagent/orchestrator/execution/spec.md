---
sidebar_label: spec
title: hackagent.orchestrator.execution.spec
---

Run-level options that do not belong on :class:`AttackConfig`.

Goal source, batching, output directory, resume step and re-judge live here
so technique configs stay limited to algorithm params and role fields.

## RunSpec Objects

```python
class RunSpec(BaseModel)
```

Orchestrator-owned run bookkeeping and scheduling knobs.

