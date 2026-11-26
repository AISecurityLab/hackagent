# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""An httpx transport that sends a dropped API request again.

A server may close an idle keep-alive connection at any moment: on its idle
timeout, when a worker process restarts, during a deploy. A request sent on
such a connection fails before any response arrives, and the client cannot
tell whether the server applied it. So only a request that is safe to send
twice is sent again: a read, a PATCH that sets fields, or a write the HackAgent
API keeps once (run events by ``seq``, trace steps by ``sequence``, a result by
its client-chosen ``id``).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Callable

import httpx

logger = logging.getLogger("hackagent.storage.http")

#: Transport errors raised before any response arrived. A read timeout is not
#: one of them: the server may still be working on the request.
DROPPED = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)

#: Answers of a proxy or a restarting server, worth asking again.
UNAVAILABLE = frozenset({502, 503, 504})

#: Longest time spent waiting between tries of one request: enough to ride
#: out an API pod restart.
BUDGET_S = 90.0
FIRST_DELAY_S = 0.25
MAX_DELAY_S = 15.0

_READS = frozenset({"GET", "HEAD", "OPTIONS"})
#: POSTs the API keeps once, matched at the end of the URL path (the base URL
#: may carry a prefix).
_REPEATABLE_POSTS = re.compile(r"/(run/[^/]+/(events|heartbeat)|result/[^/]+/trace)/?$")

Repeatable = Callable[[httpx.Request], bool]


def repeatable_api_call(request: httpx.Request) -> bool:
    """Whether sending ``request`` twice has the same effect as sending it once."""
    if request.method in _READS or request.method == "PATCH":
        return True
    return request.method == "POST" and bool(_REPEATABLE_POSTS.search(request.url.path))


class RetryingTransport(httpx.BaseTransport):
    """Wraps ``inner``: a ``repeatable`` request that was dropped, or answered
    502/503/504, is sent again after a growing delay, until ``budget_s`` of
    waiting is spent. Any other request goes through once."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        repeatable: Repeatable = repeatable_api_call,
        budget_s: float = BUDGET_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        #: Decides which requests may be sent again; replaceable after
        #: construction (RemoteBackend.connect gives it the backend's policy).
        self.repeatable = repeatable
        self._budget_s = budget_s
        self._sleep = sleep

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        waited = 0.0
        delay = FIRST_DELAY_S
        tries = 1
        while True:
            try:
                response = self._inner.handle_request(request)
            except DROPPED as exc:
                if not self._again(request, waited, delay):
                    raise
                cause = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in UNAVAILABLE or not self._again(
                    request, waited, delay
                ):
                    return response
                response.close()
                cause = f"HTTP {response.status_code}"
            tries += 1
            logger.warning(
                "API %s %s failed (%s); sending it again in %.2g s (try %d)",
                request.method,
                request.url.path,
                cause,
                delay,
                tries,
            )
            self._sleep(delay)
            waited += delay
            delay = min(delay * 2, MAX_DELAY_S)

    def _again(self, request: httpx.Request, waited: float, delay: float) -> bool:
        return waited + delay <= self._budget_s and self.repeatable(request)

    def close(self) -> None:
        self._inner.close()
