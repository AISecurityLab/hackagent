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

