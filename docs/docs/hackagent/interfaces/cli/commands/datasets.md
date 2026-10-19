---
sidebar_label: datasets
title: hackagent.interfaces.cli.commands.datasets
---

Datasets Commands

Browse built-in dataset presets and sample goals for evals.

#### datasets

```python
@click.group()
def datasets()
```

📚 Browse and sample dataset presets

#### list\_cmd

```python
@datasets.command("list")
@click.option(
    "--provider",
    type=click.Choice(
        ["huggingface", "hf", "file", "local", "url_json"],
        case_sensitive=False,
    ),
    help="Filter by provider type",
)
@click.option(
    "--query",
    "-q",
    help="Filter by name or description substring",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
@handle_errors
def list_cmd(provider: Optional[str], query: Optional[str], as_json: bool)
```

List available dataset presets

#### show\_cmd

```python
@datasets.command("show")
@click.argument("preset")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
@handle_errors
def show_cmd(preset: str, as_json: bool)
```

Show details for a dataset preset

#### sample\_cmd

```python
@datasets.command("sample")
@click.argument("preset")
@click.option("--limit",
              default=5,
              show_default=True,
              help="Number of goals to load")
@click.option("--shuffle", is_flag=True, help="Shuffle before selecting")
@click.option("--seed", type=int, help="Random seed used with --shuffle")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON",
)
@handle_errors
def sample_cmd(preset: str, limit: int, shuffle: bool, seed: Optional[int],
               as_json: bool)
```

Load and print sample goals from a dataset preset

