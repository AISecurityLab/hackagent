---
sidebar_label: group
title: hackagent.interfaces.cli.commands.attack.group
---

The `hackagent eval` command group.

#### eval\_cmd

```python
@click.group(name="eval", invoke_without_command=True)
@click.option("--agent-name", help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    show_default=True,
    help=
    "Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    help=
    "Agent endpoint URL. For OpenAI-compatible endpoints, use a base URL ending with /v1.",
)
@click.option(
    "--dataset",
    "dataset_preset",
    default=None,
    help=
    "Dataset preset for evaluation campaign (default: first PRIMARY dataset in JAILBREAK_PROFILE).",
)
@click.option(
    "--limit",
    type=int,
    default=25,
    show_default=True,
    help="Maximum number of goals loaded from the dataset per attack.",
)
@click.option(
    "--judge-identifier",
    default="ollama/llama3",
    show_default=True,
    help="Judge model identifier.",
)
@click.option(
    "--judge-type",
    default="harmbench",
    show_default=True,
    help="Judge evaluator type.",
)
@click.option(
    "--timeout",
    type=int,
    default=300,
    show_default=True,
    help="Per-attack timeout (seconds).",
)
@click.option(
    "--fail-fast/--no-fail-fast",
    default=False,
    show_default=True,
    help="Stop at first failed attack instead of continuing remaining attacks.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate evaluation campaign plan without executing attacks.",
)
@click.pass_context
@handle_errors
def eval_cmd(ctx: click.Context, agent_name: Optional[str], agent_type: str,
             endpoint: Optional[str], dataset_preset: Optional[str],
             limit: int, judge_identifier: str, judge_type: str, timeout: int,
             fail_fast: bool, dry_run: bool) -> None
```

🚀 Evaluate AI agent security.

- `hackagent eval` runs the evaluation campaign.
- `hackagent eval <strategy>` runs a specific attack strategy.

