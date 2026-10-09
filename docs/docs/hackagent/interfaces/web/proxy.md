---
sidebar_label: _proxy
title: hackagent.interfaces.web._proxy
---

Remote mode: forward the SPA&#x27;s API calls to the hosted HackAgent API.

This replaces the Next.js route handler the webapp used to carry
(`src/app/api/proxy/[...path]/route.ts`) so the bundle can be a pure static
export with no Node runtime.

Keeping the indirection matters for more than parity: the API key is read from
the local CLI configuration and attached **here**, so it never reaches the
browser. The SPA runs with authentication disabled and talks only to
`127.0.0.1`; this process is the only thing holding the credential.

#### create\_proxy

```python
def create_proxy(base_url: str,
                 api_key: str,
                 timeout: float = 120.0) -> Blueprint
```

Build a blueprint forwarding every request to `base_url` with `api_key`.

