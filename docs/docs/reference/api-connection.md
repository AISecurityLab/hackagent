---
title: "API connection settings"
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
