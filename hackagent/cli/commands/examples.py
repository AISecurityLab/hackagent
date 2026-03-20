# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Examples Commands

Launch ready-to-run example scenarios from the CLI.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import click
from rich.console import Console

from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import handle_errors
console = Console()


def _patch_textual_terminal_queries() -> None:
    """Apply compatibility patch for terminals that leak '\x1b[?2048$p' as a visible 'p'."""
    try:
        from textual.drivers.linux_driver import LinuxDriver

        LinuxDriver._query_in_band_window_resize = lambda self: None
    except Exception:
        pass


def _load_ollama_demo_module() -> ModuleType:
    """Load examples/ollama/demo.py as a module."""
    repo_root = Path(__file__).resolve().parents[3]
    demo_path = repo_root / "examples" / "ollama" / "demo.py"

    spec = importlib.util.spec_from_file_location("hackagent_ollama_demo", demo_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load demo module from {demo_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

    try:
        from textual.drivers.linux_inline_driver import LinuxInlineDriver

        LinuxInlineDriver._query_in_band_window_resize = lambda self: None
    except Exception:
        pass


@click.group()
def examples():
    """🧪 Launch built-in examples from the TUI"""
    pass


@examples.command()
@click.pass_context
@handle_errors
def ollama(ctx):
    """Run the Ollama FlipAttack demo in TUI (auto-start)."""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    demo_module = _load_ollama_demo_module()
    if not hasattr(demo_module, "build_ollama_demo_config"):
        raise click.ClickException(
            "examples/ollama/demo.py must define build_ollama_demo_config()"
        )

    demo_cfg = demo_module.build_ollama_demo_config()
    attack_config = demo_cfg.get("attack_config", {})
    agent_cfg = demo_cfg.get("agent", {})

    agent_type_obj = agent_cfg.get("agent_type", "ollama")
    agent_type = getattr(agent_type_obj, "value", str(agent_type_obj)).lower()

    goals = ""
    cfg_goals = attack_config.get("goals")
    if isinstance(cfg_goals, list) and cfg_goals:
        goals = str(cfg_goals[0])

    initial_data = {
        "agent_name": agent_cfg.get("name", "ollama-target"),
        "agent_type": agent_type,
        "endpoint": agent_cfg.get("endpoint", "http://localhost:11434"),
        "goals": goals,
        "timeout": 300,
        "attack_type": attack_config.get("attack_type", "flipattack"),
        "auto_execute_attack": True,
        "agent_adapter_operational_config": agent_cfg.get(
            "adapter_operational_config"
        ),
        "attack_config_overrides": attack_config,
    }

    try:
        from hackagent.cli.tui import HackAgentTUI

        _patch_textual_terminal_queries()
        app = HackAgentTUI(
            cli_config,
            initial_tab="attacks",
            initial_data=initial_data,
        )
        app.run()

    except ImportError:
        console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
        console.print("\n[cyan]💡 Install with:[/cyan]")
        console.print("  uv add textual")
        ctx.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
        ctx.exit(1)
