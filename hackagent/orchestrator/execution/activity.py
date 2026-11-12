# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Send what a run's executor is doing to the platform, as it does it.

The dashboard shows a run's stored results, but not what happens before and
between them: goals loading, models answering preflight, an attack's warm-up,
a target that times out and is retried. :class:`ActivityRelay` turns the
campaign runner's progress events and the run's own log records into short
activity events and sends them to ``POST /run/{id}/events``, where the run
page reads them back as its activity log.

Only operational facts leave the machine: messages made of names and counts,
and log lines. Goal texts, prompts and replies are never read; every message
has the secrets the executor knows, credential-shaped values and URL
credentials redacted, and is cut to 1,000 characters.

Sending never slows or fails the run. Events wait in a bounded queue (the
oldest ``debug`` and ``info`` events make room first, and a warning says how
many were dropped) and a daemon thread sends them in batches every couple of
seconds, or as soon as enough are waiting. A failed send is retried with the
next batch, as the server keeps one event per ``seq``. The executor flushes
what is left before it finishes the run; a server that answers that the run
is over, or that predates the endpoint, is not sent anything more.

Log records are read through filters on the loggers themselves, so nothing a
handler prints changes. ``hackagent`` records are relayed at the level the
executor's logging enables (the campaign runner reports its own progress as
events whatever that level), the OpenAI client's retries always, and the HTTP
libraries' warnings and errors. Only records logged inside the run's own
task, or threads it started with :func:`asyncio.to_thread`, belong to it, so
runs executing side by side in one process keep their logs apart.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from hackagent.core.logging import get_logger, reported_as_event
from hackagent.orchestrator.campaign.spec import _is_credential_name, redacted
from hackagent.storage.remote import (
    ExecutorRejected,
    RunAlreadyFinished,
    RunEventsUnsupported,
)
from hackagent.tracking.serialize import sanitize_for_json

logger = get_logger(__name__)

#: Longest message the platform stores.
MESSAGE_LIMIT = 1000
#: Largest ``data`` object, serialized.
DATA_LIMIT = 4096
#: Most events in one request.
BATCH_LIMIT = 200
#: Most events waiting to be sent.
QUEUE_LIMIT = 5000
#: Seconds between two sends, unless enough events are waiting before then.
FLUSH_INTERVAL_S = 2.0
#: Waiting events that start a send at once.
FLUSH_THRESHOLD = 50
#: How long finishing a run waits for its last events to be sent.
CLOSE_TIMEOUT_S = 10.0

_REDACTED = "[REDACTED]"
#: Longest attack name the platform stores.
_ATTACK_CHARS = 200
#: Distinct goal errors an event carries, and how long each may be.
_ERRORS_LIMIT = 3
_ERROR_CHARS = 200
#: Known secret values shorter than this are not searched for: a two-letter
#: value would redact half of every message.
_SECRET_MIN_CHARS = 8

_HACKAGENT = "hackagent"
#: Libraries whose retries, timeouts, warnings and errors are relayed.
_LIBRARIES = ("openai", "httpx", "litellm", "LiteLLM")
#: Loggers whose INFO lines are relayed whatever the executor's logging
#: shows: the OpenAI client logs each retry at INFO. They are module loggers
#: no other logger descends from, so lowering their level leaks nothing.
_RETRY_LOGGERS = ("openai._base_client",)
_RETRY = re.compile(r"retr(?:y|ies|ying)|timed out|timeout", re.IGNORECASE)
#: Per-call INFO lines that say nothing about the run, even when they
#: mention a timeout.
_NOISE = re.compile(r"HTTP Request:|completion\(\) model=")

_BEARER = re.compile(
    r"\b(bearer|basic|token)(\s+)[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE
)
#: ``name=value``, ``name: value`` and ``"name": "value"``.
_ASSIGNMENT = re.compile(
    r"(?P<name>[A-Za-z][\w.-]*)(?P<sep>[\"']?\s*[:=]\s*[\"']?)(?P<value>[^\s\"',;&)}\]]+)"
)
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.IGNORECASE)
#: Values shaped like the API keys of common providers.
_KEY_SHAPED = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|hf_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}"
    r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Activity:
    """One line of a run's activity log, before the relay numbers it.

    ``attack`` is the attack's name in the campaign, ``attack_run`` the id of
    its run, and ``goal_index`` the 0-based dataset index of the goal the line
    is about; each is ``None`` when the line is not about one.
    """

    level: str
    kind: str
    message: str
    attack: Optional[str] = None
    attack_run: Optional[str] = None
    goal_index: Optional[int] = None
    data: Mapping[str, Any] = field(default_factory=dict)
    time: datetime = field(default_factory=_now)

    def wire(self, seq: int) -> dict[str, Any]:
        """The event as ``POST /run/{id}/events`` takes it, numbered ``seq``."""
        return {
            "seq": seq,
            "time": self.time.isoformat(),
            "level": self.level,
            "kind": self.kind,
            "attack": self.attack,
            "attack_run": self.attack_run,
            "goal_index": self.goal_index,
            "message": self.message,
            "data": dict(self.data),
        }


class Redactor:
    """Takes secrets out of activity before it leaves the machine.

    ``secrets`` are values the executor knows to be secret, such as its API
    key and the values of the variables its models read; each is replaced
    wherever it appears. Bearer tokens, values stored under a credential's
    name (``api_key=…``), credentials in URLs and values shaped like a
    provider's API key are replaced too, by the rules a recorded campaign is
    redacted with.
    """

    def __init__(self, secrets: Iterable[Any] = ()) -> None:
        values = {
            value
            for value in secrets
            if isinstance(value, str) and len(value) >= _SECRET_MIN_CHARS
        }
        # Longest first, so a secret that contains another goes whole.
        self._secrets = sorted(values, key=len, reverse=True)

    def text(self, value: str) -> str:
        """``value`` with every secret it spells out replaced."""
        for secret in self._secrets:
            value = value.replace(secret, _REDACTED)
        value = _BEARER.sub(lambda match: f"{match[1]}{match[2]}{_REDACTED}", value)
        value = _ASSIGNMENT.sub(_redact_assignment, value)
        value = _URL.sub(lambda match: str(redacted(match[0])), value)
        return _KEY_SHAPED.sub(_REDACTED, value)

    def data(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """``value`` made JSON-safe, with credentials and secrets replaced,
        and emptied of anything but scalars when it outgrows the limit."""
        cleaned = self._strings(sanitize_for_json(redacted(dict(value))))
        if _size(cleaned) <= DATA_LIMIT:
            return cleaned
        scalars = {
            key: item
            for key, item in cleaned.items()
            if isinstance(item, (int, float, bool)) or item is None
        }
        return scalars if _size(scalars) <= DATA_LIMIT else {}

    def activity(self, activity: Activity) -> Optional[Activity]:
        """``activity`` redacted and cut to the platform's limits, on one
        line; ``None`` when nothing of its message is left."""
        message = _clip(
            " ".join(self.text(_printable(activity.message)).split()), MESSAGE_LIMIT
        )
        if not message:
            return None
        attack = _printable(activity.attack or "")[:_ATTACK_CHARS]
        index = activity.goal_index
        return replace(
            activity,
            message=message,
            attack=attack or None,
            attack_run=_uuid(activity.attack_run),
            goal_index=index if isinstance(index, int) and index >= 0 else None,
            data=self.data(activity.data),
        )

    def _strings(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(_printable(value))
        if isinstance(value, dict):
            return {key: self._strings(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._strings(item) for item in value]
        return value


def _redact_assignment(match: re.Match[str]) -> str:
    if match["value"] == _REDACTED or not _is_credential_name(match["name"]):
        return match[0]
    return f"{match['name']}{match['sep']}{_REDACTED}"


def _printable(text: str) -> str:
    """``text`` without NUL characters, which the platform does not store."""
    return text.replace("\x00", "")


def _size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _uuid(value: Optional[str]) -> Optional[str]:
    """``value`` when it is a UUID, the only kind of run id the platform has."""
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _seconds(value: Any) -> Optional[float]:
    return round(float(value), 1) if isinstance(value, (int, float)) else None


# --- runner events ----------------------------------------------------------


def activity_from_event(event: str, payload: Mapping[str, Any]) -> Optional[Activity]:
    """The activity line for one of the campaign runner's progress events.

    Only the names and counts each event is known to carry are read, so a
    field added to an event later never leaves unless it is added here. An
    event this relay does not know is ``None``.
    """
    build = _EVENTS.get(event)
    return build(payload) if build is not None else None


def _campaign_started(payload: Mapping[str, Any]) -> Activity:
    return Activity(
        "info",
        "campaign",
        f"campaign {payload.get('campaign')} · started · loading goals and models",
    )


def _goals_loaded(payload: Mapping[str, Any]) -> Activity:
    goals = int(payload.get("goals") or 0)
    return Activity(
        "info",
        "dataset",
        f"dataset · {_plural(goals, 'goal')} loaded",
        data={"goals": goals},
    )


def _models_resolved(payload: Mapping[str, Any]) -> Activity:
    counts = {
        name: int(payload.get(name) or 0) for name in ("models", "attacks", "judges")
    }
    return Activity(
        "info",
        "campaign",
        f"campaign · {_plural(counts['models'], 'model')} ready · "
        f"{_plural(counts['attacks'], 'attack')} · {_plural(counts['judges'], 'judge')}",
        data=counts,
    )


def _preflight_started(payload: Mapping[str, Any]) -> Activity:
    models = int(payload.get("models") or 0)
    return Activity(
        "info",
        "preflight",
        f"preflight · checking {_plural(models, 'model')}",
        data={"models": models},
    )


def _preflight_finished(payload: Mapping[str, Any]) -> Activity:
    models = int(payload.get("models") or 0)
    return Activity(
        "info",
        "preflight",
        f"preflight · {_plural(models, 'model')} reachable",
        data={"models": models},
    )


def _preflight_failed(payload: Mapping[str, Any]) -> Activity:
    models = int(payload.get("models") or 0)
    failures = [str(failure) for failure in payload.get("failures") or ()]
    return Activity(
        "error",
        "preflight",
        f"preflight · {len(failures)} of {_plural(models, 'model')} unreachable: "
        + "; ".join(failures),
        data={"models": models, "unreachable": len(failures)},
    )


def _audit_started(payload: Mapping[str, Any]) -> Activity:
    judges = int(payload.get("judges") or 0)
    return Activity(
        "info",
        "judge",
        f"judge audit · started · {_plural(judges, 'judge')}",
        data={"judges": judges},
    )


def _audit_finished(payload: Mapping[str, Any]) -> Activity:
    audit = payload.get("audit") or {}
    passed = audit.get("passed") if isinstance(audit, Mapping) else None
    samples = audit.get("samples") if isinstance(audit, Mapping) else None
    verdict = {True: "passed", False: "failed"}.get(passed, "finished")
    message = f"judge audit · {verdict}"
    if isinstance(samples, int):
        message += f" · {_plural(samples, 'sample')}"
    return Activity(
        "warning" if passed is False else "info",
        "judge",
        message,
        data={"passed": passed, "samples": samples},
    )


def _attack_started(payload: Mapping[str, Any]) -> Activity:
    goals = int(payload.get("expected_goals") or 0)
    return Activity(
        "info",
        "attack",
        f"{payload.get('attack')} · started · {_plural(goals, 'goal')}",
        attack=_name(payload),
        attack_run=payload.get("run_id"),
        data={"goals": goals},
    )


def _preparation_started(payload: Mapping[str, Any]) -> Activity:
    goals = int(payload.get("goals") or 0)
    return Activity(
        "info",
        "attack",
        f"{payload.get('attack')} · preparing · {_plural(goals, 'goal')}",
        attack=_name(payload),
        attack_run=payload.get("run_id"),
        data={"goals": goals},
    )


def _preparation_finished(payload: Mapping[str, Any]) -> Activity:
    elapsed = _seconds(payload.get("elapsed_s"))
    message = f"{payload.get('attack')} · prepared"
    if elapsed is not None:
        message += f" in {elapsed:.1f}s"
    return Activity(
        "info",
        "attack",
        message,
        attack=_name(payload),
        attack_run=payload.get("run_id"),
        data={"elapsed_s": elapsed},
    )


def _goal_finished(payload: Mapping[str, Any]) -> Activity:
    index = payload.get("goal_index")
    goals = payload.get("goals")
    attempts = int(payload.get("attempts") or 0)
    successful = int(payload.get("successful") or 0)
    every_error = [str(error) for error in payload.get("errors") or ()]
    errors = [_clip(error, _ERROR_CHARS) for error in every_error[:_ERRORS_LIMIT]]
    position = f"{index + 1}" if isinstance(index, int) else "?"
    if isinstance(goals, int):
        position += f"/{goals}"
    message = (
        f"{payload.get('attack')} · goal {position} · "
        f"{_plural(attempts, 'attempt')} · {successful} successful"
    )
    if errors:
        message += f" · {_plural(len(every_error), 'error')}: {errors[0]}"
    return Activity(
        "warning" if errors else "info",
        "goal",
        message,
        attack=_name(payload),
        attack_run=payload.get("run_id"),
        goal_index=index if isinstance(index, int) else None,
        data={
            "attempts": attempts,
            "successful": successful,
            "elapsed_s": _seconds(payload.get("elapsed_s")),
            "errors": errors,
        },
    )


def _attack_finished(payload: Mapping[str, Any]) -> Activity:
    error = payload.get("error")
    attempts = int(payload.get("attempts") or 0)
    successful = int(payload.get("successful") or 0)
    elapsed = _seconds(payload.get("elapsed_s"))
    data = {"attempts": attempts, "successful": successful, "elapsed_s": elapsed}
    if error:
        return Activity(
            "error",
            "attack",
            f"{payload.get('attack')} · failed · {error}",
            attack=_name(payload),
            attack_run=payload.get("run_id"),
            data=data,
        )
    message = (
        f"{payload.get('attack')} · finished · {_plural(attempts, 'attempt')} · "
        f"{successful} successful"
    )
    if elapsed is not None:
        message += f" · {elapsed:.1f}s"
    return Activity(
        "info",
        "attack",
        message,
        attack=_name(payload),
        attack_run=payload.get("run_id"),
        data=data,
    )


def _name(payload: Mapping[str, Any]) -> Optional[str]:
    attack = payload.get("attack")
    return str(attack) if attack else None


_EVENTS: dict[str, Callable[[Mapping[str, Any]], Activity]] = {
    "campaign_started": _campaign_started,
    "goals_loaded": _goals_loaded,
    "models_resolved": _models_resolved,
    "preflight_started": _preflight_started,
    "preflight_finished": _preflight_finished,
    "preflight_failed": _preflight_failed,
    "audit_started": _audit_started,
    "audit_finished": _audit_finished,
    "attack_started": _attack_started,
    "preparation_started": _preparation_started,
    "preparation_finished": _preparation_finished,
    "goal_finished": _goal_finished,
    "attack_finished": _attack_finished,
}


def activity_for_outcome(status: str, note: str) -> Activity:
    """The last line of a run's activity: how it ended, and why."""
    if status == "COMPLETED":
        return Activity(
            "info", "campaign", "campaign · completed", data={"status": status}
        )
    level = "error" if status == "FAILED" else "warning"
    message = f"campaign · {status.lower()}" + (f" · {note}" if note else "")
    return Activity(level, "campaign", message, data={"status": status})


# --- log records ------------------------------------------------------------


def activity_from_record(record: logging.LogRecord) -> Optional[Activity]:
    """The activity line for a log record, or ``None`` for one not relayed.

    ``hackagent`` records at INFO and above become ``log`` lines, except the
    ones a progress event reports too. From the HTTP and model client
    libraries, retries and timeouts become ``retry`` warnings, other warnings
    and errors ``log`` lines, and everything else, such as a line per request,
    is left out.
    """
    if reported_as_event(record) or record.name == logger.name:
        return None
    if record.levelno < logging.INFO:
        return None
    library = next((name for name in _LIBRARIES if _under(record.name, name)), None)
    if library is None and not _under(record.name, _HACKAGENT):
        return None
    message = record.getMessage()
    if record.exc_info and record.exc_info[1] is not None:
        error = record.exc_info[1]
        message += f" ({type(error).__name__}: {error})"
    time = datetime.fromtimestamp(record.created, timezone.utc)
    if library is None:
        return Activity(_level(record.levelno), "log", message, time=time)
    quiet = record.levelno < logging.WARNING
    if quiet and _NOISE.search(message):
        return None
    retry = bool(_RETRY.search(message))
    if quiet and not retry:
        return None
    return Activity(
        "warning" if quiet else _level(record.levelno),
        "retry" if retry else "log",
        f"{library.lower()} · {message}",
        time=time,
    )


def _under(name: str, root: str) -> bool:
    return name == root or name.startswith(root + ".")


def _level(levelno: int) -> str:
    if levelno >= logging.ERROR:
        return "error"
    if levelno >= logging.WARNING:
        return "warning"
    if levelno >= logging.INFO:
        return "info"
    return "debug"


#: The relay of the run whose task or thread is logging, if any.
_current: ContextVar[Optional["ActivityRelay"]] = ContextVar(
    "activity_relay", default=None
)


class _TapFilter(logging.Filter):
    """Hands each record of its logger to the current run's relay.

    A logger whose level was lowered for the relay drops, after relaying
    them, the records below ``threshold``, so no handler sees more than it
    did before.
    """

    def __init__(self, threshold: int = 0) -> None:
        super().__init__()
        self.threshold = threshold

    def filter(self, record: logging.LogRecord) -> bool:
        relay = _current.get()
        if relay is not None:
            relay.take_record(record)
        return record.levelno >= self.threshold


class _LogTap:
    """The filters on the relayed loggers, there while any relay captures.

    Shared by every relay in the process. Loggers created while it is in
    place, such as those of a model client imported when the campaign builds
    its models, are tapped on :meth:`refresh`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users = 0
        self._filters: dict[str, _TapFilter] = {}
        #: Loggers lowered to INFO, and the level each had before.
        self._levels: dict[str, int] = {}
        self._known = 0

    def acquire(self) -> None:
        """Put the filters in place, unless another relay already did."""
        with self._lock:
            self._users += 1
            if self._users == 1:
                self._scan()

    def release(self) -> None:
        """Remove the filters once the last relay is done with them."""
        with self._lock:
            self._users -= 1
            if self._users > 0:
                return
            for name, tap in self._filters.items():
                logging.getLogger(name).removeFilter(tap)
            for name, level in self._levels.items():
                logging.getLogger(name).setLevel(level)
            self._filters.clear()
            self._levels.clear()
            self._known = 0

    def refresh(self) -> None:
        """Tap the loggers created since the last look, if there are any."""
        if len(logging.Logger.manager.loggerDict) == self._known:
            return
        with self._lock:
            if self._users > 0:
                self._scan()

    def _scan(self) -> None:
        loggers = logging.Logger.manager.loggerDict
        names = list(loggers)
        self._known = len(names)
        for name in names:
            found = loggers.get(name)
            if name in self._filters or not isinstance(found, logging.Logger):
                continue
            if not any(_under(name, root) for root in (_HACKAGENT, *_LIBRARIES)):
                continue
            threshold = 0
            if name in _RETRY_LOGGERS and found.getEffectiveLevel() > logging.INFO:
                threshold = found.getEffectiveLevel()
                self._levels[name] = found.level
                found.setLevel(logging.INFO)
            tap = _TapFilter(threshold)
            found.addFilter(tap)
            self._filters[name] = tap


_TAP = _LogTap()


# --- the relay --------------------------------------------------------------


class ActivityRelay:
    """Sends a run's activity to the platform from a daemon thread.

    ``send`` posts one batch of events (as :meth:`Activity.wire` makes them)
    and raises when it cannot: :class:`~hackagent.storage.RunAlreadyFinished`
    and :class:`~hackagent.storage.ExecutorRejected` (the run is over),
    and :class:`~hackagent.storage.RunEventsUnsupported` (an older server)
    stop the sending for good, a ``ValueError`` (the server refused the batch
    itself) drops that batch, and any other error keeps it for the next try. ``secrets`` are the values the
    :class:`Redactor` replaces.

    Events are numbered as they are sent, so the server receives ``seq`` in
    order with no gaps, whatever the queue dropped.
    """

    def __init__(
        self,
        send: Callable[[list[dict[str, Any]]], Any],
        *,
        secrets: Iterable[Any] = (),
        interval_s: float = FLUSH_INTERVAL_S,
        threshold: int = FLUSH_THRESHOLD,
        batch_size: int = BATCH_LIMIT,
        limit: int = QUEUE_LIMIT,
        close_timeout_s: float = CLOSE_TIMEOUT_S,
    ) -> None:
        self._send = send
        self._redactor = Redactor(secrets)
        self._interval_s = interval_s
        self._threshold = threshold
        self._batch_size = batch_size
        self._limit = limit
        self._close_timeout_s = close_timeout_s
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._sending = threading.Lock()
        self._queue: deque[Activity] = deque()
        self._in_flight: Optional[list[dict[str, Any]]] = None
        self._seq = 0
        self._dropped = 0
        self._stopping = False
        self._stopped = False
        self._failing = False
        self._refused = False
        self._thread: Optional[threading.Thread] = None

    @property
    def stopped(self) -> bool:
        """Whether sending stopped for good: the run is over on the server,
        or the server does not record activity."""
        return self._stopped

    # Producing ------------------------------------------------------------

    def on_event(self, event: str, **payload: Any) -> None:
        """Campaign runner listener: relay ``event``. Never raises."""
        try:
            _TAP.refresh()
            if event == "goal_finished":
                # Event conversion clips errors; redact full values first so a
                # credential crossing the boundary cannot leave a partial key.
                payload["errors"] = [
                    self._redactor.text(str(error))
                    for error in payload.get("errors") or ()
                ]
            activity = activity_from_event(event, payload)
            if activity is not None:
                self.add(activity)
        except Exception:
            logger.debug("run activity | event %s not relayed", event, exc_info=True)

    def take_record(self, record: logging.LogRecord) -> None:
        """Relay a log record of the run, if it is one to relay. Never raises."""
        if self._stopped or self._stopping:
            return
        try:
            activity = activity_from_record(record)
            if activity is not None:
                self.add(activity)
        except Exception:  # noqa: BLE001 - a bad record must not reach the caller
            pass

    def finished(self, status: str, note: str) -> None:
        """Relay how the run ended, the last line before :meth:`close`."""
        self.add(activity_for_outcome(status, note))

    def add(self, activity: Activity) -> None:
        """Queue ``activity``, redacted, making room in a full queue."""
        if self._stopped or self._stopping:
            return
        item = self._redactor.activity(activity)
        if item is None:
            return
        with self._wake:
            if self._stopped or self._stopping:
                return
            if len(self._queue) >= self._limit:
                self._drop_one()
            self._queue.append(item)
            if len(self._queue) >= self._threshold:
                self._wake.notify()

    def _drop_one(self) -> None:
        """Drop the oldest ``debug`` or ``info`` event, or else the oldest."""
        for index, queued in enumerate(self._queue):
            if queued.level in ("debug", "info"):
                del self._queue[index]
                break
        else:
            self._queue.popleft()
        self._dropped += 1

    # Running --------------------------------------------------------------

    @contextmanager
    def capture(self) -> Iterator[ActivityRelay]:
        """Start sending, and relay the log records of the current context.

        Tasks created and threads started with :func:`asyncio.to_thread`
        inside the block belong to the run for as long as they log.
        """
        self.start()
        _TAP.acquire()
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)
            _TAP.release()

    def start(self) -> None:
        """Start the sending thread, once."""
        with self._lock:
            if self._thread is not None or self._stopping:
                return
            self._thread = threading.Thread(
                target=self._run, name="hackagent-run-activity", daemon=True
            )
            self._thread.start()

    def close(self) -> None:
        """Send what is queued, waiting at most ``close_timeout_s``, and stop.

        Events added afterwards are dropped.
        """
        with self._wake:
            if self._stopping:
                return
            self._stopping = True
            self._wake.notify()
            thread = self._thread
        if thread is not None:
            thread.join(self._close_timeout_s)
        else:
            self.flush()

    def flush(self) -> bool:
        """Send every queued event now, on this thread.

        Returns whether everything was sent; a send that failed keeps its
        batch for the next flush.
        """
        with self._sending:
            while not self._stopped:
                with self._lock:
                    batch = self._next_batch()
                if batch is None:
                    return True
                if not self._deliver(batch):
                    return False
            return False

    def _run(self) -> None:
        while True:
            with self._wake:
                if not self._stopping and (
                    self._failing or len(self._queue) < self._threshold
                ):
                    self._wake.wait(self._interval_s)
                stopping = self._stopping
            _TAP.refresh()
            sent = self.flush()
            if stopping:
                # One more try for a batch that failed on the way out.
                if not sent:
                    self.flush()
                return

    def _next_batch(self) -> Optional[list[dict[str, Any]]]:
        """The batch to send next: the one that failed, or a new one."""
        if self._in_flight is not None:
            return self._in_flight
        if not self._queue and not self._dropped:
            return None
        items: list[Activity] = []
        if self._dropped:
            items.append(
                Activity(
                    "warning",
                    "log",
                    f"activity · {_plural(self._dropped, 'event')} dropped: "
                    "they came faster than they could be sent",
                    data={"dropped": self._dropped},
                )
            )
            self._dropped = 0
        while self._queue and len(items) < self._batch_size:
            items.append(self._queue.popleft())
        batch = []
        for item in items:
            self._seq += 1
            batch.append(item.wire(self._seq))
        self._in_flight = batch
        return batch

    def _deliver(self, batch: list[dict[str, Any]]) -> bool:
        """Send ``batch``; return whether the next one may follow."""
        try:
            self._send(batch)
        except RunEventsUnsupported:
            self._stop()
            logger.info("run activity | the server does not record it; not sent")
            return False
        except (RunAlreadyFinished, ExecutorRejected):
            # The run is over: its run token is revoked, or it is no longer
            # running. Nothing more is accepted, and nothing went wrong.
            self._stop()
            logger.debug("run activity | the run is over; nothing more is sent")
            return False
        except (ValueError, TypeError) as exc:
            # Sending it again would be refused again.
            log = logger.debug if self._refused else logger.warning
            log("run activity | %d event(s) refused and dropped: %s", len(batch), exc)
            self._refused = True
        except Exception as exc:
            if not self._failing:
                logger.warning(
                    "run activity | could not send %d event(s), retrying: %s",
                    len(batch),
                    exc,
                )
            self._failing = True
            return False
        with self._lock:
            self._in_flight = None
        if self._failing:
            logger.info("run activity | sending again")
            self._failing = False
        return True

    def _stop(self) -> None:
        with self._lock:
            self._stopped = True
            self._queue.clear()
            self._in_flight = None


__all__ = [
    "Activity",
    "ActivityRelay",
    "Redactor",
    "activity_for_outcome",
    "activity_from_event",
    "activity_from_record",
]
