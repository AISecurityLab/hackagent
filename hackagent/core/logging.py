# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Logger access for library code, and the run's log as the one way out.

Library modules only obtain loggers and log text; they never install
handlers. What a campaign does reaches every interface as log records: the
CLI prints them, the TUI shows them in its run view, a run keeps them in its
``run.log``, and the executor relays them to the platform. Each interface is
a :class:`logging.Handler` that shows the lines its own way.

A line says what happened. Which attack and goal it is about comes from
:func:`about`, set by the code that runs them; which kind of line it is,
from the logger it was logged on (:data:`CAMPAIGN_LOGGER`,
:data:`GOALS_LOGGER`, :data:`TRACE_LOGGER`). A step of an attack's trace
also carries its fields (:func:`trace_step`), from which it is written.

An interface attaches its handler with :func:`capture`, which hands it only
the records of the run it wraps, at the handler's own level. The logger's
level is the floor for every handler: the application opens it (the CLI to
DEBUG), and each handler chooses how much of that it shows.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from contextvars import ContextVar
from typing import Any, Optional

#: The package's root logger; every library logger descends from it.
PACKAGE_LOGGER = "hackagent"
#: The campaign's own story: it started, each attack started and finished,
#: how it ended. A quiet log still shows these lines.
CAMPAIGN_LOGGER = "hackagent.campaign"
#: One line per goal and attack, saying how the goal ended: what a progress
#: count reads, with the goal count from :func:`subject_of`.
GOALS_LOGGER = "hackagent.campaign.goals"

#: Logger of an attack's trace: a record for each node an attack records
#: (:mod:`hackagent.attacks.techniques.trace`), with the node's fields in the
#: record's ``trace_step``. Only its DEBUG records quote prompts and
#: replies, and nothing below INFO leaves the machine.
TRACE_LOGGER = "hackagent.trace"


#: Loggers of the model clients that log each retry at INFO, which a run's
#: activity relays: the application opens them to INFO, as the CLI does.
CLIENT_RETRY_LOGGERS = ("openai._base_client",)


def get_logger(name: str) -> logging.Logger:
    """Return the logger called ``name`` without configuring it."""
    return logging.getLogger(name)


# --- what a record carries ---------------------------------------------------


def trace_step(record: logging.LogRecord) -> Optional[Mapping[str, Any]]:
    """The trace node a :data:`TRACE_LOGGER` record describes, or None."""
    step = getattr(record, "trace_step", None)
    return step if isinstance(step, Mapping) else None


def goal_label(goal: Any, goals: Any = None) -> str:
    """``goal 3``, its number zero-padded to the width of the run's goal
    count (``goal 03`` of 20, ``goal 003`` of 200): an attack's lines start
    their text at the same place, and ``goal 03`` never matches goal 13."""
    width = len(str(goals)) if isinstance(goals, int) and goals > 0 else 0
    if width and isinstance(goal, int):
        return f"goal {goal:0{width}d}"
    return f"goal {goal}"


# --- the plain line a log file holds ----------------------------------------

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


def public_breadcrumb(step: Mapping[str, Any]) -> str:
    """A trace record as :func:`trace_breadcrumb` says it, without what a
    model may have written: a decision says what was decided and its numbers
    and flags, not why (a reason can quote a program a model wrote, or a
    tool call it made); a failed call says it failed, not the error text. For
    what leaves the machine; the log keeps the whole sentence."""
    if step.get("node") == "decision":
        details = step.get("details") or {}
        what = str(step.get("label") or "decision") + (
            " (" + ", ".join(f"{k}={v}" for k, v in details.items()) + ")"
            if details
            else ""
        )
    elif step.get("error"):
        what = f"{step.get('role') or step.get('label') or 'call'} failed"
    else:
        what = str(step.get("what") or step.get("body") or "")
    parts = [str(step.get("source") or "run"), *map(str, step.get("within") or ())]
    return " · ".join([*parts, what])


class PlainFormatter(logging.Formatter):
    """Format a record as :func:`plain_line`; a trace record's message is its
    :func:`trace_breadcrumb`. Never padded or wrapped."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        step = trace_step(record)
        message = trace_breadcrumb(step) if step is not None else record.getMessage()
        if record.exc_info:
            # The traceback joins the message, so the record stays one line.
            message += "\n" + self.formatException(record.exc_info)
        return plain_line(record.levelname, one_line(message), record.created)


# --- what a line is about ----------------------------------------------------

#: What the code running in this context works on (``attack``, ``goal``,
#: ``goals``…), set by :func:`about`.
_subject: ContextVar[Mapping[str, Any]] = ContextVar("hackagent_subject", default={})


@contextmanager
def about(**subject: Any) -> Iterator[None]:
    """Name what the code in this context works on, such as ``attack="tap",
    goal=3, goals=20``; nested calls add to it. Every record logged inside
    names it (:func:`subject_of`), so an interface can say which attack and
    goal a line is about without the line carrying it."""
    token = _subject.set({**_subject.get(), **subject})
    try:
        yield
    finally:
        _subject.reset(token)


def subject_of(record: Optional[logging.LogRecord] = None) -> Mapping[str, Any]:
    """What a record is about: as :func:`capture` stamped it, else what the
    current context is about (a handler runs in the context that logged)."""
    stamped = getattr(record, "subject", None) if record is not None else None
    return stamped if isinstance(stamped, Mapping) else _subject.get()


# --- handing a run's records to a handler ------------------------------------

#: The captures whose block the current task or thread is running in.
_scopes: ContextVar[frozenset[int]] = ContextVar(
    "hackagent_log_scopes", default=frozenset()
)


class _InScope(logging.Filter):
    """Passes the records logged inside one :func:`capture` block, stamped
    with what they are about (:func:`about`)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if id(self) not in _scopes.get():
            return False
        # A capture of a logger and one of its descendants meets the record
        # on each as it propagates: its handler takes it once.
        seen = record.__dict__.setdefault("_hackagent_captures", set())
        if id(self) in seen:
            return False
        seen.add(id(self))
        if not hasattr(record, "subject"):
            record.subject = dict(_subject.get())
        return True


def _attach(target: logging.Logger, handler: logging.Handler) -> None:
    """Add ``handler`` to ``target`` without changing the list a logging call
    may be walking in another thread: the list is replaced, never edited, so
    a walk in progress still sees every handler it started with."""
    with _HANDLERS_LOCK:
        if handler not in target.handlers:
            target.handlers = [*target.handlers, handler]


def _detach(target: logging.Logger, handler: logging.Handler) -> None:
    """Remove ``handler`` from ``target``, as :func:`_attach` adds it."""
    with _HANDLERS_LOCK:
        target.handlers = [h for h in target.handlers if h is not handler]


#: Serialises the replacement of a logger's handler list between captures.
_HANDLERS_LOCK = threading.Lock()


@contextmanager
def capture(
    handler: logging.Handler,
    level: int = logging.INFO,
    logger: str | Sequence[str] = PACKAGE_LOGGER,
) -> Iterator[logging.Handler]:
    """Hand ``handler`` the records of ``logger`` (and the loggers under it),
    or of each of several loggers, logged at ``level`` or above inside this
    block.

    Tasks created and threads started with :func:`asyncio.to_thread` inside
    the block belong to it, so two runs in one process each reach only their
    own handlers.

    ``level`` is the handler's own; no other handler is touched. The logger's
    level is the floor for all of them, so whoever configures logging opens
    it as far as its handlers need: the CLI opens the package logger fully
    and gives each of its handlers a level.
    """
    names = [logger] if isinstance(logger, str) else list(logger)
    targets = [logging.getLogger(name) for name in names]
    scope = _InScope()
    handler.addFilter(scope)
    handler.setLevel(level)
    for target in targets:
        _attach(target, handler)
    token = _scopes.set(_scopes.get() | {id(scope)})
    try:
        yield handler
    finally:
        _scopes.reset(token)
        for target in targets:
            _detach(target, handler)
        handler.removeFilter(scope)


# --- opening loggers nobody configured ---------------------------------------


class _Opener:
    """Opens loggers while runs need them in a process whose logging nobody
    configured, and closes them after the last run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users = 0
        self._opened: set[str] = set()

    def open(self, levels: Mapping[str, int]) -> bool:
        loggers = {name: logging.getLogger(name) for name in levels}
        with self._lock:
            if self._users == 0 and (
                logging.getLogger().handlers
                or any(found.level != logging.NOTSET for found in loggers.values())
                or any(_configured_above(found) for found in loggers.values())
            ):
                return False
            self._users += 1
            for name, found in loggers.items():
                found.setLevel(min(levels[name], found.level or levels[name]))
            self._opened.update(levels)
            return True

    def close(self) -> None:
        """Release one opening; the last one closes every logger opened."""
        with self._lock:
            self._users -= 1
            if self._users == 0:
                for name in self._opened:
                    logging.getLogger(name).setLevel(logging.NOTSET)
                self._opened.clear()


def _configured_above(found: logging.Logger) -> bool:
    """Whether an application put a handler on ``found`` or a logger above it
    (not the root, checked on its own): opening it would hand that handler
    records it never asked for. A run's own handlers, which
    :func:`capture` adds, do not count."""
    node: Optional[logging.Logger] = found
    while node is not None and node is not logging.getLogger():
        if any(
            not any(isinstance(f, _InScope) for f in handler.filters)
            for handler in node.handlers
        ):
            return True
        if not node.propagate:
            return False
        node = node.parent  # type: ignore[assignment]
    return False


_OPENER = _Opener()


@contextmanager
def opened(levels: Mapping[str, int]) -> Iterator[bool]:
    """Open each logger to its level for the block, if nobody configured
    logging: no level on any of them, no handler on the root logger, on them
    or on the loggers above them. Then no one else sees what they let
    through. Otherwise whoever configured logging
    decides, and nothing changes. Yields whether they were opened."""
    held = _OPENER.open(levels)
    try:
        yield held
    finally:
        if held:
            _OPENER.close()


# --- the run's own log file --------------------------------------------------

#: What a run's log file holds: the campaign's events and lines, and what
#: the attacks decide, without quoting prompts or replies (those are DEBUG).
RUN_LOG_LEVEL = logging.INFO


@contextmanager
def run_log(path: str | Path, level: int = RUN_LOG_LEVEL) -> Iterator[Path]:
    """Write the run inside the block to ``path``, a :class:`PlainFormatter`
    line per record at ``level`` and above, as the CLI writes its log to a
    file. Only the block's records, even with runs side by side."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8", delay=True)
    handler.setFormatter(PlainFormatter())
    try:
        with opened({PACKAGE_LOGGER: level}), capture(handler, level):
            yield path
    finally:
        handler.close()
