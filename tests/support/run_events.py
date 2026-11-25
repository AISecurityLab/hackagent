# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Read a run's log back as an interface does: the lines logged in a block."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from hackagent.core.logging import (
    CAMPAIGN_LOGGER,
    GOALS_LOGGER,
    PACKAGE_LOGGER,
    capture,
    subject_of,
)


@dataclass(frozen=True)
class Line:
    """One record of the run's log: where, how loud, what, and about what."""

    logger: str
    level: int
    text: str
    subject: Mapping[str, Any] = field(default_factory=dict)

    @property
    def campaign(self) -> bool:
        """A line of the campaign's own story."""
        return self.logger == CAMPAIGN_LOGGER

    @property
    def goal(self) -> bool:
        """A goal's result."""
        return self.logger == GOALS_LOGGER


class _Lines(logging.Handler):
    def __init__(
        self, lines: list[Line], then: Optional[Callable[[Line], None]]
    ) -> None:
        super().__init__()
        self.lines = lines
        self.then = then

    def emit(self, record: logging.LogRecord) -> None:
        line = Line(
            record.name, record.levelno, record.getMessage(), dict(subject_of(record))
        )
        self.lines.append(line)
        if self.then is not None:
            self.then(line)


@contextmanager
def recorded_lines(
    then: Optional[Callable[[Line], None]] = None, level: int = logging.INFO
) -> Iterator[list[Line]]:
    """The ``hackagent`` lines logged in the block at ``level`` and above, in
    order; ``then`` is called with each as it is logged, and may raise into
    the code that logged it."""
    lines: list[Line] = []
    # Some test modules switch logging off when they are imported; the lines
    # travel through it, so it is on for the block, and the package logger is
    # opened as an application opens it.
    disabled = logging.root.manager.disable
    package = logging.getLogger(PACKAGE_LOGGER)
    was = package.level
    logging.disable(logging.NOTSET)
    package.setLevel(logging.DEBUG)
    try:
        with capture(_Lines(lines, then), level):
            yield lines
    finally:
        package.setLevel(was)
        logging.disable(disabled)
