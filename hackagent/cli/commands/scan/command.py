# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent scan <url>`` command."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel

from hackagent import HackAgent
from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import (
    display_info,
    display_success,
    get_agent_type_enum,
    handle_errors,
    load_config_file,
)
from hackagent.router.discovery.scanner import (
    DEFAULT_PLANNER_MODEL,
    PlannerError,
    plan_attack,
)

from hackagent.cli.commands.scan.helpers import (
    DEFAULT_ATTACK_TYPE,
    DEFAULT_GOALS,
    _AUTH_REMINDER,
    _provider_endpoint,
)

console = Console()


@click.command(name="scan")
@click.argument("url")
@click.option(
    "--headed",
    is_flag=True,
    help="Show the browser window instead of running it headless.",
)
@click.option(
    "--input-selector",
    default=None,
    help="CSS selector pinning the chat input box (when the built-in heuristics "
    "can't find it).",
)
@click.option(
    "--reply-selector",
    default=None,
    help="CSS selector pinning the bot's reply element (skips the DOM-diff heuristic).",
)
@click.option(
    "--open-selector",
    default=None,
    help="CSS selector for the chat-launcher bubble to click first, for widgets "
    "that start collapsed (when the built-in launcher heuristics miss it).",
)
@click.option(
    "--accept-cookies/--no-accept-cookies",
    default=True,
    show_default=True,
    help="Accept/dismiss a cookie-consent banner on load (it often overlays the "
    "page and blocks the chat launcher). Use --no-accept-cookies to leave it.",
)
@click.option(
    "--llm-fallback-model",
    default=None,
    help="LiteLLM model used to read the reply from the page only when the DOM "
    "heuristics find nothing.",
)
@click.option(
    "--install-browser/--no-install-browser",
    default=True,
    show_default=True,
    help="Auto-download Chromium (~150 MB, one-time) if it's missing.",
)
@click.option(
    "--timeout",
    default=45,
    show_default=True,
    help="Page-load timeout in seconds.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the target config (and plan, if any) as JSON and exit.",
)
@click.option(
    "--plan",
    "use_planner",
    is_flag=True,
    help="Agentic mode: an LLM inspects the target and chooses the attack "
    "strategy and parameters.",
)
@click.option(
    "--planner-model",
    default=DEFAULT_PLANNER_MODEL,
    show_default=True,
    help="LiteLLM model for the --plan planner. Defaults to a local Ollama model "
    "(no API key; run `ollama pull` for it first).",
)
@click.option(
    "--attack/--no-attack",
    default=True,
    show_default=True,
    help="Red-team the target. On by default; --no-attack just shows the config.",
)
@click.option(
    "--config-file",
    "config_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="YAML/JSON file supplying the attack config (a `goals:` list plus "
    "optional `attacker`, `judge`, `category_classifier`, `parameters`, "
    "`attack_type`). Commas inside goals are preserved here, unlike --goals. "
    "Explicit CLI flags (--goals, --attack-type, --attacker-model, "
    "--judge-model) override the file.",
)
@click.option(
    "--goals",
    multiple=True,
    help="Attack goals. Repeat --goals or pass a comma-separated string.",
)
@click.option(
    "--attack-type",
    default=DEFAULT_ATTACK_TYPE,
    show_default=True,
    help="Attack strategy (tap, pair, flipattack, advprefix…). Ignored when "
    "--plan picks one.",
)
@click.option(
    "--attacker-model",
    default=None,
    help="Override the attacker LLM with any LiteLLM model id "
    "(e.g. openai/gpt-4o-mini, anthropic/claude-sonnet-4-6, ollama_chat/llama3). "
    "Bypasses the auto-selected remote/local attacker. Provider key comes from "
    "the usual env var (OPENAI_API_KEY, ANTHROPIC_API_KEY, …).",
)
@click.option(
    "--judge-model",
    default=None,
    help="Override the judge/scorer LLM with any LiteLLM model id (same form as "
    "--attacker-model). Bypasses the auto-selected remote/local judge.",
)
@click.option(
    "--attack-timeout",
    default=300,
    show_default=True,
    help="Attack timeout in seconds.",
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Run the attack headless instead of opening the TUI.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate the wiring without executing (implies --no-tui).",
)
@click.pass_context
@handle_errors
def scan(
    ctx: click.Context,
    url: str,
    headed: bool,
    input_selector: str,
    reply_selector: str,
    open_selector: str,
    accept_cookies: bool,
    llm_fallback_model: str,
    install_browser: bool,
    timeout: int,
    as_json: bool,
    use_planner: bool,
    planner_model: str,
    attack: bool,
    config_file: Optional[str],
    goals: Tuple[str, ...],
    attack_type: str,
    attacker_model: str,
    judge_model: str,
    attack_timeout: int,
    no_tui: bool,
    dry_run: bool,
) -> None:
    """🌐 Red-team a website's chatbot via a real browser.

    Points the `web` provider at URL: it drives the live page in a browser,
    typing each prompt into the chat widget and reading the reply from the page —
    so it works on any chat UI regardless of transport (WebSocket/SSE/HTTP). Add
    `--plan` to let an LLM choose the strategy; `--no-attack` to just print the
    target config.

    \b
    Examples:
      hackagent scan https://www.example.com
      hackagent scan https://www.example.com --plan
      hackagent scan https://www.example.com --headed --input-selector 'textarea'
      hackagent scan https://www.example.com --config-file goals.yaml --no-tui
      hackagent scan https://www.example.com --no-attack --json
    """
    # Imported lazily to avoid a circular import: attack.py imports
    # ``run_quick_scan`` from this module at load time.
    from hackagent.cli.commands.attack import (
        _display_attack_results,
        _display_attack_summary,
        _parse_goals,
    )
    from hackagent.router.discovery import build_web_target

    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    # The live page IS the target — no endpoint discovery.
    agent_type, config = build_web_target(
        url,
        headless=not headed,
        input_selector=input_selector or None,
        reply_selector=reply_selector or None,
        launcher_selector=open_selector or None,
        dismiss_consent=accept_cookies,
        llm_fallback_model=llm_fallback_model or None,
        timeout=timeout,
    )
    # Carry the browser-install preference for the web provider's first run.
    config["install_browser"] = install_browser

    # Optional config file: supplies a goals list (comma-safe, unlike --goals)
    # plus any attack-config keys (attacker/judge/category_classifier/…). Explicit
    # CLI flags win over the file.
    file_config: Dict[str, Any] = {}
    if config_file:
        file_config = load_config_file(config_file) or {}
        display_info(f"Loaded configuration from: {config_file}")

    file_goals = file_config.get("goals")
    if isinstance(file_goals, str):
        file_goals = [file_goals]

    # --goals (comma-split) overrides the file's goals; the file overrides nothing
    # but the built-in DEFAULT_GOALS fallback.
    user_goals = _parse_goals(goals) or file_goals or None

    # ── Planning (optional, pure LLM reasoning — no target interaction) ──────
    plan = None
    if use_planner:
        if not as_json:
            console.print(
                f"\n[bold cyan]🧠 Planning attack strategy[/bold cyan] "
                f"[dim]({planner_model})[/dim]"
            )
        try:
            with console.status("[bold green]Reasoning over the target…"):
                plan = plan_attack(config, model=planner_model, goals=user_goals)
        except PlannerError as e:
            if as_json:
                console.print_json(data={"plan_error": str(e)})
                return
            console.print(f"[bold red]❌ Planning failed:[/bold red] {e}")
            console.print(
                "[dim]You can still attack with an explicit --attack-type.[/dim]"
            )

    if as_json:
        payload: Dict[str, Any] = {"agent_type": agent_type, "config": config}
        if plan is not None:
            payload["plan"] = {
                "attack_type": plan.attack_type,
                "goals": plan.goals,
                "parameters": plan.parameters,
                "rationale": plan.rationale,
                "confidence": plan.confidence,
                "warnings": plan.warnings,
                "attack_config": plan.to_attack_config(),
            }
        console.print_json(data=payload)
        return

    # ── Show the target ─────────────────────────────────────────────────────
    console.print("\n[bold cyan]Target (web — live browser):[/bold cyan]")
    console.print(f"  [bold]agent_type[/bold] = {agent_type!r}")
    console.print("  [bold]adapter_operational_config[/bold] =")
    console.print_json(data=config)

    if plan is not None:
        console.print(
            Panel(
                plan.summary(),
                title="🧠 Planned attack (LLM-chosen)",
                border_style="magenta",
                padding=(1, 2),
            )
        )

    if not attack:
        console.print(
            "\n[dim]--no-attack: target shown only. Drop the flag to red-team it, "
            "or pass it to `hackagent eval` via --agent-type web --endpoint …[/dim]"
        )
        return

    console.print(f"\n[dim]{_AUTH_REMINDER}[/dim]")

    # ── Wire + red-team ─────────────────────────────────────────────────────
    # The planner (if used) dictates strategy + goals + params; otherwise fall
    # back to the --attack-type / --goals CLI values.
    if plan is not None:
        effective_attack_type = plan.attack_type
        resolved_goals: List[str] = plan.goals
        # The plan dictates strategy/goals/params; the file still contributes any
        # roles the plan leaves unset (e.g. judge, category_classifier).
        planned_attack_config: Dict[str, Any] = {
            **file_config,
            **plan.to_attack_config(),
        }
    else:
        # An explicit --attack-type wins; otherwise honor the file's, else default.
        if attack_type != DEFAULT_ATTACK_TYPE:
            effective_attack_type = attack_type
        else:
            effective_attack_type = file_config.get("attack_type") or attack_type
        resolved_goals = user_goals or list(DEFAULT_GOALS)
        # Base the config on the file (attacker/judge/category_classifier/params),
        # then pin the resolved attack_type and goals on top.
        planned_attack_config = dict(file_config)
        planned_attack_config["attack_type"] = effective_attack_type
        planned_attack_config["goals"] = resolved_goals

    # Explicit attacker/judge overrides — point at any LiteLLM model you control,
    # bypassing the auto-selected remote (HackAgent API) / local (Ollama)
    # defaults. Fully specified so the orchestrator's mode-based defaults don't
    # merge in (e.g.) a mismatched api_key. The endpoint is derived from the
    # model's provider prefix (the backend requires a valid URL). The judge
    # override is mirrored onto every judge-family key since the role name
    # differs per attack (PAIR=scorer, TAP=judge, …).
    if attacker_model:
        planned_attack_config["attacker"] = {
            "identifier": attacker_model,
            "agent_type": "litellm",
            "endpoint": _provider_endpoint(attacker_model),
            "api_key": None,
        }
    if judge_model:
        judge_cfg = {
            "identifier": judge_model,
            "agent_type": "litellm",
            "endpoint": _provider_endpoint(judge_model),
            "api_key": None,
            "type": "harmbench",
        }
        planned_attack_config["judge"] = dict(judge_cfg)
        planned_attack_config["judges"] = [dict(judge_cfg)]
        planned_attack_config["scorer"] = dict(judge_cfg)

    if dry_run:
        no_tui = True

    if not no_tui:
        try:
            from hackagent.cli.tui import HackAgentTUI

            initial_data: Dict[str, Any] = {
                "agent_name": config["name"],
                "agent_type": agent_type,
                "endpoint": config["endpoint"],
                "goals": "; ".join(resolved_goals),
                "timeout": attack_timeout,
                "attack_type": effective_attack_type,
                "agent_adapter_operational_config": config,
            }
            console.print(
                f"[bold cyan]🎯 Launching red-team preset[/bold cyan] "
                f"[dim](target: {config['name']})[/dim]"
            )
            app = HackAgentTUI(
                cli_config, initial_tab="attacks", initial_data=initial_data
            )
            app.run()
            return
        except ImportError:
            console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
            console.print("\n[yellow]Run with --no-tui to execute directly.[/yellow]")
            ctx.exit(1)
        except Exception as e:
            console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
            console.print("\n[yellow]Try --no-tui to execute directly.[/yellow]")
            ctx.exit(1)

    # ── Headless path ───────────────────────────────────────────────────────
    goals_summary = "; ".join(resolved_goals)
    attack_config: Dict[str, Any] = planned_attack_config

    _display_attack_summary(
        config["name"],
        agent_type,
        config["endpoint"],
        goals_summary,
        attack_config,
    )

    if dry_run:
        display_success("✅ Configuration validation passed")
        console.print("[dim]Drop --dry-run to execute the attack[/dim]")
        return

    agent_type_enum = get_agent_type_enum(agent_type)
    with console.status("[bold green]Initializing HackAgent..."):
        try:
            agent = HackAgent(
                name=config["name"],
                endpoint=config["endpoint"],
                agent_type=agent_type_enum,
                api_key=cli_config.api_key,
                base_url=cli_config.base_url,
                adapter_operational_config=config,
            )
            display_success("Target initialized successfully")
        except Exception as e:
            raise click.ClickException(f"Failed to initialize target: {e}")

    console.print(
        f"\n[bold cyan]🎯 Executing {effective_attack_type} attack against "
        f"'{config['name']}'[/bold cyan]"
    )
    start_time = time.time()
    try:
        results = agent.hack(
            attack_config=attack_config,
            run_config_override={"timeout": attack_timeout},
            fail_on_run_error=True,
        )
        duration = time.time() - start_time
        console.print(
            f"\n[bold green]✅ Attack completed in {duration:.1f}s![/bold green]"
        )
        _display_attack_results(results)
    except Exception as e:
        duration = time.time() - start_time
        console.print(f"\n[bold red]❌ Attack failed after {duration:.1f}s[/bold red]")
        raise click.ClickException(f"Attack execution failed: {e}")
