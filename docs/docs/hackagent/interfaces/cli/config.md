---
sidebar_label: config
title: hackagent.interfaces.cli.config
---

CLI Configuration Management

Adds CLI flags and verbosity on top of :class:`hackagent.core.settings.Settings`,
so the CLI resolves settings exactly like the SDK:
CLI args &gt; Environment &gt; Config file &gt; Default.

API keys come from HACKAGENT_API_KEY or an explicit $\{VARIABLE\} file reference.
The local storage default is independent of credentials.

#### VERBOSITY

How much the terminal&#x27;s log says, by the number of `-v`: what each one
adds. With none, it is the run&#x27;s log from INFO, as every interface shows
it. The configuration file&#x27;s `verbosity` is the same number.

## CLIConfig Objects

```python
class CLIConfig()
```

CLI configuration: resolved settings plus CLI-only options.

#### reload

```python
def reload() -> None
```

Re-resolve every value from CLI flags, environment and config file.

#### save

```python
def save(path: Optional[str] = None)
```

Save non-secret settings and credential references.

#### validate

```python
def validate()
```

Require a nonempty base URL. Credentials are checked during settings resolution.

#### require\_remote

```python
def require_remote()
```

Raise an error if no api_key is set (for commands that need cloud access).

#### source\_of

```python
def source_of(key: str) -> str
```

Where the current value of `key` came from.

#### verbosity

```python
@property
def verbosity() -> int
```

The number of `-v` in effect (:data:`VERBOSITY`), as the
configuration file&#x27;s `verbosity` names it.

#### set\_user\_override

```python
def set_user_override(key: str, value)
```

Explicitly set a configuration value and track it for persistence

