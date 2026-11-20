---
sidebar_label: logging_setup
title: hackagent.interfaces.cli.logging_setup
---

Rich console logging for the CLI and TUI.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup, and :func:`apply_verbosity`
once the `-v` count is known.

In a terminal, records of the attack trace
(:data:`hackagent.core.logging.TRACE_LOGGER`) are drawn from their fields
rather than their message: a coloured tag per attack and goal, indented like
the search tree, with the role of each call, verdicts coloured like the
dashboard, and quoted text that is never read as markup.

Logs go to stderr, so a command&#x27;s own output on stdout (`--json` lines)
stays machine-readable. Anywhere but a terminal (a file, a Slurm job, a
pipe) every record is one plain line: date and time, level, message, the
first three in fixed columns, so each line stands alone in a grep. Line
breaks inside a message, a traceback&#x27;s among them, are shown as `⏎`.
A trace record&#x27;s message says where it happened, attack, goal and the
steps it is nested in, as a breadcrumb::

    11-20 15:58:12 DEBUG   bon · goal 18 · step 2/2 · candidate `3` · target: &quot;Sure, here is…&quot; · 410 tok · 1.2s
    11-20 15:58:12 INFO    bon · goal 18 · step 2/2 · candidate `3` · panel: jailbroken (score 10) · 0.1s
    11-20 15:58:13 INFO    bon · goal 18 · result: jailbroken at attempt 6 (step 2/2) · 6 attempts · 9.4s
    11-20 15:58:20 WARNING tool_output_ipi · goal 12 · target failed: timeout · 300.0s

Other libraries write through the same handler: their warnings, Python&#x27;s
`warnings`, and the Hugging Face `datasets` messages
(:func:`route_library_logs`), so a log has one format throughout.

#### render\_trace\_step

```python
def render_trace_step(step: Mapping[str, Any]) -> Text
```

One trace record as a line: tag, indentation, then what happened.

#### LEVEL\_WIDTH

Width of the level column: the longest level name, `WARNING`.

#### plain\_line

```python
def plain_line(level: str,
               message: str,
               created: Optional[float] = None) -> str
```

One record as written to a file: date and time, level, message.

#### LINE\_BREAK

What a line break inside a message is written as, to keep it one line.

#### one\_line

```python
def one_line(message: str) -> str
```

`message` with its line breaks shown as :data:`LINE_BREAK`, so a
provider error or a captured warning is one line like every other.

#### trace\_breadcrumb

```python
def trace_breadcrumb(step: Mapping[str, Any]) -> str
```

A trace record as one sentence: attack, goal, the steps it is nested
in, then what happened, joined by `·`.

## PlainFormatter Objects

```python
class PlainFormatter(logging.Formatter)
```

Format a record as :func:`plain_line`; a trace record&#x27;s message is its
:func:`trace_breadcrumb`. Never padded or wrapped.

#### logs\_to\_terminal

```python
def logs_to_terminal() -> bool
```

Whether log lines (on stderr) go to a terminal, and so are drawn with
Rich.

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

#### route\_library\_logs

```python
def route_library_logs() -> None
```

Send the Hugging Face `datasets` library&#x27;s messages through the
logging handlers instead of the stderr handler it installs for itself.

Called by the commands that load datasets, so other commands do not pay
for importing it.

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

