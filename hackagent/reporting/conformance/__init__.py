# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The sample and the responses every campaign run report server must return.

Both servers load :func:`sample` into their own store and replay
:func:`cases`; any difference from the expected response is a failure on
that side. See ``README.md`` next to this module for the sample's format and
how to load it.

Usage, from any project with ``hackagent`` installed::

    from hackagent.reporting import conformance

    data = conformance.sample()          # load it into the store
    for case in conformance.cases():
        if case.mutates: reload the store first
        response = client.generic(case.method, prefix + case.path,
                                  query_string=case.query, headers=case.headers,
                                  json=case.body)
        assert response.status_code == case.status
        if case.etag: assert response.headers["ETag"] == case.etag
        if case.expected is not None:
            assert conformance.normalized(response.json()) == case.expected
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Optional


@dataclass(frozen=True)
class Case:
    """One request and the response it must get.

    ``path`` is below the API root (``/run/summary``; the local server serves
    it at ``/api/proxy/run/summary``). ``query`` is a list of ``(key, value)``
    pairs in request order. ``body`` is a JSON request body, or None.
    ``expected`` is the :func:`normalized` JSON response body, or None for a
    response without one (``204``, ``304``). ``etag`` is the response's
    ``ETag``, or None when it has none (errors, writes). A case that
    ``mutates`` changes the store: run it against a freshly loaded sample.
    """

    name: str
    method: str
    path: str
    query: list[tuple[str, str]] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    status: int = 200
    etag: Optional[str] = None
    expected: Any = None
    mutates: bool = False


def _read(name: str) -> Any:
    return json.loads(
        resources.files(__name__).joinpath(name).read_text(encoding="utf-8")
    )


def sample() -> dict[str, Any]:
    """The canonical sample: agents, campaigns, attacks, campaign runs,
    attack runs, results and traces (a fresh copy on every call)."""
    return _read("sample.json")


def cases() -> list[Case]:
    """Every case, in the order they are listed (mutating ones last), read
    afresh on every call."""
    cases = []
    for item in _read("cases.json"):
        expected = item.pop("expected", None)
        cases.append(
            Case(
                **{
                    **item,
                    "query": [tuple(pair) for pair in item.get("query", [])],
                    "expected": _read(f"expected/{expected}") if expected else None,
                }
            )
        )
    return cases


def normalized(body: Any) -> Any:
    """A response body as the cases compare it: a page's ``next`` and
    ``previous`` links, whose form is each server's own, become booleans."""
    if isinstance(body, dict) and {"count", "next", "previous", "results"} <= set(body):
        return {
            **body,
            "next": body["next"] is not None,
            "previous": body["previous"] is not None,
        }
    return body


__all__ = ["Case", "cases", "normalized", "sample"]
