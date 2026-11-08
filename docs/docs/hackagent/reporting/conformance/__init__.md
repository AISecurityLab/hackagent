---
sidebar_label: conformance
title: hackagent.reporting.conformance
---

The sample and the responses every campaign run report server must return.

Both servers load :func:`sample` into their own store and replay
:func:`cases`; any difference from the expected response is a failure on
that side. See `README.md` next to this module for the sample&#x27;s format and
how to load it.

Usage, from any project with `hackagent` installed::

    from hackagent.reporting import conformance

    data = conformance.sample()          # load it into the store
    for case in conformance.cases():
        if case.mutates: reload the store first
        response = client.generic(case.method, prefix + case.path,
                                  query_string=case.query, headers=case.headers,
                                  json=case.body)
        assert response.status_code == case.status
        if case.etag: assert response.headers[&quot;ETag&quot;] == case.etag
        if case.expected is not None:
            assert response.json() == case.expected

## Case Objects

```python
@dataclass(frozen=True)
class Case()
```

One request and the response it must get.

`path` is below the API root (`/run/summary`; the local server serves
it at `/api/proxy/run/summary`). `query` is a list of `(key, value)`
pairs in request order. `body` is a JSON request body, or None.
`expected` is the JSON response body, exactly (page links included, in
the form of :func:`hackagent.reporting.http.page_link`), or None for a
response without one (`204`, `304`). `etag` is the response&#x27;s
`ETag`, or None when it has none (errors, writes). A case that
`mutates` changes the store: run it against a freshly loaded sample.

#### sample

```python
def sample() -> dict[str, Any]
```

The canonical sample: agents, campaigns, attacks, campaign runs,
attack runs, results and traces (a fresh copy on every call).

#### cases

```python
def cases() -> list[Case]
```

Every case, in the order they are listed (mutating ones last), read
afresh on every call.

