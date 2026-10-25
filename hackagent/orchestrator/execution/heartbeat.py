# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Background heartbeat of a run being executed.

While a run executes, the server expects a heartbeat every few seconds and
answers it with whether a cancel was requested. :class:`RunHeartbeat` beats on
a daemon thread and turns the answers into two events the executor can watch:
``cancel_requested`` and ``rejected`` (the server no longer accepts this
executor). ``on_change`` runs when either is set, so the executor can cancel
its asyncio task.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from hackagent.storage import ExecutorRejected

if TYPE_CHECKING:
    from hackagent.storage.remote import RemoteBackend

logger = logging.getLogger("hackagent.orchestrator.execution.heartbeat")


class RunHeartbeat:
    """Context manager that heartbeats ``run_id`` every ``interval_s`` seconds."""

    def __init__(
        self,
        store: RemoteBackend,
        run_id: UUID,
        *,
        interval_s: float = 15.0,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._interval_s = interval_s
        self.cancel_requested = threading.Event()
        self.rejected = threading.Event()
        self.on_change: Callable[[], None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> RunHeartbeat:
        self._thread = threading.Thread(
            target=self._run, name=f"heartbeat-{self._run_id}", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._store.heartbeat_run(self._run_id):
                    self._signal(self.cancel_requested)
            except ExecutorRejected:
                self._signal(self.rejected)
                return
            except Exception as exc:
                logger.warning("Heartbeat of run %s failed: %s", self._run_id, exc)
            if self._stop.wait(self._interval_s):
                return

    def _signal(self, event: threading.Event) -> None:
        if event.is_set():
            return
        event.set()
        callback = self.on_change
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logger.warning("Heartbeat on_change callback failed", exc_info=True)
