---
sidebar_label: info
title: hackagent.interfaces.cli.commands.attack.info
---

The `hackagent eval list` and `hackagent eval info` commands.

#### list\_attacks

```python
@eval_cmd.command(name="list")
@click.pass_context
@handle_errors
def list_attacks(ctx)
```

List available attack strategies, grouped by primary category

#### info

```python
@eval_cmd.command()
@click.argument("strategy", type=click.Choice(list(catalog_by_id())))
@click.pass_context
@handle_errors
def info(ctx, strategy)
```

Get detailed information about an attack strategy

