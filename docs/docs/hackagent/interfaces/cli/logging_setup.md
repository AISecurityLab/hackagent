---
sidebar_label: logging_setup
title: hackagent.interfaces.cli.logging_setup
---

Rich console logging for the CLI and TUI.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup.

#### setup\_package\_logging

```python
def setup_package_logging(
        logger_name: str = "hackagent",
        default_level_str: str = "WARNING") -> logging.Logger
```

Configures RichHandler for the specified logger if not already set.

#### suppress\_noisy\_libraries

```python
def suppress_noisy_libraries(*names: str) -> None
```

Silence chatty third-party loggers to WARNING.

This is opt-in so that applications embedding hackagent are not surprised
by their own library loggers being muted.

**Example**:

  &gt;&gt;&gt; from hackagent.interfaces.cli.logging_setup import suppress_noisy_libraries
  &gt;&gt;&gt; suppress_noisy_libraries(&quot;httpx&quot;, &quot;litellm&quot;, &quot;urllib3&quot;)

