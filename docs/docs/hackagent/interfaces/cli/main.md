---
sidebar_label: main
title: hackagent.interfaces.cli.main
---

HackAgent CLI Main Entry Point

Main command-line interface for HackAgent security testing toolkit.

#### init

```python
@cli.command()
@click.pass_context
@handle_errors
def init(ctx)
```

🚀 Initialize HackAgent CLI configuration

Interactive setup wizard for first-time users.

#### version

```python
@cli.command()
@click.pass_context
@handle_errors
def version(ctx)
```

📋 Show version information

#### tui

```python
@cli.command()
@click.pass_context
@handle_errors
def tui(ctx)
```

🖥️ Launch full-screen Terminal User Interface

Opens an interactive tabbed interface that occupies the whole terminal.
Navigate between tabs to manage agents, execute attacks, view results, and configure settings.


Features:
  • Dashboard - Overview and statistics
  • Agents - Manage AI agents
  • Attacks - Execute security attacks
  • Results - View attack results
  • Config - Configuration management


Keyboard Shortcuts:
  q - Quit
  F5 - Refresh current tab
  Tab - Navigate between UI elements

#### doctor

```python
@cli.command()
@click.pass_context
@handle_errors
def doctor(ctx)
```

🔍 Diagnose common configuration issues

Checks your setup and provides helpful troubleshooting information.

#### main

```python
def main() -> None
```

Process entry for the `hackagent` console script and frozen binary.

