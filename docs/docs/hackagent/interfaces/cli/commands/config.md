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

Show and change the CLI&#x27;s settings.

#### set

```python
@config.command()
@click.option("--backend",
              type=click.Choice(["local", "remote"]),
              help=_setting("backend"))
@click.option("--base-url", help=_setting("base_url"))
@click.option(
    "--ca-bundle",
    type=click.Path(exists=True, dir_okay=True),
    help=_setting("ca_bundle"),
)
@click.option("--verbosity", type=str, help=_setting("verbosity"))
@click.pass_context
@handle_errors
def set(ctx, backend, base_url, ca_bundle, verbosity)
```

Set storage, API location, CA bundle and verbosity defaults

The terminal app&#x27;s Settings screen changes the same settings.

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

#### import\_config

```python
@config.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.pass_context
@handle_errors
def import_config(ctx, config_file)
```

Import configuration from a file

