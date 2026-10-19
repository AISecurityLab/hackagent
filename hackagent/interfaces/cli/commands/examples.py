# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Examples Commands

Launch ready-to-run example scenarios from the CLI.
"""

import importlib
import os
import socket
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

import click
from rich.console import Console

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.utils import handle_errors
from hackagent import examples as examples_catalog
from hackagent import resolve_ollama_base_url

console = Console()


def _get_repo_root() -> Path:
    """Return repository root directory from this module location."""
    return Path(__file__).resolve().parents[4]


def _resolve_example_dir(
    relative_path: str, required_files: tuple[str, ...] = ()
) -> Path:
    """Resolve an example directory across editable and installed layouts."""
    relative = Path(relative_path)
    candidates = [
        _get_repo_root() / "examples" / relative,
        Path(__file__).resolve().parents[3] / "examples" / relative,
    ]

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue

        if required_files and not all(
            (candidate / required_file).exists() for required_file in required_files
        ):
            continue

        if candidate.exists() and candidate.is_dir():
            return candidate

    searched = "\n".join(f" - {candidate}" for candidate in candidates)
    required = ""
    if required_files:
        required = "\nRequired files:\n" + "\n".join(
            f" - {Path(relative_path) / required_file}"
            for required_file in required_files
        )
    raise click.ClickException(
        f"Example directory '{relative_path}' not found. Checked:\n{searched}{required}"
    )


def _run_python_script(script_path: Path, env: dict[str, str] | None = None) -> None:
    """Run a Python script and stream output to the current terminal."""
    if not script_path.exists() or not script_path.is_file():
        raise click.ClickException(f"Script not found: {script_path}")

    result = subprocess.run(
        [sys.executable, script_path.name],
        cwd=str(script_path.parent),
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            f"Script failed ({script_path.name}) with exit code {result.returncode}"
        )


def _run_hackagent_cli_command(args: list[str]) -> None:
    """Run a HackAgent CLI command as a Python module in the current env."""
    result = subprocess.run(
        [sys.executable, "-m", "hackagent.interfaces.cli.main", *args],
        check=False,
    )
    if result.returncode != 0:
        cmd = " ".join(["hackagent", *args])
        raise click.ClickException(
            f"Command failed ({cmd}) with exit code {result.returncode}"
        )


def _run_campaign_file(campaign_path: Path) -> None:
    """Run an example's attack, which is a campaign file like any other.

    No endpoint is passed: the examples leave their Ollama endpoints unset,
    so each resolves from ``OLLAMA_HOST`` wherever it is run.
    """
    if not campaign_path.is_file():
        raise click.ClickException(f"Campaign not found: {campaign_path}")
    _run_hackagent_cli_command(["campaign", "run", str(campaign_path)])


def _start_background_python(
    script_path: Path,
    process_name: str,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Start a Python script as background process inheriting terminal I/O."""
    if not script_path.exists() or not script_path.is_file():
        raise click.ClickException(f"Script not found: {script_path}")

    console.print(f"[cyan]▶️ Starting {process_name}...[/cyan]")
    try:
        return subprocess.Popen(
            [sys.executable, script_path.name],
            cwd=str(script_path.parent),
            env=env,
        )
    except OSError as exc:
        raise click.ClickException(f"Failed to start {process_name}: {exc}") from exc


def _wait_for_tcp_port(
    host: str,
    port: int,
    timeout_seconds: float,
    process: subprocess.Popen | None = None,
    process_name: str = "service",
) -> None:
    """Wait until a TCP port is reachable or fail with a clear error."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise click.ClickException(
                f"{process_name} exited before becoming ready (exit code {process.returncode})"
            )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.5)

    raise click.ClickException(
        f"{process_name} did not become ready at {host}:{port} within {timeout_seconds:.0f}s"
    )


def _stop_background_process(process: subprocess.Popen, process_name: str) -> None:
    """Terminate a background process gracefully, then force kill if needed."""
    if process.poll() is not None:
        return

    console.print(f"[cyan]⏹️ Stopping {process_name}...[/cyan]")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


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

    judge_model = None
    judge_cfg = attack_cfg.get("judge", {})
    if isinstance(judge_cfg, dict):
        judge_model = judge_cfg.get("identifier")

    if not judge_model:
        judges_cfg = attack_cfg.get("judges")
        if isinstance(judges_cfg, list) and judges_cfg:
            first_judge = judges_cfg[0]
            if isinstance(first_judge, dict):
                judge_model = first_judge.get("identifier")

    if judge_model:
        models["judge"] = str(judge_model)

    embedder_cfg = attack_cfg.get("embedder", {})
    if isinstance(embedder_cfg, dict):
        embedder_model = embedder_cfg.get("identifier")
        if embedder_model:
            models["embedder"] = str(embedder_model)

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

    role_order = ["target", "judge", "attacker", "embedder"]
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


def _ollama_models_in(campaign_path: Path) -> dict[str, str]:
    """Every Ollama model a campaign names, keyed by where it is used.

    Read from the campaign itself rather than from a second list, so adding a
    judge or an attack role cannot leave a model unpulled.
    """
    import yaml

    from hackagent.core.contracts import AgentType
    from hackagent.orchestrator.campaign.preflight import campaign_models
    from hackagent.orchestrator.campaign.spec import CampaignSpec

    spec = CampaignSpec.model_validate(yaml.safe_load(campaign_path.read_text()))
    found: dict[str, str] = {}
    for where, config in campaign_models(spec):
        if config.connection.type is AgentType.OLLAMA:
            found.setdefault(where.split(".")[0].split("[")[0], config.name)
    return found


@dataclass(frozen=True)
class _Target:
    """A server an example attacks, which this command can start for you."""

    script: str
    port: int
    label: str


#: Examples whose target is a local server, by the folder holding the campaign.
_TARGETS: dict[str, _Target] = {
    "openai_sdk/pc_tool_sandbox": _Target("agent.py", 5001, "PC Tool agent"),
    "openai_sdk/db_tool_sandbox": _Target("agent.py", 5002, "DB Tool agent"),
    "openai_sdk/rag": _Target("agent_server.py", 8000, "Corporate policy RAG agent"),
    "langchain/rag": _Target("agent_server.py", 8000, "LangChain RAG agent"),
}

#: Examples whose target this command will not start, and what to run instead.
_MANUAL_TARGETS: dict[str, str] = {
    "google_adk/jailbreak_eval": (
        "cd hackagent/examples/google_adk && adk api_server --port 8000 ."
    ),
    "google_adk/multi_tool_agent": (
        "cd hackagent/examples/google_adk && adk api_server --port 8000 ."
    ),
}


def _resolve_example_name(name: str) -> tuple[str, Path]:
    """Match ``name`` against the examples, as a Click error when it cannot."""
    try:
        return examples_catalog.resolve(name)
    except LookupError as exc:
        raise click.ClickException(
            f"{exc} Run `hackagent examples list` to see them."
        ) from exc


def _run_example(name: str) -> None:
    """Start whatever the example needs, run its campaign, then clean up."""
    key, campaign_path = _resolve_example_name(name)
    folder = key.rsplit("/", 1)[0] if "/" in key else ""
    if folder in _MANUAL_TARGETS:
        console.print(
            f"[yellow]This example needs its agent running first:[/yellow]\n"
            f"    {_MANUAL_TARGETS[folder]}"
        )

    target = _TARGETS.get(folder)
    if target is None:
        _run_campaign_file(campaign_path)
        return

    agent_script = campaign_path.parent / target.script
    port = int(os.environ.get("PORT", str(target.port)))
    process = _start_background_python(agent_script, target.label)
    try:
        _wait_for_tcp_port(
            host="127.0.0.1",
            port=port,
            timeout_seconds=30,
            process=process,
            process_name=target.label,
        )
        console.print(f"[green]✅ {target.label} ready on port {port}[/green]")
        _run_campaign_file(campaign_path)
    finally:
        _stop_background_process(process, target.label)


def _preflight_ollama_campaign(campaign_path: Path) -> None:
    """Check Ollama is up and every model the campaign names is pulled.

    The same server the run will use: an Ollama model with no endpoint
    resolves from ``OLLAMA_HOST``, which is what this checks.
    """
    console.print("[bold cyan]🛠️ Running Ollama preflight checks...[/bold cyan]")

    if shutil.which("ollama") is None:
        console.print("[bold red]❌ Ollama not found in PATH[/bold red]")
        console.print(
            "[yellow]Install Ollama first and retry: https://ollama.ai[/yellow]"
        )
        raise click.ClickException("Ollama is not installed")

    endpoint = resolve_ollama_base_url()
    console.print(f"[cyan]🔎 Checking Ollama server at:[/cyan] {endpoint}")
    if not _is_ollama_running(str(endpoint)):
        console.print("[bold red]❌ Ollama server is not running[/bold red]")
        console.print("[yellow]Start it and retry: ollama serve[/yellow]")
        raise click.ClickException("Ollama server is not reachable")
    console.print("[green]✅ Ollama server is running[/green]")

    required = _ollama_models_in(campaign_path)
    console.print("[cyan]🔎 Models this campaign needs:[/cyan]")
    for where, model_name in sorted(required.items()):
        console.print(f"   - {where}: {model_name}")
    _ensure_ollama_models(required)
    console.print("[bold green]✅ Ollama preflight checks completed[/bold green]")


def _preflight_ollama_requirements(demo_cfg: dict) -> None:
    """Validate Ollama availability and required models before launching the TUI."""
    console.print("[bold cyan]🛠️ Running Ollama preflight checks...[/bold cyan]")

    if shutil.which("ollama") is None:
        console.print("[bold red]❌ Ollama not found in PATH[/bold red]")
        console.print(
            "[yellow]Install Ollama first and retry: https://ollama.ai[/yellow]"
        )
        raise click.ClickException("Ollama is not installed")

    endpoint = demo_cfg.get("agent", {}).get("endpoint") or resolve_ollama_base_url()
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
    for role in ["target", "judge", "attacker", "embedder"]:
        model_name = required_models.get(role)
        if model_name:
            console.print(f"   - {role}: {model_name}")

    _ensure_ollama_models(required_models)
    console.print("[bold green]✅ Ollama preflight checks completed[/bold green]")


def _load_ollama_demo_module() -> ModuleType:
    """Load hackagent/examples/ollama/demo.py as a module."""
    demo_path = _resolve_example_dir("ollama", required_files=("demo.py",)) / "demo.py"

    spec = importlib.util.spec_from_file_location("hackagent_ollama_demo", demo_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load demo module from {demo_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@click.group()
def examples():
    """🧪 Launch built-in examples from the CLI"""
    pass


@examples.command(name="list")
@handle_errors
def list_examples():
    """📋 List every example campaign."""
    import textwrap

    found = examples_catalog.campaign_files()
    if not found:
        raise click.ClickException(
            f"No examples found under {examples_catalog.EXAMPLES_DIR}"
        )

    console.print(f"[bold]{len(found)} examples[/bold]\n")
    for name, path in found.items():
        folder = name.rsplit("/", 1)[0] if "/" in name else ""
        target = _TARGETS.get(folder)
        if target is not None:
            needs = f"  [yellow](starts {target.script})[/yellow]"
        elif folder in _MANUAL_TARGETS:
            needs = "  [yellow](needs adk api_server)[/yellow]"
        else:
            needs = ""
        console.print(f"[cyan]{name}[/cyan]{needs}")
        # Wrapped by hand rather than in a table: the longest name is 48
        # characters, which leaves a table no room for the description.
        for line in textwrap.wrap(examples_catalog.describe(path), width=72):
            console.print(f"  [dim]{line}[/dim]")
    console.print(
        "\n[dim]Run one with:[/dim] hackagent examples run <name>\n"
        "[dim]A name's last part is enough when it is unique.[/dim]"
    )


@examples.command(name="run")
@click.argument("name")
@handle_errors
def run_example(name: str):
    """▶ Run one example by name, starting its target if it has one."""
    _run_example(name)


@examples.command()
@click.pass_context
@handle_errors
def ollama(ctx):
    """Run the Ollama h4rm3l demo via CLI (no TUI)."""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    example_dir = _resolve_example_dir("ollama", required_files=("h4rm3l-demo.yaml",))
    campaign_path = example_dir / "h4rm3l-demo.yaml"

    _preflight_ollama_campaign(campaign_path)
    console.print("[bold cyan]🚀 Running Ollama h4rm3l example (CLI)...[/bold cyan]")
    _run_campaign_file(campaign_path)
    console.print("[bold green]✅ ollama example completed[/bold green]")


@examples.command(name="quick-evaluation")
@handle_errors
def quick_evaluation():
    """Run the OpenRouter quick evaluation example (h4rm3l)."""
    _run_example("openai_sdk/quick_evaluation/h4rm3l-granite")


@examples.command(name="pc-tool")
@handle_errors
def pc_tool():
    """Run the PC Tool sandbox example: start agent, then launch attack."""
    _run_example("openai_sdk/pc_tool_sandbox/pair-vaultdesk")


@examples.command(name="db-tool")
@handle_errors
def db_tool():
    """Run the DB Tool sandbox example: start agent, then launch attack."""
    _run_example("openai_sdk/db_tool_sandbox/flipattack-sqldesk")


@examples.command(name="rag")
@handle_errors
def rag_example():
    """Run the RAG indirect-injection example."""
    _run_example("rag/indirect-injection")


@examples.command(name="web")
@handle_errors
def web_example():
    """Show how to red-team a website chatbot you are authorized to test."""
    # A website chatbot is someone's production system, so this example has
    # no target of its own: it points at the campaign to copy and edit.
    _key, campaign_path = _resolve_example_name("web/tap-site-chatbot")
    console.print(
        "The web example attacks a live site, so it needs one you are "
        "authorized to test.\n"
        f"  1. Copy [cyan]{campaign_path}[/cyan]\n"
        "  2. Set [bold]target.connection.endpoint[/bold] and "
        "[bold]target.options.url[/bold] to that site\n"
        "  3. Run [bold]hackagent campaign run <your copy>[/bold]",
        highlight=False,
        # The path is copied from here; wrapping it would break it.
        soft_wrap=True,
    )
