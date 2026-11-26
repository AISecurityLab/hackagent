---
sidebar_label: utils
title: hackagent.interfaces.cli.utils
---

CLI Utilities

Common utilities for the HackAgent CLI including error handling,
formatting, and helper functions.

## Failed Objects

```python
class Failed(click.ClickException)
```

A command that failed, said as every failure is: ``✗ what went
wrong`, in the palette&#x27;s colour, rather than Click&#x27;s `Error:``.

#### handle\_errors

```python
def handle_errors(func)
```

Decorator for consistent error handling across CLI commands

#### load\_config\_file

```python
def load_config_file(path: str) -> Dict[str, Any]
```

Load configuration from YAML or JSON file

#### display\_results\_table

```python
def display_results_table(results: Any, title: str = "Results") -> None
```

Display results in a formatted table

#### display\_success

```python
def display_success(message: str) -> None
```

`✓ message`: something done, or a check passed.

#### display\_warning

```python
def display_warning(message: str) -> None
```

`! message`: worth knowing, not a failure.

#### display\_error

```python
def display_error(message: str) -> None
```

`✗ message`: something that failed.

#### display\_info

```python
def display_info(message: str) -> None
```

A message in passing.

#### display\_heading

```python
def display_heading(title: str) -> None
```

A section&#x27;s title, with a blank line above it.

#### display\_hint

```python
def display_hint(what: str, command: str) -> None
```

What to do next, and the command that does it.

#### confirm\_action

```python
def confirm_action(message: str, default: bool = False) -> bool
```

Get user confirmation for dangerous actions

#### format\_duration

```python
def format_duration(seconds: float) -> str
```

Format duration in seconds to human readable format

#### create\_status\_panel

```python
def create_status_panel(title: str,
                        content: str,
                        status: str = "info") -> Panel
```

Create a status panel with appropriate styling

#### launch\_tui

```python
def launch_tui(cli_config,
               initial_tab: str = "dashboard",
               initial_data: dict = None)
```

Launch the TUI application with specified tab and optional initial data

**Arguments**:

- `cli_config` - CLI configuration object
- `initial_tab` - Which tab to show initially (default: &quot;dashboard&quot;)
- `initial_data` - Initial data to pre-fill in the tab (default: None)

