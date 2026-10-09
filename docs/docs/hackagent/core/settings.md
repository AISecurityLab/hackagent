---
sidebar_label: settings
title: hackagent.core.settings
---

Runtime settings: the single place that resolves credentials and locations.

Every value is resolved with the same priority order::

    explicit argument  &gt;  environment variable  &gt;  config file  &gt;  default

An empty environment variable counts as unset. Nothing is resolved at import
time; call :meth:`Settings.resolve` when the values are needed.

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
            base_url: Optional[str] = None,
            db_path: Optional[str] = None,
            config_path: Optional[Path | str] = None,
            env: Optional[Mapping[str, str]] = None) -> "Settings"
```

Resolve every setting once, from arguments, environment and file.

**Arguments**:

- `api_key` - Explicit API key. `None` means &quot;not given&quot;; an empty
  string explicitly selects local mode.
- `base_url` - Explicit remote API base URL.
- `db_path` - Explicit local database path, or `&quot;:memory:&quot;`.
- `config_path` - Config file to read instead of the default one.
- `env` - Environment mapping (defaults to `os.environ`).
  

**Raises**:

- `ValueError` - If `base_url` is given but empty, or the config file
  cannot be parsed.

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

Remote when an API key is set, local otherwise.

#### uses\_hosted\_gateway

```python
@property
def uses_hosted_gateway() -> bool
```

Whether role models should default to the hosted LLM gateway.

Requires an API key and a base URL that is not this machine, so a
local deployment keeps its attacker and judge local.

#### gateway\_endpoint

```python
@property
def gateway_endpoint() -> str
```

OpenAI-compatible LLM gateway endpoint of the remote API.

