---
sidebar_label: http
title: hackagent.reporting.http
---

Request parsing, errors, pages and ETags shared by every server.

Both servers parse query parameters with these functions, so a request is
accepted, refused or paged identically, and refuse with the same messages.

#### FORMAT\_VERSION

Bumped when a response format changes, so cached ETags stop matching.

#### SUMMARY\_PAGE

Page sizes: `(default, maximum)` per route.

#### CACHE\_CONTROL

Cache headers every successful `GET` carries, next to its `ETag`.

## ReportError Objects

```python
class ReportError(Exception)
```

A request a server refuses, as `{"detail": ...}` with `status`.

#### parse\_uuid

```python
def parse_uuid(value: Any) -> Optional[str]
```

`value` as a canonical lowercase UUID string, or None.

#### page\_args

```python
def page_args(args: Mapping[str, str], sizes: tuple[int,
                                                    int]) -> tuple[int, int]
```

`(page, page_size)`; invalid values fall back, sizes are clamped.

#### paginate

```python
def paginate(items: Sequence[Any], count: int, page: int,
             page_size: int) -> dict[str, Any]
```

The DRF page envelope. `next`/`previous` are links whose form is
the server&#x27;s own; clients and the conformance cases only test whether
they are set.

#### goal\_index\_arg

```python
def goal_index_arg(args: Mapping[str, str], *,
                   required: bool) -> Optional[int]
```

`goal_index` as a non-negative int; raises :class:`BadRequest`.

#### scope\_arg

```python
def scope_arg(args: Mapping[str, str]) -> Optional[str]
```

The `run_id` a request is scoped to, as given (None when absent).

#### goal\_filters

```python
def goal_filters(args: Mapping[str, str]) -> GoalFilters
```

The filters of `/goals`; raises :class:`BadRequest`.

#### baseline\_arg

```python
def baseline_arg(args: Mapping[str, str], current: str) -> str
```

The `baseline` of `/compare`; raises :class:`BadRequest`.

#### selection

```python
def selection(body: Any) -> list[str]
```

The ids of `POST /run/delete`; raises :class:`BadRequest`.

#### query\_pairs

```python
def query_pairs(args: Iterable[tuple[str, str]]) -> list[tuple[str, str]]
```

A request&#x27;s query parameters in a canonical order, for :func:`etag`.

#### etag

```python
def etag(route: str, query: Iterable[tuple[str, str]],
         revisions: Iterable[tuple[str, int]], *extra: Any) -> str
```

The weak ETag of a response.

The SHA-256 of the compact JSON array ``[FORMAT_VERSION, route,
[[key, value], ...], [[campaign_run_id, revision], ...], *extra]`` (query
pairs sorted, revisions in the order given), cut to 32 hex digits:
`W/"<digits>"`. `route` is the name of the route (`"summary-list"`,
`"summary"`, `"report"`, `"matrix"`, `"goals"`, `"attempts"`,
`"structure"`, `"costs"`, `"compare"`); `revisions` lists every
campaign run whose data is in the response, and `extra` anything else
it depends on (the list&#x27;s total).

#### etag\_matches

```python
def etag_matches(if_none_match: Optional[str], tag: str) -> bool
```

Whether an `If-None-Match` header matches `tag` (weak comparison).

