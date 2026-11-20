---
sidebar_label: buckets
title: hackagent.reporting.buckets
---

Classification of evaluation outcomes into reporting buckets.

The only definition of the four buckets. `LocalBackend` registers
:func:`result_bucket` as an SQLite function; the platform API stores its value
on every result so a database can group by it.

A human review of an attempt overrides its automated bucket
(:func:`effective_bucket`); see :mod:`hackagent.reporting.reviews`.

#### JAILBREAK

The buckets a result can fall into.

#### REVIEW\_OUTCOMES

The verdicts a human reviewer can record on an attempt.

#### result\_bucket

```python
def result_bucket(status: Optional[str],
                  notes: Optional[str] = None) -> Bucket
```

Classify a result into one of `jailbreak`/`mitigated`/`error`/`pending`.

#### effective\_bucket

```python
def effective_bucket(automated: Bucket, review: Optional[str]) -> Bucket
```

An attempt&#x27;s bucket once its latest human review is applied.

`review` is the latest review&#x27;s outcome. A jailbreak or mitigated review
replaces the automated bucket; `inconclusive` makes the attempt
`pending` (a reviewer who cannot decide leaves it unresolved, whatever
the judges said); no review, or a withdrawn one (`None`), keeps it.

#### overrides

```python
def overrides(automated: Bucket, review: Optional[str]) -> bool
```

Whether a review&#x27;s outcome changes the automated bucket.

