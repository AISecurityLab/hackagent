---
sidebar_label: utils
title: hackagent.interfaces.cli.utils
---

CLI Utilities

Common utilities for the HackAgent CLI including error handling,
formatting, and helper functions.

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

Display success message with formatting

#### display\_warning

```python
def display_warning(message: str) -> None
```

Display warning message with formatting

#### display\_error

```python
def display_error(message: str) -> None
```

Display error message with formatting

#### display\_info

```python
def display_info(message: str) -> None
```

Display info message with formatting

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

