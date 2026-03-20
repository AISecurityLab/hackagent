# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Examples Commands

Launch ready-to-run example scenarios from the CLI.
"""

import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

import click
from rich.console import Console

from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import handle_errors

console = Console()


def _extract_ollama_models_from_demo_cfg(demo_cfg: dict) -> dict[str, str]:
    """Extract target, attacker, and judge Ollama model names from demo config."""
    models: dict[str, str] = {}

    agent_cfg = demo_cfg.get("agent", {})
    adapter_cfg = agent_cfg.get("adapter_operational_config", {})
    target_model = adapter_cfg.get("name")
    if target_model:
        models["target"] = str(target_model)

    attack_cfg = demo_cfg.get("attack_config", {})
    attacker_cfg = attack_cfg.get("attacker", {})
    attacker_model = attacker_cfg.get("identifier")
    if attacker_model:
        models["attacker"] = str(attacker_model)

    judge_cfg = attack_cfg.get("judge", {})
    judge_model = judge_cfg.get("identifier")
    if judge_model:
        models["judge"] = str(judge_model)

    return models


def _is_ollama_running(endpoint: str) -> bool:
    """Check if Ollama server responds on the configured endpoint."""
    base = endpoint if endpoint.endswith("/") else f"{endpoint}/"
    health_url = urljoin(base, "api/tags")

    try:
        with urlopen(health_url, timeout=3):
            return True
    except (URLError, TimeoutError, ValueError):
        return False


def _get_installed_ollama_models() -> set[str]:
    """Return model names currently available in local Ollama."""
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        raise click.ClickException(f"Failed to read local Ollama models: {stderr}")

    models: set[str] = set()
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for line in lines[1:]:
        model_name = line.split()[0]
        if model_name:
            models.add(model_name)
    return models


def _normalize_ollama_model_aliases(model_name: str) -> set[str]:
    """Return equivalent model aliases considering Ollama's implicit :latest tag."""
    aliases = {model_name}
    if ":" in model_name:
        base, tag = model_name.rsplit(":", 1)
        if tag == "latest":
            aliases.add(base)
    else:
        aliases.add(f"{model_name}:latest")
    return aliases


def _is_model_present(model_name: str, installed_models: set[str]) -> bool:
    """Check if model exists locally, accounting for equivalent :latest aliases."""
    aliases = _normalize_ollama_model_aliases(model_name)
    return any(alias in installed_models for alias in aliases)


def _ensure_ollama_models(models_by_role: dict[str, str]) -> None:
    """Ensure required models are available locally; pull missing ones via `ollama run`."""
    if not models_by_role:
        console.print(
            "[yellow]⚠️ No Ollama models found in demo config to validate[/yellow]"
        )
        return

    console.print("[cyan]🔎 Checking local Ollama model catalog...[/cyan]")
    installed = _get_installed_ollama_models()

    role_order = ["target", "judge", "attacker"]
    for role in role_order:
        model_name = models_by_role.get(role)
        if not model_name:
            continue

        if _is_model_present(model_name, installed):
            console.print(
                f"[green]✅ {role.title()} model available:[/green] {model_name}"
            )
            continue

        console.print(f"[yellow]⬇️ {role.title()} model missing:[/yellow] {model_name}")
        console.print(
            f"[cyan]   Pulling model with:[/cyan] ollama run {model_name!s} ping"
        )

        pull_result = subprocess.run(
            ["ollama", "run", model_name, "ping"],
            capture_output=True,
            text=True,
            check=False,
        )
        if pull_result.returncode != 0:
            stderr = pull_result.stderr.strip() or "unknown error"
            raise click.ClickException(
                f"Failed to pull Ollama model '{model_name}' with 'ollama run': {stderr}"
            )

        console.print(f"[green]✅ Model ready:[/green] {model_name}")
        installed.update(_normalize_ollama_model_aliases(model_name))


def _preflight_ollama_requirements(demo_cfg: dict) -> None:
    """Validate Ollama availability and required models before launching the TUI."""
    console.print("[bold cyan]🛠️ Running Ollama preflight checks...[/bold cyan]")

    if shutil.which("ollama") is None:
        console.print("[bold red]❌ Ollama not found in PATH[/bold red]")
        console.print(
            "[yellow]Install Ollama first and retry: https://ollama.ai[/yellow]"
        )
        raise click.ClickException("Ollama is not installed")

    endpoint = demo_cfg.get("agent", {}).get("endpoint") or "http://localhost:11434"
    console.print(f"[cyan]🔎 Checking Ollama server at:[/cyan] {endpoint}")

    if not _is_ollama_running(str(endpoint)):
        console.print("[bold red]❌ Ollama server is not running[/bold red]")
        console.print(
            "[yellow]Install/start Ollama and retry. If already installed, run: ollama serve[/yellow]"
        )
        raise click.ClickException("Ollama server is not reachable")

    console.print("[green]✅ Ollama server is running[/green]")

    required_models = _extract_ollama_models_from_demo_cfg(demo_cfg)
    console.print("[cyan]🔎 Required models from demo config:[/cyan]")
    for role in ["target", "judge", "attacker"]:
        model_name = required_models.get(role)
        if model_name:
            console.print(f"   - {role}: {model_name}")

    _ensure_ollama_models(required_models)
    console.print("[bold green]✅ Ollama preflight checks completed[/bold green]")


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
    _preflight_ollama_requirements(demo_cfg)
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
        "agent_adapter_operational_config": agent_cfg.get("adapter_operational_config"),
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
