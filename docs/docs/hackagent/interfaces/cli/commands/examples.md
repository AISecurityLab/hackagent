---
sidebar_label: examples
title: hackagent.interfaces.cli.commands.examples
---

Examples Commands

Launch ready-to-run example scenarios from the CLI.

#### examples

```python
@click.group()
def examples()
```

List, copy and run the example campaigns.

#### list\_examples

```python
@examples.command(name="list")
@handle_errors
def list_examples()
```

List every example campaign.

#### CAMPAIGN\_SCHEMA\_URL

Where the docs site serves the campaign JSON Schema.

#### copy\_example

```python
@examples.command(name="copy")
@click.argument("name")
@click.argument("destination", required=False, type=click.Path(path_type=Path))
@click.option("--force",
              is_flag=True,
              help="Overwrite a file that is already there.")
@handle_errors
def copy_example(name: str, destination: Optional[Path], force: bool)
```

Copy an example campaign here, to edit and run as your own.

DESTINATION is a file or a folder, the current folder by default.

#### run\_example

```python
@examples.command(name="run")
@click.argument("name")
@handle_errors
def run_example(name: str)
```

Run one example by name, starting its target if it has one.

