# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Logger access for library code.

Library modules only obtain loggers; they never install handlers or set
levels. Handler configuration belongs to the application (the CLI does it in
:mod:`hackagent.interfaces.cli.logging_setup`).
"""

import logging
from collections.abc import Mapping
from typing import Any, Optional

#: ``extra=`` for a log line whose fact a campaign progress event reports
#: too. The line still reaches every handler; the run activity relay skips
#: it, so the platform records the fact once, from the event.
REPORTED_AS_EVENT: Mapping[str, bool] = {"reported_as_event": True}

#: Logger of an attack's trace: a record for each node an attack records
#: (:mod:`hackagent.attacks.techniques.trace`), with the node's fields in the
#: record's ``trace_step``. Its DEBUG records quote prompts and replies, so
#: it stays on this machine: the run activity relay never reads it.
TRACE_LOGGER = "hackagent.trace"


def get_logger(name: str) -> logging.Logger:
    """Return the logger called ``name`` without configuring it."""
    return logging.getLogger(name)


def reported_as_event(record: logging.LogRecord) -> bool:
    """Return whether ``record`` was logged with :data:`REPORTED_AS_EVENT`."""
    return bool(getattr(record, "reported_as_event", False))


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
