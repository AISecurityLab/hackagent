# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Sending a dropped API request again.

A server may close an idle keep-alive connection at any moment: on its idle
timeout, when a worker process restarts, during a deploy. A request sent on
such a connection fails before any response arrives, and the client cannot
tell whether the server applied it. So only a request that is safe to send
twice is sent again: a read, a PATCH that sets fields, or a write the HackAgent
API keeps once (run events by ``seq``, trace steps by ``sequence``, a result by
its client-chosen ``id``).

A :class:`RetryPolicy` decides; :class:`RetryingTransport` applies it around
each transport of an httpx client (the default one and every proxy mount), so
the client's proxy routing stays as httpx builds it.
"""

from __future__ import annotations

import logging
import re
import socket
import ssl
import time
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger("hackagent.storage.http")

#: Raised after part of the exchange: the connection dropped under the request.
DROPPED = (httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError)
#: Raised before the request left: no connection. Worth a short retry (an API
#: pod restarting refuses connections for a moment), never a long one. A pool
#: timeout is neither: the pool is full, and waiting again would not empty it.
UNREACHABLE = (httpx.ConnectError, httpx.ConnectTimeout)
#: Answers of a proxy or a restarting server, worth asking again.
UNAVAILABLE = frozenset({502, 503, 504})

#: Longest time one request may take, every try and wait included.
BUDGET_S = 90.0
#: Longest time spent on a server that cannot be reached at all.
CONNECT_BUDGET_S = 10.0
FIRST_DELAY_S = 0.25
MAX_DELAY_S = 15.0

_READS = frozenset({"GET", "HEAD", "OPTIONS"})
#: POSTs the API keeps once, matched at the end of the URL path (the base URL
#: may carry a prefix).
_REPEATABLE_POSTS = re.compile(r"/(run/[^/]+/(events|heartbeat)|result/[^/]+/trace)/?$")

Repeatable = Callable[[httpx.Request], bool]


def repeatable_api_call(
    request: httpx.Request, *, result_ids_kept: bool = False
) -> bool:
    """Whether sending ``request`` twice has the same effect as sending it once.

    ``POST /result`` is, once the server has shown it keeps the id the client
    gives a new result (``result_ids_kept``): a repeat then returns the stored
    result instead of creating a second one.
    """
    if request.method in _READS or request.method == "PATCH":
        return True
    if request.method != "POST":
        return False
    path = request.url.path
    if _REPEATABLE_POSTS.search(path):
        return True
    return result_ids_kept and _is_result_create(path)


def _is_result_create(path: str) -> bool:
    """``POST /result``, and not ``POST /run/{id}/result`` (the SDK never
    sends a client id there)."""
    parts = [part for part in path.split("/") if part]
    return (
        bool(parts) and parts[-1] == "result" and (len(parts) < 3 or parts[-3] != "run")
    )


def _permanent(exc: BaseException) -> bool:
    """A connect error no retry can fix: TLS refused, or a host name that
    does not resolve."""
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ssl.SSLError, socket.gaierror)):
            return True
        current = current.__cause__ or current.__context__
    return False


class RetryPolicy:
    """Which requests a client sends again, and for how long.

    One policy is shared by every transport of a client, so what the client
    learns (:attr:`result_ids_kept`) holds whichever transport a request takes
    and whichever store sharing the client learned it.
    """

    def __init__(
        self,
        *,
        repeatable: Optional[Repeatable] = None,
        budget_s: float = BUDGET_S,
        connect_budget_s: float = CONNECT_BUDGET_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._predicate = repeatable
        self.budget_s = budget_s
        self.connect_budget_s = connect_budget_s
        self.sleep = sleep
        self.clock = clock
        #: Whether the server keeps the id a client gives a new result. Set by
        #: every store that creates results through this client.
        self.result_ids_kept = False

    def repeatable(self, request: httpx.Request) -> bool:
        """Whether ``request`` may be sent again."""
        if self._predicate is not None:
            return self._predicate(request)
        return repeatable_api_call(request, result_ids_kept=self.result_ids_kept)

    def wrap(self, transport: httpx.BaseTransport) -> RetryingTransport:
        """``transport``, sending again what this policy allows."""
        return RetryingTransport(transport, policy=self)

    def install(self, client: httpx.Client) -> httpx.Client:
        """Wrap every transport of ``client``: its default one and each
        mount (the proxies httpx set up from the environment)."""
        client._transport = self.wrap(client._transport)
        client._mounts = {
            pattern: None if transport is None else self.wrap(transport)
            for pattern, transport in client._mounts.items()
        }
        return client


class RetryingTransport(httpx.BaseTransport):
    """Wraps ``inner``: a repeatable request whose connection dropped, that
    could not connect, or that was answered 502/503/504, is sent again after
    a growing delay while the policy's time budget lasts. Any other request
    goes through once. Without a ``policy``, one is made from ``options``
    (see :class:`RetryPolicy`)."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        policy: Optional[RetryPolicy] = None,
        **options: Any,
    ) -> None:
        self._inner = inner
        self.policy = policy if policy is not None else RetryPolicy(**options)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        policy = self.policy
        started = policy.clock()
        delay = FIRST_DELAY_S
        tries = 1
        while True:
            try:
                response = self._inner.handle_request(request)
            except UNREACHABLE as exc:
                budget = min(policy.budget_s, policy.connect_budget_s)
                if _permanent(exc) or not self._again(request, started, delay, budget):
                    raise
                cause = f"{type(exc).__name__}: {exc}"
            except DROPPED as exc:
                if not self._again(request, started, delay, policy.budget_s):
                    raise
                cause = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in UNAVAILABLE or not self._again(
                    request, started, delay, policy.budget_s
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
            policy.sleep(delay)
            delay = min(delay * 2, MAX_DELAY_S)

    def _again(
        self, request: httpx.Request, started: float, delay: float, budget: float
    ) -> bool:
        """Whether another try, after ``delay``, still fits ``budget``."""
        elapsed = self.policy.clock() - started
        return elapsed + delay <= budget and self.policy.repeatable(request)

    def close(self) -> None:
        self._inner.close()
