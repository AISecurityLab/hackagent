---
sidebar_label: chain
title: hackagent.interfaces.cli.commands.attack.chain
---

The `hackagent eval chain` command.

#### chain

```python
@eval_cmd.command(name="chain")
@click.option("--agent-name", required=True, help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    help=
    "Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    required=True,
    help=
    "Agent endpoint URL. For OpenAI-compatible endpoints, provide base URL ending with /v1.",
)
@click.option(
    "--config-file",
    required=True,
    type=click.Path(exists=True),
    help="JSON/YAML file with a top-level 'attacks' list of attack_config dicts "
    "(each needs its own 'attack_type'; only the first needs 'goals'/'dataset'/"
    "'intents' unless a shared '--goals'/'goals' is provided).",
)
@click.option(
    "--goals",
    multiple=True,
    help="Shared goals for the whole chain, overriding goals/dataset/intents on "
    "the first attack. Repeat --goals or pass a comma-separated string.",
)
@click.option("--timeout", default=300, help="Per-attack timeout in seconds")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate configuration without running the chain",
)
@click.option(
    "--before-guardrail-name",
    default=None,
    help=
    "Before-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
)
@click.option(
    "--before-guardrail-type",
    default=None,
    help="Before-guardrail agent type (e.g., openai-sdk, ollama)",
)
@click.option("--before-guardrail-endpoint",
              default=None,
              help="Before-guardrail endpoint URL")
@click.option(
    "--after-guardrail-name",
    default=None,
    help=
    "After-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
)
@click.option(
    "--after-guardrail-type",
    default=None,
    help="After-guardrail agent type (e.g., openai-sdk, ollama)",
)
@click.option("--after-guardrail-endpoint",
              default=None,
              help="After-guardrail endpoint URL")
@click.pass_context
@handle_errors
def chain(ctx, agent_name, agent_type, endpoint, config_file, goals, timeout,
          dry_run, before_guardrail_name, before_guardrail_type,
          before_guardrail_endpoint, after_guardrail_name,
          after_guardrail_type, after_guardrail_endpoint)
```

Run a fallback ladder of attacks against shared goals.

Each goal starts at the first attack in the chain. A goal that succeeds
is never retried; a goal that is mitigated escalates to the next attack,
and so on until it succeeds or the chain is exhausted. This is a thin
CLI wrapper around `HackAgent.hack_chain()` — see its docstring for the
exact success/mitigation semantics.

Example `--config-file` (YAML):


    attacks:
      - attack_type: pair
        dataset: \{preset: advbench, limit: 25\}
        judges: [\{identifier: ollama/llama3, type: harmbench\}]
      - attack_type: tap
      - attack_type: bon

Not currently available in the TUI — use `--no-tui`-style direct
execution only.

