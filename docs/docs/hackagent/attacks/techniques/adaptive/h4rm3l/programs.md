---
sidebar_label: programs
title: hackagent.attacks.techniques.adaptive.h4rm3l.programs
---

Named decorator programs from the h4rm3l paper, and ones measured here.

`H4rm3lParams.program` accepts either one of these names or a raw program.
They are also what the search seeds its pool with, so a program added here
is both directly runnable and a starting point synthesis can build on.

#### resolve\_program

```python
def resolve_program(program: str) -> str
```

Return the program for a preset name, or `program` unchanged.

