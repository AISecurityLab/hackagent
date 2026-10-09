---
sidebar_label: _local_api
title: hackagent.interfaces.web._local_api
---

Offline REST surface: the HackAgent API contract served from local SQLite.

When no API key is configured there is no remote to proxy to, so this blueprint
answers the same routes `api.hackagent.dev` exposes, reading from the
`LocalBackend` the SDK writes its runs into. The bundled SPA therefore works
unchanged offline.

Reads go through the facade. `DELETE /run/&lt;id&gt;` is the one explicit write
(`delete_run`). Launching an attack needs a generator, a judge and credits,
none of which exist offline, so the other write routes answer 501.

#### create\_local\_api

```python
def create_local_api(client) -> Blueprint
```

Build the offline REST blueprint backed by a facade `client`.

