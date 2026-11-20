# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


"""Rich console logging for the CLI and TUI.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup, and :func:`apply_verbosity`
once the ``-v`` count is known.

In a terminal, records of the attack trace
(:data:`hackagent.core.logging.TRACE_LOGGER`) are drawn from their fields
rather than their message: a coloured tag per attack and goal, indented like
the search tree, with the role of each call, verdicts coloured like the
dashboard, and quoted text that is never read as markup.

Logs go to stderr, so a command's own output on stdout (``--json`` lines)
stays machine-readable. Anywhere but a terminal (a file, a Slurm job, a
pipe) every record is one plain line: date and time, level, message, the
first three in fixed columns, so each line stands alone in a grep. Line
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
"""

import logging
import os
import sys
import time
import zlib
from typing import Any, Mapping, Optional

from rich.console import Console, ConsoleRenderable
from rich.logging import RichHandler
from rich.text import Text

from hackagent.core.logging import goal_label, trace_step

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

_ROLE_STYLES = {
    "target": "bold blue",
    "panel": "bold",
    "attacker": "bold magenta",
    "scorer": "bold cyan",
    "on_topic": "cyan",
}


def _attack_style(attack: str) -> str:
    return _ATTACK_COLOURS[zlib.crc32(attack.encode()) % len(_ATTACK_COLOURS)]


def render_trace_step(step: Mapping[str, Any]) -> Text:
    """One trace record as a line: tag, indentation, then what happened."""
    line = Text()
    attack = str(step.get("attack") or "run")
    tag = " · ".join(
        [attack]
        + (
            [goal_label(step["goal"], step.get("goals"))]
            if step.get("goal") is not None
            else []
        )
        + ([f"attempt {step['attempt']}"] if step.get("attempt") is not None else [])
    )
    line.append(tag, style=_attack_style(attack))
    line.append("  " + "  " * max(0, int(step.get("depth") or 1) - 1))
    within = step.get("within") or []
    node = step.get("node")
    if node != "phase" and within:
        # The whole path: "stream 1/1" alone does not say which round.
        line.append(" › ".join(within) + " › ", style="dim")
    error = step.get("error")
    if node == "phase":
        line.append("▸ ", style="dim")
        line.append(str(step.get("label") or ""), style="bold")
    elif node == "decision":
        line.append("◆ ", style="yellow")
        line.append(str(step.get("label") or ""), style="bold yellow")
        if step.get("reason"):
            line.append(f" {step['reason']}")
        details = step.get("details") or {}
        if details:
            line.append(
                " (" + ", ".join(f"{k}={v}" for k, v in details.items()) + ")",
                style="dim",
            )
    elif node == "artifact":
        line.append("▪ ", style="dim")
        line.append(f"{step.get('label')}", style="bold")
        uri = (step.get("details") or {}).get("uri")
        if uri:
            line.append(f" {uri}", style="dim")
    elif node == "call":
        role = str(step.get("role") or step.get("label") or "call")
        line.append(f"{role:<8}", style=_ROLE_STYLES.get(role, "bold"))
        if error:
            line.append(f" failed: {error}", style="red")
        elif role == "panel":
            score = step.get("score")
            if isinstance(score, (int, float)):
                line.append(f" {score:g}")
            success = step.get("success")
            if success is True:
                line.append(" jailbroken", style="bold red")
            elif success is False:
                line.append(" mitigated", style="green")
        elif step.get("text"):
            line.append(f' "{step["text"]}"', style="italic")
        details = []
        if step.get("tokens") is not None:
            details.append(f"{step['tokens']} tok")
        if step.get("latency_s") is not None:
            details.append(f"{step['latency_s']:.1f}s")
        if details:
            line.append("  " + " · ".join(details), style="dim")
    else:
        line.append(str(step.get("message") or ""))
    return line


#: Width of the level column: the longest level name, ``WARNING``.
LEVEL_WIDTH = 7


def plain_line(level: str, message: str, created: Optional[float] = None) -> str:
    """One record as written to a file: date and time, level, message."""
    stamp = time.strftime("%m-%d %H:%M:%S", time.localtime(created))
    return f"{stamp} {level:<{LEVEL_WIDTH}} {message}"


#: What a line break inside a message is written as, to keep it one line.
LINE_BREAK = " ⏎ "


def one_line(message: str) -> str:
    """``message`` with its line breaks shown as :data:`LINE_BREAK`, so a
    provider error or a captured warning is one line like every other."""
    return LINE_BREAK.join(
        line.strip() for line in message.splitlines() if line.strip()
    )


def trace_breadcrumb(step: Mapping[str, Any]) -> str:
    """A trace record as one sentence: attack, goal, the steps it is nested
    in, then what happened, joined by ``·``."""
    parts = [str(step.get("source") or "run"), *map(str, step.get("within") or ())]
    return " · ".join([*parts, str(step.get("what") or step.get("body") or "")])


class PlainFormatter(logging.Formatter):
    """Format a record as :func:`plain_line`; a trace record's message is its
    :func:`trace_breadcrumb`. Never padded or wrapped."""

    def format(self, record: logging.LogRecord) -> str:
        step = trace_step(record)
        message = trace_breadcrumb(step) if step is not None else record.getMessage()
        if record.exc_info:
            # The traceback joins the message, so the record stays one line.
            message += "\n" + self.formatException(record.exc_info)
        return plain_line(record.levelname, one_line(message), record.created)


def logs_to_terminal() -> bool:
    """Whether log lines (on stderr) go to a terminal, and so are drawn with
    Rich."""
    try:
        return sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


class HackAgentRichHandler(RichHandler):
    """A :class:`RichHandler` that draws attack trace records from their fields."""

    def render_message(
        self, record: logging.LogRecord, message: str
    ) -> ConsoleRenderable:
        step = trace_step(record)
        if step is not None:
            return render_trace_step(step)
        return super().render_message(record, message)


def apply_verbosity(verbose: Optional[int], logger_name: str = "hackagent") -> None:
    """Set the package's log level from the ``-v`` count.

    ``HACKAGENT_LOG_LEVEL``, when set, wins; so does an unset count.
    """
    if not isinstance(verbose, int) or os.getenv(f"{logger_name.upper()}_LOG_LEVEL"):
        return
    level = _VERBOSITY_LEVELS[max(0, min(verbose, max(_VERBOSITY_LEVELS)))]
    logging.getLogger(logger_name).setLevel(level)


_rich_handler_configured_for_package = False


def setup_package_logging(
    logger_name: str = "hackagent", default_level_str: str = "WARNING"
) -> logging.Logger:
    """Configures RichHandler for the specified logger if not already set."""
    global _rich_handler_configured_for_package

    package_logger = logging.getLogger(logger_name)

    if logger_name == "hackagent" and _rich_handler_configured_for_package:
        return package_logger

    # Use RichHandler specifically — StreamHandler is too broad since
    # RichHandler is a subclass and would incorrectly match the guard.
    has_rich_handler = any(
        isinstance(h, RichHandler) or getattr(h, "hackagent_cli", False)
        for h in package_logger.handlers
    )

    if not has_rich_handler:
        log_level_env = os.getenv(
            f"{logger_name.upper()}_LOG_LEVEL", default_level_str
        ).upper()
        level = getattr(logging, log_level_env, logging.WARNING)
        package_logger.setLevel(level)

        package_logger.addHandler(_handler())
        package_logger.propagate = False  # Avoid duplicate logs with root logger
        if logger_name == "hackagent":
            _route_other_loggers()

    if logger_name == "hackagent":
        _rich_handler_configured_for_package = True

    return package_logger


def _handler(level: int = logging.NOTSET) -> logging.Handler:
    """The CLI's log handler: Rich in a terminal, plain lines elsewhere."""
    if logs_to_terminal():
        handler: logging.Handler = HackAgentRichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_level=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
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
