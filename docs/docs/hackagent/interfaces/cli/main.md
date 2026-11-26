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

Set up HackAgent for the first time.

Asks where results are kept and how much the log says, and saves it.

#### doctor

```python
@cli.command()
@click.pass_context
@handle_errors
def doctor(ctx)
```

Check the setup for common problems.

Says what is missing, and how to fix it: what the terminal app&#x27;s Setup
screen shows.

#### main

```python
def main() -> None
```

Process entry for the `hackagent` console script and frozen binary.

