---
sidebar_label: settings
title: hackagent.core.settings
---

Runtime settings: the single place that resolves credentials and locations.

Non-secret values are resolved with the same priority order::

    explicit argument  &gt;  environment variable  &gt;  config file  &gt;  default

Empty non-secret environment settings use the next source in that order.
The platform `api_key` defaults to `HACKAGENT_API_KEY`. Python callers pass
resolved values; configuration files contain explicit `${VARIABLE}`
references. Resolved secret values are held in memory. The selected reference
must contain a nonempty value.

The storage backend is chosen explicitly (`local` by default) and never
inferred from the presence of a key. Nothing is resolved at import time; call
:meth:`Settings.resolve` when the values are needed.

#### CA\_BUNDLE\_ENV\_VARS

Standard variables naming a CA bundle to trust, checked in this order.

## Source Objects

```python
class Source(str, Enum)
```

Where a resolved setting came from.

## Mode Objects

```python
class Mode(str, Enum)
```

Where runs are persisted.

#### resolve\_ollama\_base\_url

```python
def resolve_ollama_base_url(env: Optional[Mapping[str, str]] = None) -> str
```

Return the local Ollama base URL, honouring environment overrides.

#### resolve\_remote\_base\_url

```python
def resolve_remote_base_url(env: Optional[Mapping[str, str]] = None) -> str
```

Return the remote API base URL from the environment or the default.

#### resolve\_remote\_role\_endpoint

```python
def resolve_remote_role_endpoint(
        env: Optional[Mapping[str, str]] = None) -> str
```

Return the remote LLM gateway endpoint (base URL + `/v1`).

#### env\_ca\_bundle

```python
def env_ca_bundle(env: Optional[Mapping[str, str]] = None) -> Optional[str]
```

Return the CA bundle named by `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`.

#### ssl\_verify

```python
def ssl_verify(ca_bundle: Optional[str]) -> ssl.SSLContext | bool
```

Return an httpx `verify` value trusting `ca_bundle` (or defaults).

#### tls\_error\_hint

```python
def tls_error_hint(error: BaseException) -> Optional[str]
```

Return :data:`TLS_VERIFY_HINT` if `error` is a certificate failure.

#### read\_config\_file

```python
def read_config_file(path: Path) -> Dict[str, Any]
```

Read a JSON or YAML config file; a missing file is an empty config.

**Raises**:

- `ValueError` - If the file exists but cannot be parsed.

## Settings Objects

```python
@dataclass(frozen=True)
class Settings()
```

Resolved runtime settings. Build one with :meth:`resolve`.

#### resolve

```python
@classmethod
def resolve(cls,
            *,
            api_key: Optional[str] = None,
            backend: Optional[str | Mode] = None,
            base_url: Optional[str] = None,
            db_path: Optional[str] = None,
            config_path: Optional[Path | str] = None,
            env: Optional[Mapping[str, str]] = None,
            ca_bundle: Optional[str] = None) -> "Settings"
```

Resolve every setting once, from arguments, environment and file.

**Arguments**:

- `api_key` - Platform API key value injected at runtime.
- `backend` - `"local"` (default) or `"remote"` storage. Falls
  back to `HACKAGENT_BACKEND`, then `backend` in the config
  file. Remote storage requires a platform API key.
- `base_url` - Explicit remote API base URL.
- `db_path` - Explicit local database path, or `":memory:"`.
- `config_path` - Config file to read instead of the default one.
- `env` - Environment mapping (defaults to `os.environ`).
- `ca_bundle` - CA bundle file (or directory) used to verify the remote
  API&#x27;s TLS certificate, e.g. for a server signed by a private
  CA. Falls back to `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`,
  then to `ca_bundle` in the config file. Checked when a
  remote client is built (:attr:`verify`).
  

**Raises**:

- `CredentialError` - If a selected key is empty or missing, or a
  configuration file contains a literal key.
- `ValueError` - If `base_url` is given but empty, the backend is
  invalid, or the config file cannot be parsed.

#### verify

```python
@property
def verify() -> ssl.SSLContext | bool
```

TLS verification for HTTP clients talking to `base_url`.

`True` (default trust store) unless a CA bundle is configured, in
which case an SSL context trusting that bundle. Never `False`.

#### is\_local\_host

```python
@property
def is_local_host() -> bool
```

Whether `base_url` points at this machine rather than a service.

#### mode

```python
@property
def mode() -> Mode
```

The selected storage backend (never inferred from the API key).

#### uses\_hosted\_gateway

```python
@property
def uses_hosted_gateway() -> bool
```

Whether role models should default to the hosted LLM gateway.

Requires a platform API key and a base URL that is not this machine,
so a local deployment keeps its attacker and judge local. Independent
of the storage backend.

#### gateway\_endpoint

```python
@property
def gateway_endpoint() -> str
```

OpenAI-compatible LLM gateway endpoint of the remote API.

