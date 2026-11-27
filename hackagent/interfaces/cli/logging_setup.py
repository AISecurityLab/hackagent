# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


"""The CLI's and TUI's log: one line per record, the same everywhere.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup, and :func:`apply_verbosity`
once the ``-v`` count is known. The package logger is opened fully and the
``-v`` count is the level of the CLI's own handler (:func:`shown_level`):
every other handler of a run has a level of its own.

Logs go to stderr, so a command's own output on stdout (``--json`` lines)
stays machine-readable. Every record is one line: date and time, level,
message, the first three in fixed columns, so each line stands alone in a
grep. In a terminal the line is coloured (:func:`log_text`): the time
dimmed, the level by severity, each attack in its own colour, verdicts
picked out; anywhere else (a file, a Slurm job, a pipe) it is plain. The
words are the same either way, and the same the TUI, ``run.log`` and the
platform's activity log show. Line
breaks inside a message, a traceback's among them, are shown as ``⏎``.
A trace record's message says where it happened, attack, goal and the
steps it is nested in, as a breadcrumb::

    11-20 15:58:12 DEBUG   bon · goal 18 · step 2/2 · candidate #3 · target: "Sure, here is…" · 410 tok · 1.2s
    11-20 15:58:12 INFO    bon · goal 18 · step 2/2 · candidate #3 · panel: jailbroken (score 10) · 0.1s
    11-20 15:58:13 INFO    bon · goal 18 · result: jailbroken at attempt 6 (step 2/2) · 6 attempts · 9.4s
    11-20 15:58:20 WARNING tool_output_ipi · goal 12 · target failed: timeout · 300.0s

Other libraries write through the same handler: their warnings, Python's
``warnings``, and the Hugging Face ``datasets`` messages
(:func:`route_library_logs`), so a log has one format throughout.

While a campaign runs, :func:`show_run` prints on stdout the campaign's own
lines the log level hides (each attack starting and finishing, how the run
ended), unless stdout is for ``--json``.

The TUI shows the same coloured lines (:func:`log_markup`).
"""

import logging
import os
import re
import sys
import zlib
from contextlib import contextmanager
from typing import Iterator, Optional

import click
from rich.console import Console
from rich.text import Text
from rich.traceback import Traceback

from hackagent.core.logging import (
    CAMPAIGN_LOGGER,
    CLIENT_RETRY_LOGGERS,
    LEVEL_WIDTH,
    PlainFormatter,
    capture,
    subject_of,
    trace_step,
)

#: ``-v`` count to log level: the default shows warnings, ``-vv`` what the
#: attacks decide, ``-vvv`` every call they make.
_VERBOSITY_LEVELS = {
    0: logging.ERROR,
    1: logging.WARNING,
    2: logging.INFO,
    3: logging.DEBUG,
}

#: Colours an attack's tag can take; each attack keeps one for the whole run.
_ATTACK_COLOURS = (
    "cyan",
    "magenta",
    "blue",
    "yellow",
    "bright_cyan",
    "bright_magenta",
    "bright_blue",
    "bright_yellow",
)


def _attack_style(attack: str) -> str:
    return _ATTACK_COLOURS[zlib.crc32(attack.encode()) % len(_ATTACK_COLOURS)]


def logs_to_terminal() -> bool:
    """Whether log lines (on stderr) go to a terminal, and so are drawn with
    Rich."""
    try:
        return sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


class LogLineHandler(logging.Handler):
    """The CLI's log in a terminal: each record as the line a log file has
    (:func:`log_text`), coloured, one record per line; the terminal wraps a
    long one rather than the handler. A record's traceback is drawn below
    its line."""

    def __init__(self, console: Optional[Console] = None) -> None:
        super().__init__()
        self.console = console or Console(stderr=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            error = record.exc_info
            if error:
                # The line without the traceback, which follows it drawn.
                record = logging.makeLogRecord(
                    {**record.__dict__, "exc_info": None, "exc_text": None}
                )
            self.console.print(log_text(record), soft_wrap=True, highlight=False)
            if error and error[1] is not None:
                self.console.print(Traceback.from_exception(*error))
        except Exception:
            self.handleError(record)


#: Colour of each level's name in a coloured log line.
_LEVEL_STYLES = {
    "DEBUG": "dim",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold reverse red",
}

#: Words a coloured log line picks out wherever they appear, coloured as the
#: dashboard colours verdicts.
_WORD_STYLES = (
    (r"\bjailbroken\b", "bold red"),
    (r"\bmitigated\b", "green"),
    (r"\b(?:failed|unreachable|FAILED)\b", "red"),
)

#: A count of none just before a word: "0 jailbroken", "0 of 20 goals
#: jailbroken". A word it counts is no news, so it is not picked out.
_NONE_BEFORE = re.compile(r"(?:^|\D)0 (?:of \d+ goals? )?$")

#: Width of :func:`plain_line`'s date and time, ``11-20 15:58:12``.
_STAMP_WIDTH = 14


def log_text(record: logging.LogRecord) -> Text:
    """``record`` as :class:`PlainFormatter` writes it to a file, coloured as
    a log viewer colours it: the time dimmed, the level by severity, the
    attack the record is about in its own colour, and verdicts picked out.

    Its plain text is the file's line, character for character."""
    line = Text(PlainFormatter().format(record))
    level_at = _STAMP_WIDTH + 1
    line.stylize("dim", 0, _STAMP_WIDTH)
    line.stylize(
        _LEVEL_STYLES.get(record.levelname, "bold"),
        level_at,
        level_at + len(record.levelname),
    )
    message_at = _message_at(record)
    attack = (trace_step(record) or subject_of(record)).get("attack")
    if attack and line.plain.startswith(str(attack), message_at):
        line.stylize(_attack_style(str(attack)), message_at, message_at + len(attack))
    for pattern, style in _WORD_STYLES:
        for match in re.finditer(pattern, line.plain):
            if not _NONE_BEFORE.search(line.plain[: match.start()]):
                line.stylize(style, match.start(), match.end())
    return line


def _message_at(record: logging.LogRecord) -> int:
    """Where the message starts in :func:`plain_line`'s line."""
    return _STAMP_WIDTH + 1 + max(LEVEL_WIDTH, len(record.levelname)) + 1


def log_markup(record: logging.LogRecord) -> str:
    """:func:`log_text` as Rich markup."""
    return log_text(record).markup


class RunStatusHandler(logging.Handler):
    """The campaign's own lines (:data:`~hackagent.core.logging.CAMPAIGN_LOGGER`:
    each attack starting and finishing, how the run ended) that the log
    hides, on stdout, so a quiet log does not say nothing until the run
    ends: coloured in a terminal, the file's line elsewhere."""

    def __init__(self, hidden_below: int, console: Optional[Console] = None) -> None:
        super().__init__()
        self.hidden_below = hidden_below
        self.console = console or Console()

    def emit(self, record: logging.LogRecord) -> None:
        if record.name != CAMPAIGN_LOGGER or record.levelno >= self.hidden_below:
            return
        try:
            if self.console.is_terminal:
                message = log_text(record)[_message_at(record) :]
                self.console.print(message, soft_wrap=True, highlight=False)
            else:
                click.echo(PlainFormatter().format(record))
        except Exception:
            self.handleError(record)


@contextmanager
def show_run(as_json: bool, logger_name: str = "hackagent") -> Iterator[None]:
    """Show on stdout the campaign's own lines the log hides, unless stdout
    is for ``--json``, which prints only the run's summary at the end."""
    shown = shown_level(logger_name)
    if as_json or shown <= logging.INFO:
        yield
        return
    with capture(RunStatusHandler(shown), logging.INFO, logger_name):
        yield


def _cli_handler(logger_name: str = "hackagent") -> Optional[logging.Handler]:
    """The CLI's log handler on ``logger_name``, if the CLI installed one."""
    return next(
        (
            handler
            for handler in logging.getLogger(logger_name).handlers
            if getattr(handler, "hackagent_cli", False)
        ),
        None,
    )


def shown_level(logger_name: str = "hackagent") -> int:
    """The level the CLI's log shows: its handler's level, never below what
    the logger lets through. Without the CLI's handler (the SDK, a test), the
    logger's own level."""
    effective = logging.getLogger(logger_name).getEffectiveLevel()
    handler = _cli_handler(logger_name)
    return max(handler.level, effective) if handler is not None else effective


def apply_verbosity(verbose: Optional[int], logger_name: str = "hackagent") -> None:
    """Set what the CLI's log shows from the ``-v`` count: its handler's
    level, which leaves every other handler of the run its own.

    ``HACKAGENT_LOG_LEVEL``, when set, wins; so does an unset count.
    """
    if not isinstance(verbose, int) or os.getenv(f"{logger_name.upper()}_LOG_LEVEL"):
        return
    level = _VERBOSITY_LEVELS[max(0, min(verbose, max(_VERBOSITY_LEVELS)))]
    handler = _cli_handler(logger_name)
    if handler is not None:
        handler.setLevel(level)
    else:
        logging.getLogger(logger_name).setLevel(level)


def setup_package_logging(
    logger_name: str = "hackagent", default_level_str: str = "WARNING"
) -> logging.Logger:
    """Install the CLI's log handler on the specified logger, if not already set.

    The logger lets every record through and the handler shows
    ``HACKAGENT_LOG_LEVEL`` (else ``default_level_str``) and above, so a
    run's other handlers (the TUI's pane, ``--json``, the platform relay)
    each choose their own level.

    Idempotent: a logger that already has the CLI's handler is left as is.
    """
    package_logger = logging.getLogger(logger_name)

    if not any(getattr(h, "hackagent_cli", False) for h in package_logger.handlers):
        log_level_env = os.getenv(
            f"{logger_name.upper()}_LOG_LEVEL", default_level_str
        ).upper()
        level = getattr(logging, log_level_env, logging.WARNING)
        package_logger.setLevel(logging.DEBUG)

        package_logger.addHandler(_handler(level))
        package_logger.propagate = False  # Avoid duplicate logs with root logger
        if logger_name == "hackagent":
            _route_other_loggers()

    return package_logger


def _handler(level: int = logging.NOTSET) -> logging.Handler:
    """The CLI's log handler: the log line coloured in a terminal
    (:class:`LogLineHandler`), plain elsewhere; the same words either way."""
    if logs_to_terminal():
        handler: logging.Handler = LogLineHandler(Console(stderr=True))
    else:
        # A file or a pipe: one plain line per record, as vLLM writes.
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(PlainFormatter())
    handler.setLevel(level)
    handler.hackagent_cli = True  # type: ignore[attr-defined]
    return handler


def _route_other_loggers() -> None:
    """Write other libraries' warnings, and Python's ``warnings``, through
    the same kind of handler, so they share the package's format instead of
    each printing its own way."""
    root = logging.getLogger()
    if not any(getattr(h, "hackagent_cli", False) for h in root.handlers):
        root.addHandler(_handler(logging.WARNING))
    logging.captureWarnings(True)
    # Each retry is an INFO line: the run's activity relays them, while the
    # handler above still shows only warnings.
    for name in CLIENT_RETRY_LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)


def route_library_logs() -> None:
    """Send the Hugging Face ``datasets`` library's messages through the
    logging handlers instead of the stderr handler it installs for itself.

    Called by the commands that load datasets, so other commands do not pay
    for importing it.
    """
    try:
        from datasets.utils import logging as datasets_logging
    except Exception:
        return
    library = logging.getLogger("datasets")
    # datasets adds a bare StreamHandler to its root logger the first time it
    # logs, and keeps its records from propagating: make it log once, take
    # that handler off, and let the records reach ours.
    datasets_logging.get_verbosity()
    for handler in list(library.handlers):
        if type(handler) is logging.StreamHandler:
            library.removeHandler(handler)
    datasets_logging.enable_propagation()


def suppress_noisy_libraries(*names: str) -> None:
    """
    Silence chatty third-party loggers to WARNING.

    This is opt-in so that applications embedding hackagent are not surprised
    by their own library loggers being muted.

    Example:
        >>> from hackagent.interfaces.cli.logging_setup import suppress_noisy_libraries
        >>> suppress_noisy_libraries("httpx", "litellm", "urllib3")
    """
    for name in names:
        logging.getLogger(name).setLevel(logging.WARNING)
