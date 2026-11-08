---
sidebar_label: proxy
title: hackagent.interfaces.web._proxy
---

Remote mode: forward the SPA&#x27;s API calls to the hosted HackAgent API.

This replaces the Next.js route handler the webapp used to carry
(`src/app/api/proxy/[...path]/route.ts`) so the bundle can be a pure static
export with no Node runtime.

Launches are the one call it changes: the dashboard leaves where a run
executes to the deployment, and this deployment is the user&#x27;s machine. So the
proxy launches and preflights every campaign as a `local` run, and hands
each run it launched to `on_launched` to execute here.

Everything else crosses unchanged, the campaign run report routes
(`/run/summary`, `/run/<id>/report`, ...) included: `If-None-Match` goes
up, `ETag`, `Cache-Control` and a `304` come back, so the dashboard&#x27;s
conditional polling works through this hop as it does against the API.

Keeping the indirection matters for more than parity: the API key is read from
the local CLI configuration and attached **here**, so it never reaches the
browser. The SPA runs with authentication disabled and talks only to
`127.0.0.1`; this process is the only thing holding the credential.

#### create\_proxy

```python
def create_proxy(
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
        verify: Union[bool, ssl.SSLContext] = True,
        on_launched: Optional[Callable[[UUID], None]] = None) -> Blueprint
```

Build a blueprint forwarding every request to `base_url` with `api_key`.

A path prefix on `base_url` (`https://host/api`) is kept on every
forwarded request. `verify` is the TLS verification setting.
`on_launched` is given the id of every run a launch queued.

