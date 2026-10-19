---
sidebar_label: logger
title: hackagent.interfaces.tui.logger
---

TUI Logging Handler and Decorator

This module provides a thread-safe logging system for displaying attack
execution logs in the TUI. It includes:
- A custom logging handler that captures logs for TUI display
- A decorator that can be applied to any attack&#x27;s run() method
- Thread-safe log transmission to the TUI

## TUILogHandler Objects

```python
class TUILogHandler(logging.Handler)
```

Thread-safe logging handler that captures logs for TUI display.

This handler captures log records and transmits them to the TUI
via a thread-safe callback mechanism. It supports:
- Thread-safe log transmission
- Log level filtering
- Bounded buffer to prevent memory overflow
- Graceful handling of TUI disconnection

#### \_\_init\_\_

```python
def __init__(app: Optional[App] = None,
             callback: Optional[Callable[[str, str], None]] = None,
             max_buffer_size: int = 1000,
             level: int = logging.INFO)
```

Initialize the TUI log handler.

**Arguments**:

- `app` - Textual App instance for thread-safe calls
- `callback` - Function to call with (message, level) for each log
- `max_buffer_size` - Maximum number of logs to buffer
- `level` - Minimum log level to capture (default: INFO)

#### emit

```python
def emit(record: logging.LogRecord) -> None
```

Emit a log record to the TUI.

This method is called by the logging system for each log entry.
It formats the record and transmits it to the TUI via the callback.

**Arguments**:

- `record` - The log record to emit

#### get\_buffer

```python
def get_buffer() -> list[tuple[str, str]]
```

Get all buffered log entries.

**Returns**:

  List of (message, level) tuples

#### clear\_buffer

```python
def clear_buffer() -> None
```

Clear all buffered log entries.

#### deactivate

```python
def deactivate() -> None
```

Deactivate the handler (stop emitting logs).

#### activate

```python
def activate() -> None
```

Activate the handler (resume emitting logs).

