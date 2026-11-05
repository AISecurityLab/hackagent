---
sidebar_label: local_api
title: hackagent.interfaces.web._local_api
---

Offline REST surface: the HackAgent API contract served from local SQLite.

With the local backend selected, this blueprint answers dashboard requests
from the SQLite store through the facade. Local is the default backend.

`DELETE /run/<id>` deletes a local run. Other write routes return 501.
Start campaigns through the CLI or Python campaign runner.

#### create\_local\_api

```python
def create_local_api(client) -> Blueprint
```

Build the offline REST blueprint backed by a facade `client`.

