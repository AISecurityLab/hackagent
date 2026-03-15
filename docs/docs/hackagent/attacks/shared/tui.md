---
sidebar_label: tui
title: hackagent.attacks.shared.tui
---

Shared TUI logging decorator.

Provides a single, lazy-loaded TUI logging decorator used by all attack
techniques. This eliminates the ~20-line copy-pasted boilerplate in each
technique&#x27;s attack.py.

Usage:
    from hackagent.attacks.shared.tui import with_tui_logging

    class MyAttack(BaseAttack):
        @with_tui_logging(logger_name=&quot;hackagent.attacks&quot;, level=logging.INFO)
        def run(self, goals):
            ...

#### with\_tui\_logging

```python
def with_tui_logging(*args, **kwargs)
```

TUI-aware logging decorator (lazy-loaded).

Wraps the real TUI logging decorator from hackagent.cli.tui.logger,
falling back to a no-op if the TUI module is not available.

**Arguments**:

  *args, **kwargs: Passed through to the real decorator.
  

**Returns**:

  Decorated function with TUI logging support.

