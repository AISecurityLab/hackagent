---
sidebar_label: local_api
title: hackagent.interfaces.web._local_api
---

Offline REST surface: the HackAgent API contract served from local SQLite.

With the local backend selected, this blueprint answers dashboard requests
from the SQLite store through the facade. Local is the default backend.

`DELETE /run/<id>` deletes a local run. The campaign run report routes
(`/run/summary`, `/run/<id>/report`, ...) come from :mod:`._run_reports`.
Campaigns are saved to the local
store and launched on this machine: a launch runs the campaign in this process
(see :mod:`._launcher`), and its parent run and attack runs are served like any
other while their results land. The other write routes (agents, keys, the
account) return 501: they belong to the hosted service. The technique catalogue
and campaign schema need no account either.

#### create\_local\_api

```python
def create_local_api(client) -> Blueprint
```

Build the offline REST blueprint backed by a facade `client`.

