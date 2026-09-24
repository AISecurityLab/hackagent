---
sidebar_label: config
title: hackagent.interfaces.cli.config
---

CLI Configuration Management

Adds CLI flags and verbosity on top of :class:`hackagent.core.settings.Settings`,
so the CLI resolves credentials exactly like the SDK:
CLI args &gt; Environment &gt; Config file &gt; Default.

#### VERBOSITY\_ERROR

Only errors

#### VERBOSITY\_WARNING

Errors and warnings

#### VERBOSITY\_INFO

Errors, warnings, and info

#### VERBOSITY\_DEBUG

Everything including debug

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

Save configuration to file.

#### validate

```python
def validate()
```

Validate configuration — warns if no api_key but does NOT raise (local mode).

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

#### set\_user\_override

```python
def set_user_override(key: str, value)
```

Explicitly set a configuration value and track it for persistence

