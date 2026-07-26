# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent eval chain`` command."""

import time

import click
from rich.console import Console
from rich.panel import Panel

from hackagent import HackAgent
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import (
    display_success,
    get_agent_type_enum,
    handle_errors,
    load_config_file,
)


from hackagent.cli.commands.attack.config import (
    _build_guardrail_config,
    _parse_goals,
    _summarize_goals_source,
)
from hackagent.cli.commands.attack.display import _display_attack_results
from hackagent.cli.commands.attack.group import eval_cmd


console = Console()


@eval_cmd.command(name="chain")
@click.option("--agent-name", required=True, help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    required=True,
    help="Agent endpoint URL. For OpenAI-compatible endpoints, provide base URL ending with /v1.",
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
    help="Before-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
)
@click.option(
    "--before-guardrail-type",
    default=None,
    help="Before-guardrail agent type (e.g., openai-sdk, ollama)",
)
@click.option(
    "--before-guardrail-endpoint", default=None, help="Before-guardrail endpoint URL"
)
@click.option(
    "--after-guardrail-name",
    default=None,
    help="After-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
)
@click.option(
    "--after-guardrail-type",
    default=None,
    help="After-guardrail agent type (e.g., openai-sdk, ollama)",
)
@click.option(
    "--after-guardrail-endpoint", default=None, help="After-guardrail endpoint URL"
)
@click.pass_context
@handle_errors
def chain(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    config_file,
    goals,
    timeout,
    dry_run,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Run a fallback ladder of attacks against shared goals.

    Each goal starts at the first attack in the chain. A goal that succeeds
    is never retried; a goal that is mitigated escalates to the next attack,
    and so on until it succeeds or the chain is exhausted. This is a thin
    CLI wrapper around ``HackAgent.hack_chain()`` — see its docstring for the
    exact success/mitigation semantics.

    Example ``--config-file`` (YAML):

    \b
        attacks:
          - attack_type: pair
            dataset: {preset: advbench, limit: 25}
            judges: [{identifier: ollama/llama3, type: harmbench}]
          - attack_type: tap
          - attack_type: bon

    Not currently available in the TUI — use ``--no-tui``-style direct
    execution only.
    """
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    try:
        file_config = load_config_file(config_file)
    except Exception as e:
        raise click.ClickException(f"Failed to load config file: {e}")

    attacks = file_config.get("attacks")
    if not isinstance(attacks, list) or not attacks:
        raise click.ClickException(
            "Config file must contain a non-empty top-level 'attacks' list of "
            "attack_config dicts."
        )
    for index, step in enumerate(attacks):
        if not isinstance(step, dict) or not step.get("attack_type"):
            raise click.ClickException(
                f"'attacks[{index}]' must be a dict with an 'attack_type' key."
            )

    parsed_goals = _parse_goals(goals)
    shared_goals = parsed_goals or file_config.get("goals")
    if isinstance(shared_goals, str):
        shared_goals = [shared_goals]

    if not shared_goals:
        first_step = attacks[0]
        has_goals = isinstance(first_step.get("goals"), (list, str)) and first_step.get(
            "goals"
        )
        has_dataset = first_step.get("dataset") is not None
        has_intents = first_step.get("intents") is not None
        if not (has_goals or has_dataset or has_intents):
            raise click.ClickException(
                "Provide --goals, a top-level 'goals' in the config file, or "
                "'goals'/'dataset'/'intents' on attacks[0]."
            )

    goals_summary = (
        "; ".join(str(g) for g in shared_goals)
        if shared_goals
        else _summarize_goals_source(attacks[0])
    )
    attack_chain_summary = " → ".join(str(step["attack_type"]) for step in attacks)

    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    summary_content = f"""[bold]Target Agent:[/bold] {agent_name}
[bold]Agent Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}
[bold]Chain:[/bold] {attack_chain_summary}
[bold]Goals:[/bold] {goals_summary}"""
    console.print(
        Panel(
            summary_content,
            title="🔗 Attack Chain Configuration",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if dry_run:
        display_success("✅ Configuration validation passed")
        return

    agent_type_enum = get_agent_type_enum(agent_type)

    with console.status("[bold green]Initializing HackAgent..."):
        try:
            before_guardrail = _build_guardrail_config(
                before_guardrail_name,
                before_guardrail_type,
                before_guardrail_endpoint,
            )
            after_guardrail = _build_guardrail_config(
                after_guardrail_name,
                after_guardrail_type,
                after_guardrail_endpoint,
            )
            agent = HackAgent(
                name=agent_name,
                endpoint=endpoint,
                agent_type=agent_type_enum,
                api_key=cli_config.api_key,
                base_url=cli_config.base_url,
                before_guardrail=before_guardrail,
                after_guardrail=after_guardrail,
            )
            display_success(f"Agent '{agent_name}' initialized successfully")
        except Exception as e:
            raise click.ClickException(f"Failed to initialize agent: {e}")

    console.print(
        f"\n[bold cyan]🔗 Executing attack chain against '{agent_name}': "
        f"{attack_chain_summary}"
    )

    start_time = time.time()
    try:
        results = agent.hack_chain(
            attacks=attacks,
            goals=shared_goals,
            run_config_override={"timeout": timeout},
            fail_on_run_error=True,
        )
        duration = time.time() - start_time
        console.print(
            f"\n[bold green]✅ Attack chain completed successfully in {duration:.1f}s!"
        )
        _display_attack_results(results)
    except Exception as e:
        duration = time.time() - start_time
        console.print(f"\n[bold red]❌ Attack chain failed after {duration:.1f}s")
        raise click.ClickException(f"Attack chain execution failed: {e}")
