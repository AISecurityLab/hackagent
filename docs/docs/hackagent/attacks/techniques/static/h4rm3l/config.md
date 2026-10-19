---
sidebar_label: config
title: hackagent.attacks.techniques.static.h4rm3l.config
---

Configuration for h4rm3l.

## H4rm3lParams Objects

```python
class H4rm3lParams(AttackParams)
```

A decorator program and the model its LLM-assisted decorators use.

`program` is a preset name from :data:`~.programs.PRESET_PROGRAMS` or
a raw program. `decorator` is a role: it is needed only when the
program contains an LLM-assisted decorator such as `TranslateDecorator`.

