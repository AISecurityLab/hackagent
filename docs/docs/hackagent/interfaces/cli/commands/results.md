---
sidebar_label: results
title: hackagent.interfaces.cli.commands.results
---

Results Commands

View and manage attack results.

#### results

```python
@click.group()
def results()
```

📊 View and manage attack results

#### list

```python
@results.command()
@click.option("--limit", default=10, help="Number of results to show")
@click.option(
    "--status",
    type=click.Choice(["pending", "running", "completed", "failed"]),
    help="Filter by status",
)
@click.option("--agent", help="Filter by agent name")
@click.option("--attack-type", help="Filter by attack type")
@click.pass_context
@handle_errors
def list(ctx, limit, status, agent, attack_type)
```

List recent attack results

#### show

```python
@results.command()
@click.argument("result_id")
@click.pass_context
@handle_errors
def show(ctx, result_id)
```

Show detailed information about a specific result

#### summary

```python
@results.command()
@click.option(
    "--status",
    type=click.Choice(["pending", "running", "completed", "failed"]),
    help="Filter by status",
)
@click.option("--agent", help="Filter by agent name")
@click.option("--attack-type", help="Filter by attack type")
@click.option("--days",
              default=7,
              help="Number of days to include (default: 7)")
@click.pass_context
@handle_errors
def summary(ctx, status, agent, attack_type, days)
```

Show summary statistics of attack results

