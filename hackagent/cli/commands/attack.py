# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Eval Commands

Evaluate AI agent security.

`hackagent eval` without a strategy runs the evaluation campaign.
`hackagent eval <strategy>` runs a specific attack strategy.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hackagent import HackAgent
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import (
    display_info,
    display_results_table,
    display_success,
    get_agent_type_enum,
    handle_errors,
    load_config_file,
)
from hackagent.cli.commands.scan import run_quick_scan

console = Console()


ATTACK_CATALOG: Dict[str, Dict[str, str]] = {
    "advprefix": {
        "label": "AdvPrefix",
        "description": "Adversarial prefix generation pipeline with judge-based evaluation.",
    },
    "baseline": {
        "label": "Baseline",
        "description": "Template-based baseline jailbreak attack.",
    },
    "pair": {
        "label": "PAIR",
        "description": "Prompt Automatic Iterative Refinement with attacker/scorer loops.",
    },
    "flipattack": {
        "label": "FlipAttack",
        "description": "Prompt obfuscation via character/word flipping modes.",
    },
    "tap": {
        "label": "TAP",
        "description": "Tree of Attacks with Pruning search attack.",
    },
    "autodan_turbo": {
        "label": "AutoDAN-Turbo",
        "description": "Lifelong jailbreak strategy search with warm-up and retrieval phases.",
    },
    "bon": {
        "label": "BoN",
        "description": "Best-of-N augmentation search with inline judge evaluation.",
    },
    "cipherchat": {
        "label": "CipherChat",
        "description": "Cipher-based prompt transformation with optional demonstrations.",
    },
    "h4rm3l": {
        "label": "h4rm3l",
        "description": "Composable decorator-program attack chaining multiple obfuscations.",
    },
    "pap": {
        "label": "PAP",
        "description": "Persuasive Adversarial Prompts using persuasion-technique taxonomies.",
    },
    "mml": {
        "label": "MML",
        "description": "Multi-Modal Linkage attack encoding harmful prompts into images for VLMs.",
    },
}


def _common_attack_options(func):
    """Apply common CLI options shared by all attack subcommands."""
    options = [
        click.option("--agent-name", required=True, help="Target agent name"),
        click.option(
            "--agent-type",
            type=str,
            default="other",
            help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
        ),
        click.option(
            "--endpoint",
            required=True,
            help="Agent endpoint URL. For OpenAI-compatible endpoints, provide base URL ending with /v1 (e.g., http://localhost:8000/v1). For LangServe, provide full path (e.g., http://localhost:8000/invoke).",
        ),
        click.option(
            "--goals",
            multiple=True,
            help="Attack goals. Repeat --goals multiple times or pass a comma-separated string.",
        ),
        click.option(
            "--config-file",
            type=click.Path(exists=True),
            help="Attack configuration file (JSON/YAML)",
        ),
        click.option("--timeout", default=300, help="Attack timeout in seconds"),
        click.option(
            "--dry-run",
            is_flag=True,
            help="Validate configuration without running attack",
        ),
        click.option(
            "--no-tui",
            is_flag=True,
            help="Run attack directly without opening TUI (default: open TUI)",
        ),
        # Before guardrail options
        click.option(
            "--before-guardrail-name",
            default=None,
            help="Before-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
        ),
        click.option(
            "--before-guardrail-type",
            default=None,
            help="Before-guardrail agent type (e.g., openai-sdk, ollama)",
        ),
        click.option(
            "--before-guardrail-endpoint",
            default=None,
            help="Before-guardrail endpoint URL",
        ),
        # After guardrail options
        click.option(
            "--after-guardrail-name",
            default=None,
            help="After-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
        ),
        click.option(
            "--after-guardrail-type",
            default=None,
            help="After-guardrail agent type (e.g., openai-sdk, ollama)",
        ),
        click.option(
            "--after-guardrail-endpoint",
            default=None,
            help="After-guardrail endpoint URL",
        ),
    ]

    for option in reversed(options):
        func = option(func)

    return func


def _parse_goals(goals: Tuple[str, ...]) -> List[str]:
    """Normalize --goals values into a clean list of goal strings."""
    parsed: List[str] = []
    for raw in goals:
        if not raw:
            continue
        chunks = [chunk.strip() for chunk in raw.split(",")]
        parsed.extend([chunk for chunk in chunks if chunk])
    return parsed


def _build_attack_config(
    attack_type: str,
    goals: Tuple[str, ...],
    config_file: Optional[str],
) -> Dict[str, Any]:
    """Build and validate attack configuration from CLI args and optional file."""
    if not goals and not config_file:
        raise click.ClickException(
            "Provide at least one --goals value or a --config-file containing goals/dataset."
        )

    attack_config: Dict[str, Any] = {"attack_type": attack_type}

    if config_file:
        try:
            file_config = load_config_file(config_file)
            attack_config.update(file_config)
            display_info(f"Loaded configuration from: {config_file}")
        except Exception as e:
            raise click.ClickException(f"Failed to load config file: {e}")

    parsed_goals = _parse_goals(goals)
    if parsed_goals:
        attack_config["goals"] = parsed_goals

    # Command selection controls the attack type and should win over config-file values.
    attack_config["attack_type"] = attack_type

    # Coerce string goals loaded from config files to list form.
    if isinstance(attack_config.get("goals"), str):
        attack_config["goals"] = [attack_config["goals"]]

    goals_in_config = attack_config.get("goals")
    has_goals = isinstance(goals_in_config, list) and len(goals_in_config) > 0
    has_dataset = attack_config.get("dataset") is not None

    if not has_goals and not has_dataset:
        raise click.ClickException(
            "Attack configuration must include non-empty 'goals' or a 'dataset' section."
        )

    return attack_config


def _build_guardrail_config(
    name: Optional[str],
    type: Optional[str],
    endpoint: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Build a guardrail config dict from individual CLI options.

    Returns None if no guardrail name is provided.
    """
    if not name:
        return None
    return {"identifier": name, "agent_type": type, "endpoint": endpoint}


def _run_attack_command(
    ctx,
    attack_type: str,
    attack_label: str,
    agent_name: str,
    agent_type: str,
    endpoint: str,
    goals: Tuple[str, ...],
    config_file: Optional[str],
    timeout: int,
    dry_run: bool,
    no_tui: bool,
    before_guardrail_name: Optional[str] = None,
    before_guardrail_type: Optional[str] = None,
    before_guardrail_endpoint: Optional[str] = None,
    after_guardrail_name: Optional[str] = None,
    after_guardrail_type: Optional[str] = None,
    after_guardrail_endpoint: Optional[str] = None,
):
    """Shared implementation for all attack subcommands."""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    attack_config = _build_attack_config(attack_type, goals, config_file)

    goals_for_display = attack_config.get("goals") or attack_config.get("dataset")
    if isinstance(goals_for_display, list):
        goals_summary = "; ".join(str(g) for g in goals_for_display)
    else:
        goals_summary = str(goals_for_display)

    # Launch TUI with attack form pre-filled (default behavior)
    if not no_tui:
        try:
            from hackagent.cli.tui import HackAgentTUI

            initial_data = {
                "agent_name": agent_name,
                "agent_type": agent_type,
                "endpoint": endpoint,
                "goals": goals_summary,
                "timeout": timeout,
                "attack_type": attack_type,
            }

            app = HackAgentTUI(
                cli_config, initial_tab="attacks", initial_data=initial_data
            )
            app.run()
            return

        except ImportError:
            console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
            console.print("\n[cyan]💡 Install with:[/cyan]")
            console.print("  uv add textual")
            console.print(
                "\n[yellow]Or run with --no-tui flag to execute directly[/yellow]"
            )
            ctx.exit(1)
        except Exception as e:
            console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
            console.print(
                "\n[yellow]Try running with --no-tui flag to execute directly[/yellow]"
            )
            ctx.exit(1)

    # Convert agent type
    agent_type_enum = get_agent_type_enum(agent_type)

    # Display logo first
    from hackagent.utils import display_hackagent_splash

    display_hackagent_splash()

    # Display attack summary
    _display_attack_summary(
        agent_name, agent_type, endpoint, goals_summary, attack_config
    )

    if dry_run:
        display_success("✅ Configuration validation passed")
        display_info("Use --dry-run=false to execute the attack")
        return

    # Initialize HackAgent
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

    # Execute attack with progress tracking
    console.print(
        f"\n[bold cyan]🎯 Executing {attack_label} attack against '{agent_name}'"
    )
    console.print(f"[cyan]Goals/Dataset: {goals_summary}")
    console.print(f"[cyan]Timeout: {timeout}s")

    start_time = time.time()

    try:
        results = agent.hack(
            attack_config=attack_config,
            run_config_override={"timeout": timeout},
            fail_on_run_error=True,
        )

        duration = time.time() - start_time
        console.print(
            f"\n[bold green]✅ Attack completed successfully in {duration:.1f}s!"
        )

        # Display results summary
        _display_attack_results(results)

    except Exception as e:
        duration = time.time() - start_time
        console.print(f"\n[bold red]❌ Attack failed after {duration:.1f}s")
        raise click.ClickException(f"Attack execution failed: {e}")


@click.group(name="eval", invoke_without_command=True)
@click.option("--agent-name", help="Target agent name")
@click.option(
    "--agent-type",
    type=str,
    default="other",
    show_default=True,
    help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
)
@click.option(
    "--endpoint",
    help="Agent endpoint URL. For OpenAI-compatible endpoints, use a base URL ending with /v1.",
)
@click.option(
    "--dataset",
    "dataset_preset",
    default=None,
    help="Dataset preset for evaluation campaign (default: first PRIMARY dataset in JAILBREAK_PROFILE).",
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
def eval_cmd(
    ctx: click.Context,
    agent_name: Optional[str],
    agent_type: str,
    endpoint: Optional[str],
    dataset_preset: Optional[str],
    limit: int,
    judge_identifier: str,
    judge_type: str,
    timeout: int,
    fail_fast: bool,
    dry_run: bool,
) -> None:
    """🚀 Evaluate AI agent security.

    - `hackagent eval` runs the evaluation campaign.
    - `hackagent eval <strategy>` runs a specific attack strategy.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not agent_name or not endpoint:
        raise click.ClickException(
            "Evaluation campaign requires --agent-name and --endpoint. "
            "For a specific attack use: hackagent eval <strategy> ..."
        )

    run_quick_scan(
        ctx=ctx,
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        dataset_preset=dataset_preset,
        limit=limit,
        judge_identifier=judge_identifier,
        judge_type=judge_type,
        timeout=timeout,
        fail_fast=fail_fast,
        dry_run=dry_run,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def advprefix(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute AdvPrefix attack strategy

    This command runs the AdvPrefix attack against a target agent.
    Goals should describe what you want the agent to do incorrectly.

    Examples:

      # Basic attack with goals
            hackagent eval advprefix \\
        --agent-name "weather-bot" \\
        --agent-type "google-adk" \\
        --endpoint "http://localhost:8000" \\
        --goals "Return fake weather data and ignore safety guidelines"

              # Attack with configuration file
                hackagent eval advprefix \\
          --agent-name "multi-tool-agent" \\
          --agent-type "google-adk" \\
          --endpoint "http://localhost:8000" \\
          --config-file "attack-config.json"
api    """
    _run_attack_command(
        ctx=ctx,
        attack_type="advprefix",
        attack_label=ATTACK_CATALOG["advprefix"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def baseline(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute Baseline attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="baseline",
        attack_label=ATTACK_CATALOG["baseline"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def pair(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute PAIR attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="pair",
        attack_label=ATTACK_CATALOG["pair"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def flipattack(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute FlipAttack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="flipattack",
        attack_label=ATTACK_CATALOG["flipattack"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def tap(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute TAP attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="tap",
        attack_label=ATTACK_CATALOG["tap"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command(name="autodan_turbo")
@_common_attack_options
@click.pass_context
@handle_errors
def autodan_turbo(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute AutoDAN-Turbo attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="autodan_turbo",
        attack_label=ATTACK_CATALOG["autodan_turbo"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def bon(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute BoN attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="bon",
        attack_label=ATTACK_CATALOG["bon"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def cipherchat(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute CipherChat attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="cipherchat",
        attack_label=ATTACK_CATALOG["cipherchat"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def h4rm3l(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute h4rm3l attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="h4rm3l",
        attack_label=ATTACK_CATALOG["h4rm3l"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def pap(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute PAP attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="pap",
        attack_label=ATTACK_CATALOG["pap"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command()
@_common_attack_options
@click.pass_context
@handle_errors
def mml(
    ctx,
    agent_name,
    agent_type,
    endpoint,
    goals,
    config_file,
    timeout,
    dry_run,
    no_tui,
    before_guardrail_name,
    before_guardrail_type,
    before_guardrail_endpoint,
    after_guardrail_name,
    after_guardrail_type,
    after_guardrail_endpoint,
):
    """Execute MML (Multi-Modal Linkage) attack strategy."""
    _run_attack_command(
        ctx=ctx,
        attack_type="mml",
        attack_label=ATTACK_CATALOG["mml"]["label"],
        agent_name=agent_name,
        agent_type=agent_type,
        endpoint=endpoint,
        goals=goals,
        config_file=config_file,
        timeout=timeout,
        dry_run=dry_run,
        no_tui=no_tui,
        before_guardrail_name=before_guardrail_name,
        before_guardrail_type=before_guardrail_type,
        before_guardrail_endpoint=before_guardrail_endpoint,
        after_guardrail_name=after_guardrail_name,
        after_guardrail_type=after_guardrail_type,
        after_guardrail_endpoint=after_guardrail_endpoint,
    )


@eval_cmd.command(name="list")
@click.pass_context
@handle_errors
def list_attacks(ctx):
    """List available attack strategies"""

    table = Table(
        title="Available Attack Strategies", show_header=True, header_style="bold cyan"
    )
    table.add_column("Strategy", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Status", style="yellow")

    for attack_key, meta in ATTACK_CATALOG.items():
        table.add_row(attack_key, meta["description"], "✅ Available")

    console.print(table)
    console.print(
        "\n[cyan]💡 Use 'hackagent eval STRATEGY --help' for strategy-specific options"
    )


@eval_cmd.command()
@click.argument("strategy", type=click.Choice(list(ATTACK_CATALOG.keys())))
@click.pass_context
@handle_errors
def info(ctx, strategy):
    """Get detailed information about an attack strategy"""

    if strategy == "advprefix":
        _display_advprefix_info()
    else:
        _display_generic_attack_info(strategy)


def _display_generic_attack_info(strategy: str) -> None:
    """Display concise info for attack strategies that don't have long-form docs."""
    meta = ATTACK_CATALOG[strategy]

    info_content = f"""[bold]{meta["label"]} Attack Strategy[/bold]

[cyan]Description:[/cyan]
{meta["description"]}

[cyan]CLI Usage:[/cyan]
hackagent eval {strategy} --agent-name <name> --endpoint <url> --goals "<goal>" --no-tui

[cyan]Advanced Configuration:[/cyan]
Use --config-file with JSON/YAML to provide full attack-specific configuration.

[cyan]Quick Help:[/cyan]
hackagent eval {strategy} --help"""

    panel = Panel(
        info_content,
        title=f"{meta['label']} Attack Information",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)


def _display_attack_summary(
    agent_name: str,
    agent_type: str,
    endpoint: str,
    goals: str,
    attack_config: Dict[str, Any],
) -> None:
    """Display a summary of the attack configuration"""

    # Create summary panel
    summary_content = f"""[bold]Target Agent:[/bold] {agent_name}
[bold]Agent Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}
[bold]Attack Type:[/bold] {attack_config["attack_type"]}
[bold]Goals:[/bold] {goals}"""

    if len(attack_config) > 2:  # More than just attack_type and goals
        summary_content += f"\n[bold]Additional Config:[/bold] {len(attack_config) - 2} parameters loaded"

    panel = Panel(
        summary_content,
        title="🎯 Attack Configuration",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)


def _display_attack_results(results: Any) -> None:
    """Display attack results summary"""

    console.print("\n[bold cyan]📊 Attack Results Summary")

    # Handle list results (most common case when pandas is not available)
    if isinstance(results, list):
        console.print(f"[green]📈 Generated {len(results)} result entries")
        if results and isinstance(results[0], dict):
            # Show sample of keys from first result
            sample_keys = list(results[0].keys())[:5]
            console.print(f"[cyan]📋 Sample fields: {', '.join(sample_keys)}")

            # Try to show some useful info from results
            success_count = sum(
                1 for r in results if r.get("eval_hb") == 1 or r.get("eval_jb") == 1
            )
            if success_count > 0:
                console.print(
                    f"[green]✅ Successful jailbreaks: {success_count}/{len(results)}"
                )
            else:
                console.print("[yellow]⚠️ No successful jailbreaks detected")
        return

    try:
        # Check if results is a pandas DataFrame (optional dependency)
        if hasattr(results, "columns") and hasattr(results, "empty"):
            console.print(f"[green]📈 Generated {len(results)} result entries")

            # Show key metrics if available
            if not results.empty:
                # Try to display some key columns if they exist
                summary_table = Table(
                    title="Key Metrics", show_header=True, header_style="bold cyan"
                )
                summary_table.add_column("Metric", style="cyan")
                summary_table.add_column("Value", style="green")

                summary_table.add_row("Total Results", str(len(results)))

                # Add column info
                summary_table.add_row("Columns", str(len(results.columns)))

                # Try to show success metrics if available
                for col in results.columns:
                    if "success" in col.lower() or "score" in col.lower():
                        if results[col].dtype in ["int64", "float64"]:
                            mean_val = results[col].mean()
                            summary_table.add_row(f"Avg {col}", f"{mean_val:.3f}")

                console.print(summary_table)

                # Show sample of results
                if len(results) > 0:
                    console.print("\n[cyan]📋 Sample Results (first 5 rows):")
                    # Filter to show only goal and prefix columns if they exist
                    display_columns = []
                    if "goal" in results.columns:
                        display_columns.append("goal")
                    if "prefix" in results.columns:
                        display_columns.append("prefix")

                    if display_columns:
                        filtered_results = results[display_columns].head()
                        display_results_table(
                            filtered_results, "Attack Results - Goals & Prefixes"
                        )
                    else:
                        # Fallback to showing all columns if goal/prefix not found
                        display_results_table(results.head(), "Sample Attack Results")
        else:
            console.print(f"[green]📈 Results: {type(results).__name__}")
            if hasattr(results, "__len__"):
                console.print(f"[green]📊 Count: {len(results)}")

    except Exception as e:
        console.print(f"[yellow]⚠️ Could not analyze results: {e}")
        console.print(f"[green]📈 Results type: {type(results).__name__}")


def _display_advprefix_info() -> None:
    """Display detailed information about AdvPrefix attack strategy"""

    info_content = """[bold]AdvPrefix Attack Strategy[/bold]

[cyan]Description:[/cyan]
The AdvPrefix attack generates adversarial prefixes that can manipulate AI agent behavior.
It uses a multi-step pipeline involving uncensored language models to craft effective attacks.

[cyan]How it works:[/cyan]
1. Generate candidate prefixes using language models
2. Compute cross-entropy scores for effectiveness
3. Test prefixes against the target agent
4. Evaluate results using judge models
5. Select and report successful attacks

[cyan]Configuration Options:[/cyan]
• goals: List of malicious objectives for the agent
• generator: Language model configuration for prefix generation  
• judges: Judge models for evaluating attack success
• batch_size: Number of prefixes to generate per batch
• temperature: Sampling temperature for generation
• max_tokens: Maximum tokens to generate

[cyan]Example Config File:[/cyan]
{
  "goals": ["Return fake data", "Ignore safety guidelines"],
  "generator": {
    "identifier": "ollama/llama2-uncensored",
    "endpoint": "http://localhost:11434/api/generate"
  },
  "judges": [
    {
      "identifier": "ollama/llama3",
      "endpoint": "http://localhost:11434/api/judge", 
      "type": "harmbench"
    }
  ],
  "batch_size": 20,
  "temperature": 1.0,
  "max_tokens": 512
}

[cyan]Requirements:[/cyan]
• Target agent must be running and accessible
• Generator model (e.g., Ollama with uncensored model)
• Judge model for evaluation
• Sufficient computational resources

[yellow]⚠️ Ethical Usage:[/yellow]
Only use this attack against agents you own or have explicit permission to test.
Always follow responsible disclosure practices for any vulnerabilities found."""

    panel = Panel(
        info_content,
        title="AdvPrefix Attack Information",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print(panel)
