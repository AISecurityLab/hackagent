---
sidebar_label: campaign
title: hackagent.interfaces.cli.commands.campaign
---

Run declarative campaign files (`campaign.yaml`) from the CLI.

`hackagent campaign run` loads a campaign, applies any run-time endpoint
overrides, waits for local servers, and executes it; `validate` resolves it
(goals, models, judges) without attacking, so configuration errors surface
before a run starts. Both build on
:mod:`hackagent.orchestrator.campaign.overrides`, shared with
`scripts/run_campaign.py`.

#### campaign

```python
@click.group()
def campaign() -> None
```

🎯 Run declarative campaign files (campaign.yaml).

#### run

```python
@campaign.command()
@click.argument("file",
                default="campaign.yaml",
                type=click.Path(dir_okay=False))
@click.option("--dry-run",
              is_flag=True,
              help="Resolve and report without attacking.")
@click.option("--json",
              "as_json",
              is_flag=True,
              help="Emit events and summary as JSON.")
@_endpoint_options
@handle_errors
def run(file: str, dry_run: bool, as_json: bool,
        ollama_endpoint: Optional[str], openai_endpoint: Optional[str],
        judge_endpoint: Optional[str], attacker_endpoint: Optional[str],
        output_directory: Optional[str], concurrency: Optional[int],
        wait_for_ollama: float, ollama_pid: Optional[int],
        wait_for_server: float, server_pid: Optional[int],
        judge_server_pid: Optional[int],
        attacker_server_pid: Optional[int]) -> None
```

Run a campaign file against its (or overridden) model servers.

#### validate

```python
@campaign.command()
@click.argument("file",
                default="campaign.yaml",
                type=click.Path(dir_okay=False))
@handle_errors
def validate(file: str) -> None
```

Resolve a campaign (goals, models, judges) without attacking it.

