---
sidebar_label: logging
title: hackagent.core.logging
---

Logger access for library code.

Library modules only obtain loggers; they never install handlers or set
levels. Handler configuration belongs to the application (the CLI does it in
:mod:`hackagent.interfaces.cli.logging_setup`).

#### get\_logger

```python
def get_logger(name: str) -> logging.Logger
```

Return the logger called `name` without configuring it.

