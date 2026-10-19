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

🖥️ Launch the campaign builder

Opens a full-screen app that builds a campaign, checks it as you type, and
runs it. Start from a template or open an existing campaign.yaml.

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

🔍 Diagnose common configuration issues

Checks your setup and provides helpful troubleshooting information.

#### main

```python
def main() -> None
```

Process entry for the `hackagent` console script and frozen binary.

