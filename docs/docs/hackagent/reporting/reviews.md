---
sidebar_label: reviews
title: hackagent.reporting.reviews
---

Human reviews of attempts: the rule that applies them and their routes.

A reviewer reads an attempt and records their own verdict on it. Reviews are
append-only: each one names the review it replaces (`supersedes`), and a
review whose `outcome` is null withdraws the one before it. Only an
attempt&#x27;s latest review counts. The automated evaluation is never changed.

The latest review decides the attempt&#x27;s bucket (:func:`effective_bucket`),
so every tally, verdict and rate counts the human decision. `inconclusive`
counts as `pending`: a reviewer who cannot decide leaves the attempt
unresolved, whatever the judges said.

Routes, below the API root:

* `GET /result/{id}/reviews`: the attempt&#x27;s reviews, newest first
  (:func:`review_history`);
* `POST /result/{id}/reviews` with ``\{"outcome", "explanation",
  "expected_review_id"\}``: record a review (:func:`parse_review`,
  :func:`check_review`), answered `201` with :func:`review_created`.

`expected_review_id` is the latest review the reviewer saw (a withdrawal
included), or null for an attempt they saw unreviewed. When another review
was recorded since, the request is refused with `409`, so two reviewers
never overwrite each other unknowingly.

#### MAX\_EXPLANATION

Longest explanation a review keeps, in characters.

## ReviewRequest Objects

```python
@dataclass(frozen=True)
class ReviewRequest()
```

A parsed `POST /result/{id}/reviews` body.

#### review\_item

```python
def review_item(review: Review) -> dict[str, Any]
```

One review as every response renders it.

#### human\_review

```python
def human_review(review: Optional[Review]) -> Optional[dict[str, Any]]
```

An attempt&#x27;s `human_review` field: its latest review, or null.

#### review\_history

```python
def review_history(reviews: Iterable[Review]) -> dict[str, Any]
```

`GET /result/{id}/reviews`: every review, newest first.

#### review\_history\_etag

```python
def review_history_etag(query: Iterable[tuple[str, str]],
                        reviews: Iterable[Review]) -> str
```

The ETag of `GET /result/{id}/reviews`: reviews never change, so
their ids, newest first, identify the response.

#### parse\_review

```python
def parse_review(body: Any) -> ReviewRequest
```

Validate a `POST /result/{id}/reviews` body.

**Raises**:

- `BadRequest` - when the body is not exactly `outcome`, optional
  `explanation` and `expected_review_id`.

#### check\_review

```python
def check_review(latest: Optional[Review], request: ReviewRequest) -> None
```

Refuse a review that does not follow the attempt&#x27;s latest one.

Call it with the latest review read under the same lock or transaction
that records the new one.

**Raises**:

- `Conflict` - another review was recorded after the one the reviewer saw.
- `BadRequest` - a withdrawal when no review is active.

#### review\_created

```python
def review_created(review: Review, *, run_id: str, goal_index: Optional[int],
                   automated_bucket: Bucket) -> dict[str, Any]
```

`POST /result/{id}/reviews` (`201`): the review and the attempt&#x27;s
buckets after it.

