---
sidebar_label: logs
title: hackagent.interfaces.tui.widgets.logs
---

Attack Log Viewer Component

A reusable Textual widget for displaying live attack execution logs
with syntax highlighting, auto-scrolling, and filtering capabilities.

## AttackLogViewer Objects

```python
class AttackLogViewer(Container)
```

A container widget for displaying attack execution logs in real-time.

This component provides:
- Live log streaming with syntax highlighting
- Color-coded log levels (INFO, WARNING, ERROR)
- Auto-scroll to latest logs
- Manual scroll capability
- Clear logs functionality
- Export logs to file

#### \_\_init\_\_

```python
def __init__(title: str = "Attack Execution Logs",
             show_controls: bool = True,
             max_lines: int = 1000,
             **kwargs)
```

Initialize the log viewer.

**Arguments**:

- `title` - Title to display in the header
- `show_controls` - Whether to show control buttons
- `max_lines` - Maximum number of log lines to retain
- `**kwargs` - Additional keyword arguments for Container

#### compose

```python
def compose() -> ComposeResult
```

Compose the log viewer layout.

#### on\_mount

```python
def on_mount() -> None
```

Called when the widget is mounted.

#### on\_button\_pressed

```python
def on_button_pressed(event: Button.Pressed) -> None
```

Handle button press events.

#### on\_checkbox\_changed

```python
def on_checkbox_changed(event: Checkbox.Changed) -> None
```

React to level-filter toggles by re-rendering the visible log.

#### on\_input\_changed

```python
def on_input_changed(event: Input.Changed) -> None
```

React to the search input (case-insensitive substring filter).

#### add\_log

```python
def add_log(message: str, level: str = "INFO") -> None
```

Append a log message; respects current level/search filters.

#### add\_step\_header

```python
def add_step_header(step_name: str, step_number: int = 0) -> None
```

Append a step banner. Always visible regardless of level filters.

#### clear\_logs

```python
def clear_logs() -> None
```

Clear all log messages from the viewer.

#### save\_logs\_to\_file

```python
def save_logs_to_file() -> "Optional[str]"
```

Save current (filtered) log text to a timestamped temp file.

#### copy\_logs

```python
def copy_logs() -> bool
```

Copy currently visible logs to the clipboard.

Uses the shared clipboard helper (OSC 52 → OS tools → pyperclip → file).

**Returns**:

  True if logs were copied successfully, False otherwise.

#### view\_in\_pager

```python
def view_in_pager() -> None
```

View currently visible logs in $PAGER / less for navigation.

#### toggle\_auto\_scroll

```python
def toggle_auto_scroll() -> None
```

Toggle automatic scrolling to latest logs.

#### update\_log\_count

```python
def update_log_count(count: int) -> None
```

Update the log count display.

**Arguments**:

- `count` - Number of log lines currently displayed

#### get\_log\_text

```python
def get_log_text() -> str
```

All log text as a plain string — currently visible records only.

#### load\_logs\_from\_buffer

```python
def load_logs_from_buffer(buffer: list[tuple[str, str]]) -> None
```

Load logs from a buffer (e.g., from TUILogHandler).

**Arguments**:

- `buffer` - List of (message, level) tuples

