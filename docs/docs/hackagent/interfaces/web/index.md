---
sidebar_label: web
title: hackagent.interfaces.web
---

The HackAgent web UI: the hosted dashboard, served from this process.

`hackagent web` serves a statically exported build of `hackagent-webapp`
(the same single-page app as `app.hackagent.dev`) and answers its API calls
under `/api/proxy`:

* **remote mode** — an API key is configured, so calls are forwarded to
  `api.hackagent.dev` with the key attached server-side (`_proxy`);
* **offline mode** — no API key, so calls are answered from the local SQLite
  store the SDK writes runs into (`_local_api`), read-only.

Either way the browser only ever talks to `127.0.0.1`, and the SPA itself is
identical to the hosted one — there is no second dashboard to keep in sync.

#### API\_PREFIX

Mounted under this prefix because the SPA&#x27;s generated client hardcodes it as
its basePath (`src/lib/apiClient.ts`).

## MissingBundleError Objects

```python
class MissingBundleError(RuntimeError)
```

Raised when this build ships no web UI bundle.

#### runtime\_config

```python
def runtime_config(api_url: str = API_PREFIX) -> Dict[str, Any]
```

The payload the SPA fetches from `/config.json` on boot.

Authentication is reported as disabled: the user already authenticated by
configuring an API key in the CLI, and that key is applied by the proxy.
Asking them to log in again in a browser against a localhost server would
add a round trip and a second credential for no security gain.

#### create\_app

```python
def create_app(client) -> Flask
```

Build the Flask app serving the web UI.

**Arguments**:

- `client` - a :class:`hackagent.client.HackAgent` session. A configured
  API key selects remote proxy mode. Otherwise calls are answered
  from the session&#x27;s local store. `delete_run` is the one local
  write; other writes stay unavailable.
  

**Raises**:

- `MissingBundleError` - this build ships no web UI bundle.
- `ValueError` - `client` was not provided.

