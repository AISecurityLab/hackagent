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

#### version

```python
@cli.command()
@click.pass_context
@handle_errors
def version(ctx)
```

Show the version, and where the configuration is.

#### tui

```python
@cli.command()
@click.pass_context
@handle_errors
def tui(ctx)
```

Open the terminal app: build, check and run a campaign.

The same as `hackagent` alone. Start from an example or open an
existing campaign.yaml; the app checks it as you type, and runs it.


Keys:
  F1      what this screen is, and every key
  ctrl+r  run the campaign
  ctrl+s  save it to a file
  q       quit

#### doctor

```python
@cli.command()
@click.pass_context
@handle_errors
def doctor(ctx)
```

Check the setup for common problems.

Says what is missing, and how to fix it.

#### main

```python
def main() -> None
```

Process entry for the `hackagent` console script and frozen binary.

