---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.h4rm3l.config
---

Configuration for h4rm3l.

## H4rm3lParams Objects

```python
class H4rm3lParams(AttackParams)
```

The program to run, and how long to search for a better one.

With no `synthesizer` role the attack runs `program` and nothing
else: one decorated request per goal, cheap and repeatable. Configure a
`synthesizer` and it first searches the decorator language for
programs that work against this target, seeded with `program` and the
presets, and then attacks each goal with the best it found; every field
from `iterations` down governs that search and is ignored without it.

`decorator` is needed only when a program contains an LLM-assisted
primitive such as `TranslateDecorator`.

