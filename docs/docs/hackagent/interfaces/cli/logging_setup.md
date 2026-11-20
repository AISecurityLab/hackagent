---
sidebar_label: logging_setup
title: hackagent.interfaces.cli.logging_setup
---

Rich console logging for the CLI and TUI.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup, and :func:`apply_verbosity`
once the `-v` count is known.

Records of the attack trace (:data:`hackagent.core.logging.TRACE_LOGGER`)
are drawn from their fields rather than their message: a coloured tag per
attack and goal, indented like the search tree, with the role of each call,
verdicts coloured like the dashboard, and quoted text that is never read as
markup.

#### render\_trace\_step

```python
def render_trace_step(step: Mapping[str, Any]) -> Text
```

One trace record as a line: tag, indentation, then what happened.

## HackAgentRichHandler Objects

```python
class HackAgentRichHandler(RichHandler)
```

A :class:`RichHandler` that draws attack trace records from their fields.

#### apply\_verbosity

```python
def apply_verbosity(verbose: Optional[int],
                    logger_name: str = "hackagent") -> None
```

Set the package&#x27;s log level from the `-v` count.

`HACKAGENT_LOG_LEVEL`, when set, wins; so does an unset count.

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

