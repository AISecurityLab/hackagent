---
title: "API connection settings"
slug: "/reference/api-connection"
description: "API keys, result storage, base URLs, CA bundles and proxies."
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

Set `HACKAGENT_API_KEY` before starting the SDK or CLI:

```bash
export HACKAGENT_API_KEY="your_api_key"
```

Settings read this variable when `api_key` is omitted. In Python, pass a
resolved value through `api_key`:

```python
import os
from hackagent import Settings

settings = Settings.resolve(api_key=os.environ["HACKAGENT_API_KEY"])
```

In a YAML or JSON configuration, write an environment reference in `api_key`:

```yaml
api_key: "${HACKAGENT_API_KEY}"
```

The reference is resolved when the configuration is loaded. A missing or
empty referenced variable is a configuration error. Files store references;
resolved secret values stay in memory and are excluded from saved settings
and run metadata.

Model connections use the `api_key` reference written in their connection
configuration. Provider examples name the credential for that provider
explicitly. The default platform key is supplied to the configured HackAgent
gateway only.

## Result storage

Results are stored locally by default. Select `backend="remote"` in SDK
settings or `--backend remote` for CLI sessions to use remote storage.
Campaigns select remote storage with `execution.storage.backend: remote`.
Remote storage requires a valid platform key. Model endpoints determine
where model requests are sent independently of result storage.

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
