---
sidebar_label: run_reports
title: hackagent.interfaces.web._run_reports
---

Offline campaign run reports: the platform&#x27;s `/run` report routes.

`/run/summary`, `/run/delete` and the detail actions `summary`,
`report`, `goals`, `matrix`, `attempts`, `structure`, `costs` and
`compare` of a campaign run, answered from the local store. The store reads
light rows (mostly its per-goal tallies) and :mod:`hackagent.reporting`
builds every response, as it does on the platform, so the dashboard gets the
same JSON from both.

Every `GET` carries a weak `ETag` computed from the revisions of the
campaign runs in the response, before the response is built: a matching
`If-None-Match` is answered `304` without reading anything else.

#### register\_run\_reports

```python
def register_run_reports(bp: Blueprint, client: Any) -> None
```

Add the campaign run report routes to the offline `bp`.

