---
sidebar_label: logging_setup
title: hackagent.interfaces.cli.logging_setup
---

The CLI&#x27;s and TUI&#x27;s log: one line per record, the same everywhere.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup, and :func:`apply_verbosity`
once the `-v` count is known. The package logger is opened fully and the
`-v` count is the level of the CLI&#x27;s own handler (:func:`shown_level`):
every other handler of a run has a level of its own.

Logs go to stderr, so a command&#x27;s own output on stdout (`--json` lines)
stays machine-readable. Every record is one line: date and time, level,
message, the first three in fixed columns, so each line stands alone in a
grep. In a terminal the line is coloured (:func:`log_text`): the time
dimmed, the level by severity, each attack in its own colour, verdicts
picked out; anywhere else (a file, a Slurm job, a pipe) it is plain. The
words are the same either way, and the same the TUI, `run.log` and the
platform&#x27;s activity log show. Line
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

While a campaign runs, :func:`show_run` prints on stdout the campaign&#x27;s own
lines the log level hides (each attack starting and finishing, how the run
ended), unless stdout is for `--json`.

The TUI shows the same coloured lines (:func:`log_markup`).

#### logs\_to\_terminal

```python
def logs_to_terminal() -> bool
```

Whether log lines (on stderr) go to a terminal, and so are drawn with
Rich.

## LogLineHandler Objects

```python
class LogLineHandler(logging.Handler)
```

The CLI&#x27;s log in a terminal: each record as the line a log file has
(:func:`log_text`), coloured, one record per line; the terminal wraps a
long one rather than the handler. A record&#x27;s traceback is drawn below
its line.

#### log\_text

```python
def log_text(record: logging.LogRecord) -> Text
```

`record` as :class:`PlainFormatter` writes it to a file, coloured as
a log viewer colours it: the time dimmed, the level by severity, the
attack the record is about in its own colour, and verdicts picked out.

Its plain text is the file&#x27;s line, character for character.

#### log\_markup

```python
def log_markup(record: logging.LogRecord) -> str
```

:func:`log_text` as Rich markup.

## RunStatusHandler Objects

```python
class RunStatusHandler(logging.Handler)
```

The campaign&#x27;s own lines (:data:`~hackagent.core.logging.CAMPAIGN_LOGGER`:
each attack starting and finishing, how the run ended) that the log
hides, on stdout, so a quiet log does not say nothing until the run
ends: coloured in a terminal, the file&#x27;s line elsewhere.

#### show\_run

```python
@contextmanager
def show_run(as_json: bool, logger_name: str = "hackagent") -> Iterator[None]
```

Show on stdout the campaign&#x27;s own lines the log hides, unless stdout
is for `--json`, which prints only the run&#x27;s summary at the end.

#### shown\_level

```python
def shown_level(logger_name: str = "hackagent") -> int
```

The level the CLI&#x27;s log shows: its handler&#x27;s level, never below what
the logger lets through. Without the CLI&#x27;s handler (the SDK, a test), the
logger&#x27;s own level.

#### apply\_verbosity

```python
def apply_verbosity(verbose: Optional[int],
                    logger_name: str = "hackagent") -> None
```

Set what the CLI&#x27;s log shows from the `-v` count: its handler&#x27;s
level, which leaves every other handler of the run its own.

`HACKAGENT_LOG_LEVEL`, when set, wins; so does an unset count.

#### setup\_package\_logging

```python
def setup_package_logging(
        logger_name: str = "hackagent",
        default_level_str: str = "WARNING") -> logging.Logger
```

Install the CLI&#x27;s log handler on the specified logger, if not already set.

The logger lets every record through and the handler shows
`HACKAGENT_LOG_LEVEL` (else `default_level_str`) and above, so a
run&#x27;s other handlers (the TUI&#x27;s pane, `--json`, the platform relay)
each choose their own level.

Idempotent: a logger that already has the CLI&#x27;s handler is left as is.

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

