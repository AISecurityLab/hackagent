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

Show what past runs found.

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
    "--limit",
    default=10,
    show_default=True,
    type=click.IntRange(min=1),
    help="How many of the latest campaigns to show.",
)
@click.option("--goals",
              is_flag=True,
              help="List each attack's goals and verdicts.")
@click.pass_context
@handle_errors
def summary(ctx, limit, goals)
```

Show what the latest campaigns found.

Each campaign, then each of its attacks, as the terminal app&#x27;s Results
shows them; with --goals, the goals each attack tried and how each went.

