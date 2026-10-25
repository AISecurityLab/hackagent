# Connecting to a self-hosted API

HackAgent can record runs to, and read results from, a HackAgent API running
on your own infrastructure instead of `https://api.hackagent.dev`. This page
covers the base URL, the API key, private certificate authorities and
corporate proxies.

## Base URL

Point the SDK and the CLI at your deployment with `HACKAGENT_BASE_URL`, the
`--base-url` flag, or `base_url` in the config file
(`~/.config/hackagent/config.json`):

```bash
export HACKAGENT_BASE_URL=https://hackagent.example.com/api
```

The URL may include a **path prefix** (`/api` above), with or without a
trailing slash. Every client keeps it: SDK runs and results, `hackagent
results`, `hackagent config validate` and the `hackagent web` proxy all call
`https://hackagent.example.com/api/<endpoint>`.

The LLM gateway used for attacker and judge models in remote mode lives under
the same prefix (`https://hackagent.example.com/api/v1`). A base URL on
`localhost` / `127.0.0.1` is treated as a local deployment, so role models stay
local; any other host, whatever its path, is treated as a service.

## API key

Remote mode is enabled by an API key issued by your deployment:

```bash
export HACKAGENT_API_KEY=hk_...
# or
hackagent config set --api-key hk_... --base-url https://hackagent.example.com/api
hackagent config validate
```

From Python:

```python
from hackagent import HackAgent, Settings

agent = HackAgent(
    Settings.resolve(
        api_key="hk_...",
        base_url="https://hackagent.example.com/api",
    )
)
```

## Private certificate authority

TLS certificates are always verified; there is no option to turn
verification off. If your API's certificate is issued by a private CA, tell
HackAgent which CA bundle (PEM file, or a directory of hashed certificates) to
trust. In priority order:

1. `--ca-bundle /path/to/ca.pem` on the CLI, or `ca_bundle=` in
   `Settings.resolve(...)`;
2. the `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` environment variable;
3. `ca_bundle` in the config file (`hackagent config set --ca-bundle /path/to/ca.pem`).

```bash
export REQUESTS_CA_BUNDLE=/etc/pki/corp-root-ca.pem
hackagent config validate
```

The bundle replaces the default trust store for API calls, so include any
public CAs you also need. Without the right bundle, calls fail with a TLS
certificate error and a hint naming these options; a configured bundle that
does not exist is reported as `CA bundle not found`.

## Corporate proxy

Outbound HTTP(S) honours the standard proxy variables:

```bash
export HTTPS_PROXY=http://proxy.example.com:3128
export NO_PROXY=localhost,127.0.0.1
```

If the proxy intercepts TLS, add its CA to the bundle configured above.
