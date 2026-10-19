---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.autodan_turbo.config
---

Configuration for AutoDAN-Turbo.

## AutoDANTurboParams Objects

```python
class AutoDANTurboParams(AttackParams)
```

How long the search runs, and the three models it learns with.

`attacker` explores and crafts prompts; `summarizer` distils what
worked into named strategies; `embedder` indexes those strategies by
the responses they beat so they can be retrieved. All three are required.
The judge is the campaign panel, whose score drives the search and whose
`break_score` ends it.

