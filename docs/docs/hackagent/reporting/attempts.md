---
sidebar_label: attempts
title: hackagent.reporting.attempts
---

One goal&#x27;s attempts, paged (`/attempts`) or in full (`/structure`).

Attempts are numbered from 1 in `created_at`, then `id`, order: the
order the conversation happened in, and the one `first_jailbreak_attempt`
of the costs counts in.

#### attempt\_page

```python
def attempt_page(
    rows: Sequence[Attempt],
    count: int,
    page: int,
    page_size: int,
    first: Optional[FirstSuccess],
    query: Iterable[tuple[str, str]] = ()
) -> dict[str, Any]
```

`GET /run/{id}/attempts`: one page of rows (already ordered and cut
by the database), with the page of the first jailbreak. `query` is the
request&#x27;s query parameters, which the page links keep.

#### attack\_structure

```python
def attack_structure(results: Iterable[StructureResult],
                     traces: Iterable[StructureTrace]) -> dict[str, Any]
```

`GET /run/{id}/structure`: a goal&#x27;s whole recorded search in one
attack run, including work that produced no result.

