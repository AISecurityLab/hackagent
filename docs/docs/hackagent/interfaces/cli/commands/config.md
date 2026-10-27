---
sidebar_label: config
title: hackagent.interfaces.cli.commands.config
---

Configuration Commands

Manage HackAgent CLI configuration settings.

#### config

```python
@click.group()
def config()
```

🔧 Manage HackAgent CLI configuration

#### set

```python
@config.command()
@click.option(
    "--backend",
    type=click.Choice(["local", "remote"]),
    help=
    "Default storage backend (remote reads the key from HACKAGENT_API_KEY)",
)
@click.option("--base-url", help="HackAgent API base URL")
@click.option(
    "--ca-bundle",
    type=click.Path(exists=True, dir_okay=True),
    help="CA bundle (PEM) trusted for the HackAgent API",
)
@click.option(
    "--verbose",
    type=str,
    help="Default verbosity level: 0/error, 1/warning, 2/info, 3/debug",
)
@click.pass_context
@handle_errors
def set(ctx, backend, base_url, ca_bundle, verbose)
```

Set storage, API location, CA bundle and verbosity defaults

#### show

```python
@config.command()
@click.pass_context
@handle_errors
def show(ctx)
```

Show current configuration

#### reset

```python
@config.command()
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
@handle_errors
def reset(ctx, confirm)
```

Reset configuration to defaults

#### validate

```python
@config.command()
@click.pass_context
@handle_errors
def validate(ctx)
```

Validate current configuration

#### import\_config

```python
@config.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.pass_context
@handle_errors
def import_config(ctx, config_file)
```

Import configuration from a file

