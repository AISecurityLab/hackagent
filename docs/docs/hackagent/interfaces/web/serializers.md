---
sidebar_label: _serializers
title: hackagent.interfaces.web._serializers
---

Render `LocalBackend` records in the HackAgent REST wire format.

The bundled web UI is the same single-page app that runs against
`api.hackagent.dev`; its generated client expects Django REST Framework
payloads (snake_case keys, `{count, next, previous, results}` pages). These
functions are the offline-mode adapter: they translate the SQLite-backed
records of `hackagent.storage.records` into exactly those shapes so the
SPA cannot tell the difference.

Fields the local store has no equivalent for (per-request HTTP metadata,
credits, Auth0 identifiers) are emitted as `None`/zero rather than omitted —
the generated client dereferences them unconditionally.

#### LOCAL\_USER\_ID

Identity presented by offline mode. The local store has a single implicit
user; the SPA still needs a stable id/username pair to render headers.

#### paginate

```python
def paginate(items: List[Dict[str, Any]], total: int, page: int,
             page_size: int) -> Dict[str, Any]
```

Wrap `items` in DRF&#x27;s `PageNumberPagination` envelope.

`next`/`previous` are booleans-as-URLs in DRF; the SPA only checks them
for truthiness to decide whether to request another page, so a sentinel
string is enough and avoids having to reconstruct absolute URLs.

#### organization

```python
def organization(org_id: UUID) -> Dict[str, Any]
```

Full Organization payload. Credits are meaningless offline: report 0.

#### result

```python
def result(record: Any, traces: Optional[List[Any]] = None) -> Dict[str, Any]
```

Serialise a result.

`traces` is always present in the wire format (the generated client maps
over it unconditionally); pass `None` for list endpoints, where loading
every trace would turn one page into hundreds of queries.

#### run\_summary

```python
def run_summary(record: Any,
                results: List[Any],
                agent_name: Optional[str] = None,
                attack_type: Optional[str] = None,
                org_id: Optional[UUID] = None) -> Dict[str, Any]
```

Serialise a run with the per-outcome counts the run list renders.

