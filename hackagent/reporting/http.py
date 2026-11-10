# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Request parsing, errors, pages and ETags shared by every server.

Both servers parse query parameters with these functions, so a request is
accepted, refused or paged identically, and refuse with the same messages.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlencode
from uuid import UUID

from hackagent.reporting.goals import VERDICTS, GoalFilters

#: Bumped when a response format changes, so cached ETags stop matching.
FORMAT_VERSION = 2

CAMPAIGN_RUN_NOT_FOUND = "Campaign run not found."
ATTACK_RUN_NOT_FOUND = "Attack run not found."
GOAL_INDEX_REQUIRED = "A non-negative goal_index is required."
INVALID_VERDICT = "Invalid goal verdict."
BASELINE_REQUIRED = "A baseline campaign run id is required."
BASELINE_IS_CURRENT = "The baseline must be a different campaign run."
INVALID_SELECTION = "Provide 1 to 100 valid campaign run ids."
ACTIVE_CAMPAIGN_RUN = "An active campaign run cannot be deleted."

#: Page sizes: ``(default, maximum)`` per route.
SUMMARY_PAGE = (20, 100)
GOALS_PAGE = (20, 1000)
ATTEMPTS_PAGE = (20, 100)

#: Cache headers every successful ``GET`` carries, next to its ``ETag``.
CACHE_CONTROL = "private, no-cache"


class ReportError(Exception):
    """A request a server refuses, as ``{"detail": ...}`` with ``status``."""

    status = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail

    def body(self) -> dict[str, str]:
        """Return the JSON error body, ``{"detail": ...}``."""
        return {"detail": self.detail}


class BadRequest(ReportError):
    """A malformed request (HTTP 400)."""

    status = 400


class NotFound(ReportError):
    """A campaign run, attack run or goal that does not exist (HTTP 404)."""

    status = 404


class Conflict(ReportError):
    """A request that conflicts with the resource's state (HTTP 409)."""

    status = 409


def parse_uuid(value: Any) -> Optional[str]:
    """``value`` as a canonical lowercase UUID string, or None."""
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def page_args(args: Mapping[str, str], sizes: tuple[int, int]) -> tuple[int, int]:
    """``(page, page_size)``; invalid values fall back, sizes are clamped."""
    default, maximum = sizes
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(args.get("page_size", default))
    except (TypeError, ValueError):
        page_size = default
    return page, max(1, min(page_size, maximum))


def page_link(query: Iterable[tuple[str, str]], page: int) -> str:
    """The link to ``page`` of the request whose query parameters are
    ``query``: ``?`` and the parameters in request order with every ``page``
    removed and ``page=<page>`` appended, form-encoded
    (:func:`urllib.parse.urlencode`). Both servers emit exactly this."""
    pairs = [(str(key), str(value)) for key, value in query if key != "page"]
    return "?" + urlencode([*pairs, ("page", str(page))])


def paginate(
    items: Sequence[Any],
    count: int,
    page: int,
    page_size: int,
    query: Iterable[tuple[str, str]] = (),
) -> dict[str, Any]:
    """The DRF page envelope, with :func:`page_link` links to the next and
    previous pages of the request whose query parameters are ``query``."""
    query = list(query)
    return {
        "count": count,
        "next": page_link(query, page + 1) if page * page_size < count else None,
        "previous": page_link(query, page - 1) if page > 1 else None,
        "results": list(items),
    }


def page_slice(items: Sequence[Any], page: int, page_size: int) -> list[Any]:
    """Return the items of 1-based ``page`` of ``page_size`` items."""
    start = (page - 1) * page_size
    return list(items[start : start + page_size])


def goal_index_arg(args: Mapping[str, str], *, required: bool) -> Optional[int]:
    """``goal_index`` as a non-negative int; raises :class:`BadRequest`."""
    if "goal_index" not in args:
        if required:
            raise BadRequest(GOAL_INDEX_REQUIRED)
        return None
    try:
        index = int(args["goal_index"])
    except (TypeError, ValueError):
        raise BadRequest(GOAL_INDEX_REQUIRED) from None
    if index < 0:
        raise BadRequest(GOAL_INDEX_REQUIRED)
    return index


def scope_arg(args: Mapping[str, str]) -> Optional[str]:
    """The ``run_id`` a request is scoped to, as given (None when absent)."""
    return args.get("run_id") or None


def goal_filters(args: Mapping[str, str]) -> GoalFilters:
    """The filters of ``/goals``; raises :class:`BadRequest`."""
    index = goal_index_arg(args, required=False)
    verdict = args.get("verdict", "")
    if verdict and verdict not in VERDICTS:
        raise BadRequest(INVALID_VERDICT)
    return GoalFilters(
        goal_index=index,
        category=args.get("category", ""),
        subcategory=args.get("subcategory", ""),
        search=args.get("search", ""),
        verdict=verdict or None,  # type: ignore[arg-type]
    )


def baseline_arg(args: Mapping[str, str], current: str) -> str:
    """The ``baseline`` of ``/compare``; raises :class:`BadRequest`."""
    baseline = parse_uuid(args.get("baseline"))
    if baseline is None:
        raise BadRequest(BASELINE_REQUIRED)
    if baseline == current:
        raise BadRequest(BASELINE_IS_CURRENT)
    return baseline


def selection(body: Any) -> list[str]:
    """The ids of ``POST /run/delete``; raises :class:`BadRequest`."""
    ids = body.get("ids") if isinstance(body, dict) else None
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
        raise BadRequest(INVALID_SELECTION)
    parsed = [parse_uuid(ident) if isinstance(ident, str) else None for ident in ids]
    if any(ident is None for ident in parsed):
        raise BadRequest(INVALID_SELECTION)
    return list(dict.fromkeys(ident for ident in parsed if ident is not None))


def query_pairs(args: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """A request's query parameters in a canonical order, for :func:`etag`:
    sorted by key only, so repeated keys keep their request order (routes
    read a key's first value)."""
    return sorted(((str(key), str(value)) for key, value in args), key=lambda p: p[0])


def etag(
    route: str,
    query: Iterable[tuple[str, str]],
    revisions: Iterable[tuple[str, int]],
    *extra: Any,
) -> str:
    """The weak ETag of a response.

    The SHA-256 of the compact JSON array ``[FORMAT_VERSION, route,
    [[key, value], ...], [[campaign_run_id, revision], ...], *extra]`` (query
    pairs as :func:`query_pairs` orders them, revisions in the order given),
    cut to 32 hex digits:
    ``W/"<digits>"``. ``route`` is the name of the route (``"summary-list"``,
    ``"summary"``, ``"report"``, ``"matrix"``, ``"goals"``, ``"attempts"``,
    ``"structure"``, ``"costs"``, ``"compare"``); ``revisions`` lists every
    campaign run whose data is in the response, and ``extra`` anything else
    it depends on (the list's total).
    """
    payload = json.dumps(
        [
            FORMAT_VERSION,
            route,
            [list(pair) for pair in query_pairs(query)],
            [[ident, int(revision)] for ident, revision in revisions],
            *extra,
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return f'W/"{hashlib.sha256(payload.encode()).hexdigest()[:32]}"'


def etag_matches(if_none_match: Optional[str], tag: str) -> bool:
    """Whether an ``If-None-Match`` header matches ``tag`` (weak comparison)."""
    if not if_none_match:
        return False

    def opaque(value: str) -> str:
        value = value.strip()
        return value[2:] if value.startswith("W/") else value

    wanted = opaque(tag)
    return any(
        candidate.strip() == "*" or opaque(candidate) == wanted
        for candidate in if_none_match.split(",")
    )


__all__ = [
    "ACTIVE_CAMPAIGN_RUN",
    "ATTACK_RUN_NOT_FOUND",
    "ATTEMPTS_PAGE",
    "BASELINE_IS_CURRENT",
    "BASELINE_REQUIRED",
    "BadRequest",
    "CACHE_CONTROL",
    "CAMPAIGN_RUN_NOT_FOUND",
    "Conflict",
    "FORMAT_VERSION",
    "GOALS_PAGE",
    "GOAL_INDEX_REQUIRED",
    "INVALID_SELECTION",
    "INVALID_VERDICT",
    "NotFound",
    "ReportError",
    "SUMMARY_PAGE",
    "baseline_arg",
    "etag",
    "etag_matches",
    "goal_filters",
    "goal_index_arg",
    "page_args",
    "page_link",
    "page_slice",
    "paginate",
    "parse_uuid",
    "query_pairs",
    "scope_arg",
]
