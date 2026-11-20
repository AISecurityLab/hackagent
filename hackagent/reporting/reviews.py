# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Human reviews of attempts: the rule that applies them and their routes.

A reviewer reads an attempt and records their own verdict on it. Reviews are
append-only: each one names the review it replaces (``supersedes``), and a
review whose ``outcome`` is null withdraws the one before it. Only an
attempt's latest review counts. The automated evaluation is never changed.

The latest review decides the attempt's bucket (:func:`effective_bucket`),
so every tally, verdict and rate counts the human decision. ``inconclusive``
counts as ``pending``: a reviewer who cannot decide leaves the attempt
unresolved, whatever the judges said.

Routes, below the API root:

* ``GET /result/{id}/reviews``: the attempt's reviews, newest first
  (:func:`review_history`);
* ``POST /result/{id}/reviews`` with ``{"outcome", "explanation",
  "expected_review_id"}``: record a review (:func:`parse_review`,
  :func:`check_review`), answered ``201`` with :func:`review_created`.

``expected_review_id`` is the latest review the reviewer saw (a withdrawal
included), or null for an attempt they saw unreviewed. When another review
was recorded since, the request is refused with ``409``, so two reviewers
never overwrite each other unknowingly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from hackagent.reporting.buckets import (
    REVIEW_OUTCOMES,
    Bucket,
    ReviewOutcome,
    effective_bucket,
    overrides,
)
from hackagent.reporting.http import BadRequest, Conflict, etag, parse_uuid
from hackagent.reporting.report import iso
from hackagent.reporting.rows import Review

INVALID_REVIEW = (
    "Provide outcome (jailbreak, mitigated, inconclusive, or null to withdraw), "
    "optional explanation text, and expected_review_id (null for the first review)."
)
STALE_REVIEW = "This attempt has a newer review. Reload before saving."
NOTHING_TO_WITHDRAW = "This attempt has no active review to withdraw."
RESULT_NOT_FOUND = "Result not found."

#: Longest explanation a review keeps, in characters.
MAX_EXPLANATION = 10_000


@dataclass(frozen=True)
class ReviewRequest:
    """A parsed ``POST /result/{id}/reviews`` body."""

    outcome: Optional[ReviewOutcome]
    explanation: str
    expected_review_id: Optional[str]


def review_item(review: Review) -> dict[str, Any]:
    """One review as every response renders it."""
    return {
        "id": review.id,
        "result_id": review.result_id,
        "outcome": review.outcome,
        "explanation": review.explanation,
        "reviewer": review.reviewer,
        "created_at": iso(review.created_at),
        "supersedes_review_id": review.supersedes,
    }


def human_review(review: Optional[Review]) -> Optional[dict[str, Any]]:
    """An attempt's ``human_review`` field: its latest review, or null."""
    return review_item(review) if review is not None else None


def review_history(reviews: Iterable[Review]) -> dict[str, Any]:
    """``GET /result/{id}/reviews``: every review, newest first."""
    ordered = sorted(
        reviews, key=lambda review: (review.created_at, review.id), reverse=True
    )
    return {"results": [review_item(review) for review in ordered]}


def review_history_etag(
    query: Iterable[tuple[str, str]], reviews: Iterable[Review]
) -> str:
    """The ETag of ``GET /result/{id}/reviews``: reviews never change, so
    their ids, newest first, identify the response."""
    ordered = sorted(
        reviews, key=lambda review: (review.created_at, review.id), reverse=True
    )
    return etag("reviews", query, [], [review.id for review in ordered])


def parse_review(body: Any) -> ReviewRequest:
    """Validate a ``POST /result/{id}/reviews`` body.

    Raises:
        BadRequest: when the body is not exactly ``outcome``, optional
            ``explanation`` and ``expected_review_id``.
    """
    if not isinstance(body, Mapping) or set(body) - {
        "outcome",
        "explanation",
        "expected_review_id",
    }:
        raise BadRequest(INVALID_REVIEW)
    if "outcome" not in body or "expected_review_id" not in body:
        raise BadRequest(INVALID_REVIEW)
    outcome = body["outcome"]
    explanation = body.get("explanation", "")
    expected = body["expected_review_id"]
    if outcome is not None and outcome not in REVIEW_OUTCOMES:
        raise BadRequest(INVALID_REVIEW)
    if not isinstance(explanation, str) or len(explanation) > MAX_EXPLANATION:
        raise BadRequest(INVALID_REVIEW)
    if expected is not None:
        expected = parse_uuid(expected) if isinstance(expected, str) else None
        if expected is None:
            raise BadRequest(INVALID_REVIEW)
    return ReviewRequest(outcome, explanation.strip(), expected)


def check_review(latest: Optional[Review], request: ReviewRequest) -> None:
    """Refuse a review that does not follow the attempt's latest one.

    Call it with the latest review read under the same lock or transaction
    that records the new one.

    Raises:
        Conflict: another review was recorded after the one the reviewer saw.
        BadRequest: a withdrawal when no review is active.
    """
    if (latest.id if latest is not None else None) != request.expected_review_id:
        raise Conflict(STALE_REVIEW)
    if request.outcome is None and (latest is None or latest.outcome is None):
        raise BadRequest(NOTHING_TO_WITHDRAW)


def review_created(
    review: Review,
    *,
    run_id: str,
    goal_index: Optional[int],
    automated_bucket: Bucket,
) -> dict[str, Any]:
    """``POST /result/{id}/reviews`` (``201``): the review and the attempt's
    buckets after it."""
    return {
        **review_item(review),
        "attempt": {
            "id": review.result_id,
            "run_id": run_id,
            "goal_index": goal_index,
            "bucket": effective_bucket(automated_bucket, review.outcome),
            "automated_bucket": automated_bucket,
        },
    }


__all__ = [
    "INVALID_REVIEW",
    "MAX_EXPLANATION",
    "NOTHING_TO_WITHDRAW",
    "RESULT_NOT_FOUND",
    "REVIEW_OUTCOMES",
    "Review",
    "ReviewOutcome",
    "ReviewRequest",
    "STALE_REVIEW",
    "check_review",
    "effective_bucket",
    "human_review",
    "overrides",
    "parse_review",
    "review_created",
    "review_history",
    "review_history_etag",
    "review_item",
]
