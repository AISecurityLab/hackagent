# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Execute one claimed cloud run in a process of its own.

``hackagent-worker`` starts ``python -m hackagent.interfaces.worker_run``
for each run it claims, with an environment it builds from scratch (see
:func:`hackagent.interfaces.worker.child_environment`), and writes the claim
to its standard input as JSON: ``{"run": ..., "run_token": ...,
"claimed_by": ...}``. The process executes the run with its run token and
exits; whatever the run left behind in the process goes with it.

The exit status tells the worker whether the run was finished:
:data:`EXIT_COMPLETED` or :data:`EXIT_ENDED` when it was, anything else
when the worker must finish it. SIGTERM finishes the run FAILED with
:data:`STOPPED_NOTE`.
"""

from __future__ import annotations

import json
import os
import signal
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import IO, Any, Optional
from uuid import UUID

import httpx

from hackagent.core.logging import get_logger
from hackagent.core.settings import BASE_URL_ENV
from hackagent.interfaces.cli.logging_setup import setup_package_logging
from hackagent.orchestrator.execution import execute_run
from hackagent.storage.remote import ClaimResult, RemoteBackend

logger = get_logger(__name__)

#: The note of a run the worker was stopped in the middle of (SIGTERM).
STOPPED_NOTE = "The cloud worker stopped before the run finished"
#: The run was finished as COMPLETED.
EXIT_COMPLETED = 0
#: The run was finished as FAILED or CANCELLED.
EXIT_ENDED = 3


def read_claim(stream: IO[str]) -> tuple[ClaimResult, str]:
    """The claim the worker wrote to ``stream``, and who claimed it."""
    payload = json.load(stream)
    claim = ClaimResult(run=payload["run"], run_token=payload["run_token"], env={})
    return claim, payload["claimed_by"]


def _unfollowed(response: httpx.Response) -> httpx.Response:
    # A caller that follows redirects by hand reads them from here.
    response.next_request = None
    return response


@contextmanager
def redirects_refused() -> Iterator[None]:
    """No HTTP client of this process follows a redirect meanwhile.

    Every request is sent as if ``follow_redirects=False``: a 3xx reply is
    the reply, which the model clients report as an error.
    """
    sync_send, async_send = httpx.Client.send, httpx.AsyncClient.send

    def send(self: httpx.Client, request: httpx.Request, **kwargs: Any) -> Any:
        kwargs["follow_redirects"] = False
        return _unfollowed(sync_send(self, request, **kwargs))

    async def asend(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: Any
    ) -> Any:
        kwargs["follow_redirects"] = False
        return _unfollowed(await async_send(self, request, **kwargs))

    httpx.Client.send = send  # type: ignore[method-assign]
    httpx.AsyncClient.send = asend  # type: ignore[method-assign]
    try:
        yield
    finally:
        httpx.Client.send = sync_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = async_send  # type: ignore[method-assign]


def _stop(signum: int, frame: Optional[FrameType]) -> None:
    # execute_run finishes the run FAILED with STOPPED_NOTE, then re-raises.
    raise KeyboardInterrupt


def main(stream: IO[str] = sys.stdin) -> int:
    """Execute the claim read from ``stream``; returns the exit status."""
    signal.signal(signal.SIGTERM, _stop)
    setup_package_logging(default_level_str="INFO")
    claim, claimed_by = read_claim(stream)
    assert claim.run_token  # a cloud claim always carries one
    base_url = os.environ[BASE_URL_ENV]
    run_id = UUID(str(claim.run["id"]))
    with redirects_refused():
        store = RemoteBackend.connect(base_url, claim.run_token)
        try:
            outcome = execute_run(
                store,
                run_id,
                base_url=base_url,
                gateway_key=claim.run_token,
                claimed_by=claimed_by,
                claim=claim,
                interrupted_as=("FAILED", STOPPED_NOTE),
            )
        except KeyboardInterrupt:
            logger.info("Run %s stopped: it was ended as failed", run_id)
            return EXIT_ENDED
        finally:
            store.close(close_client=True)
    logger.info("Run %s %s: %s", run_id, outcome.status, outcome.note)
    return EXIT_COMPLETED if outcome.status == "COMPLETED" else EXIT_ENDED


if __name__ == "__main__":
    raise SystemExit(main())
