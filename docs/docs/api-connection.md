---
title: "API connection settings"
slug: "/reference/api-connection"
description: "Base URLs, CA bundles and proxy settings for API clients."
---

These settings apply to connections to the HackAgent API.

## Base URL

Set `HACKAGENT_BASE_URL`, pass `--base-url` to the CLI, or supply
`base_url` to `Settings.resolve(...)`. A base URL may include a path
prefix, with or without a trailing slash:

```bash
export HACKAGENT_BASE_URL=https://api.example.com/prefix
```

API requests preserve the prefix: an endpoint such as `/agent/` is
requested at `https://api.example.com/prefix/agent/`.

## API key

The default platform credential variable is `HACKAGENT_API_KEY`.
Credentials do not select storage: choose `backend: remote` explicitly when
results should be stored remotely.

Python callers can supply a runtime value:

```python
import os
from hackagent import Settings

settings = Settings.resolve(
    api_key=os.environ["HACKAGENT_API_KEY"], backend="remote"
)
```

Configuration files use the same `api_key` field with an explicit reference:

```yaml
api_key: "${HACKAGENT_API_KEY}"
```

Other variables may be selected explicitly with `${VARIABLE}`. Missing or
empty selected variables fail before execution. Literal keys are rejected
in configuration files; resolved values are never written back to them.
Model connections select their own credential explicitly. A platform key
is only supplied automatically to the configured HackAgent gateway.

## CA bundle

TLS certificates are verified. To trust a private certificate authority,
configure a PEM bundle or a directory of hashed CA certificates. Settings
are resolved in this order:

1. The CLI `--ca-bundle` option or `ca_bundle=` in `Settings.resolve(...)`.
2. `REQUESTS_CA_BUNDLE`, then `SSL_CERT_FILE`.
3. `ca_bundle` in the configuration file.
4. The default trust store.

```bash
export SSL_CERT_FILE=/path/to/ca-bundle.pem
```

A configured bundle replaces the default trust store for these API
connections; include any public CAs that are also needed. A missing bundle
produces a configuration error. An untrusted certificate produces a TLS
error with guidance on configuring the CA bundle.

## Proxy

API connections honour `HTTPS_PROXY` and `NO_PROXY`:

```bash
export HTTPS_PROXY=http://proxy.example.com:3128
export NO_PROXY=localhost,127.0.0.1
```

If a proxy intercepts TLS, include its CA in the configured bundle.
