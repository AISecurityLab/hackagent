---
sidebar_label: base
title: hackagent.interfaces.tui.base
---

Base Tab Class

Base class for all TUI tabs with common functionality.

## HackAgentHeader Objects

```python
class HackAgentHeader(Container)
```

Custom header with ASCII logo

## BaseTab Objects

```python
class BaseTab(Container)
```

Base class for all TUI tabs.

Provides common functionality:
- CLI configuration access
- API client creation with timeout
- Error handling helpers
- Refresh mechanism

Subclasses should implement refresh_data() method.

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig, **kwargs)
```

Initialize base tab.

**Arguments**:

- `cli_config` - CLI configuration instance
- `**kwargs` - Additional arguments passed to Container

#### client

```python
def client()
```

Session used for reads. Remote when an API key is configured.

#### handle\_api\_error

```python
def handle_api_error(error: Exception, context: str = "API call") -> str
```

Format API error messages for display.

**Arguments**:

- `error` - The exception that occurred
- `context` - Description of what operation failed
  

**Returns**:

  Formatted error message

#### refresh\_data

```python
def refresh_data() -> None
```

Refresh tab data from API.

Should be overridden by subclasses that need data refresh functionality.
Default implementation does nothing.

#### enable\_auto\_refresh

```python
def enable_auto_refresh(interval: float = 5.0) -> None
```

Enable automatic data refresh at specified interval.

**Arguments**:

- `interval` - Refresh interval in seconds (default: 5.0)

#### disable\_auto\_refresh

```python
def disable_auto_refresh() -> None
```

Disable automatic data refresh.

#### on\_mount

```python
def on_mount() -> None
```

Called when tab is mounted.

Subclasses can override to add custom mounting behavior,
but should call super().on_mount() to ensure proper initialization.

#### on\_show

```python
def on_show() -> None
```

Refresh lazily the first time a hidden tab becomes visible.

