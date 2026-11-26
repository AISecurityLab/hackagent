# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Examples Commands

Launch ready-to-run example scenarios from the CLI.
"""

import re
import os
import socket
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

import click
from rich.markup import escape

from hackagent.interfaces.cli.utils import (
    Failed,
    console,
    display_hint,
    display_info,
    display_success,
    display_warning,
    handle_errors,
)
from hackagent import examples as examples_catalog
from hackagent import resolve_ollama_base_url


def _root_options() -> list[str]:
    """The root options this command was given (``--backend``, ``-v``, …),
    to pass on to a child ``hackagent`` so it reads and writes the same way."""
    context = click.get_current_context(silent=True)
    if context is None:
        return []
    params = context.find_root().params
    forwarded: list[str] = []
    for name in ("config_file", "backend", "base_url", "ca_bundle"):
        if params.get(name):
            forwarded += [f"--{name.replace('_', '-')}", str(params[name])]
    if params.get("verbose"):
        forwarded.append("-" + "v" * int(params["verbose"]))
    return forwarded


def _run_hackagent_cli_command(args: list[str]) -> None:
    """Run a HackAgent CLI command as a Python module in the current env,
    with the root options this one was given."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hackagent.interfaces.cli.main",
            *_root_options(),
            *args,
        ],
        check=False,
    )
    if result.returncode != 0:
        cmd = " ".join(["hackagent", *args])
        raise Failed(f"Command failed ({cmd}) with exit code {result.returncode}")


def _run_campaign_file(campaign_path: Path) -> None:
    """Run an example's attack, which is a campaign file like any other.

    No endpoint is passed: the examples leave their Ollama endpoints unset,
    so each resolves from ``OLLAMA_HOST`` wherever it is run.
    """
    if not campaign_path.is_file():
        raise Failed(f"Campaign not found: {campaign_path}")
    _run_hackagent_cli_command(["campaign", "run", str(campaign_path)])


def _start_background_python(
    script_path: Path,
    process_name: str,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Start a Python script as background process inheriting terminal I/O."""
    if not script_path.exists() or not script_path.is_file():
        raise Failed(f"Script not found: {script_path}")

    display_info(f"Starting {process_name}…")
    try:
        return subprocess.Popen(
            [sys.executable, script_path.name],
            cwd=str(script_path.parent),
            env=env,
        )
    except OSError as exc:
        raise Failed(f"Failed to start {process_name}: {exc}") from exc


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
            raise Failed(
                f"{process_name} exited before becoming ready (exit code {process.returncode})"
            )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.5)

    raise Failed(
        f"{process_name} did not become ready at {host}:{port} within {timeout_seconds:.0f}s"
    )


def _stop_background_process(process: subprocess.Popen, process_name: str) -> None:
    """Terminate a background process gracefully, then force kill if needed."""
    if process.poll() is not None:
        return

    display_info(f"Stopping {process_name}…")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


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
        raise Failed(f"Failed to read local Ollama models: {stderr}")

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
        display_warning("No Ollama models found in demo config to validate")
        return

    display_info("Checking the local Ollama models…")
    installed = _get_installed_ollama_models()

    role_order = ["target", "judge", "attacker", "embedder"]
    for role in role_order:
        model_name = models_by_role.get(role)
        if not model_name:
            continue

        if _is_model_present(model_name, installed):
            display_success(f"{role.title()} model available: {model_name}")
            continue

        display_warning(f"{role.title()} model missing: {model_name}")
        display_hint("Pulling it with", f"ollama run {model_name!s} ping")

        pull_result = subprocess.run(
            ["ollama", "run", model_name, "ping"],
            capture_output=True,
            text=True,
            check=False,
        )
        if pull_result.returncode != 0:
            stderr = pull_result.stderr.strip() or "unknown error"
            raise Failed(
                f"Failed to pull Ollama model '{model_name}' with 'ollama run': {stderr}"
            )

        display_success(f"Model ready: {model_name}")
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


# What an example needs running before it, kept with the examples.
_Target = examples_catalog.Target
_TARGETS = examples_catalog.TARGETS
_MANUAL_TARGETS = examples_catalog.MANUAL_TARGETS


def _resolve_example_name(name: str) -> tuple[str, Path]:
    """Match ``name`` against the examples, as a Click error when it cannot."""
    try:
        return examples_catalog.resolve(name)
    except LookupError as exc:
        raise Failed(f"{exc} Run `hackagent examples list` to see them.") from exc


def _run_example(name: str) -> None:
    """Start whatever the example needs, run its campaign, then clean up."""
    key, campaign_path = _resolve_example_name(name)
    folder = key.rsplit("/", 1)[0] if "/" in key else ""
    if folder == "web":
        # A website chatbot is someone's production system, so this example
        # has no target of its own: it says what to copy and edit instead.
        _explain_web_example()
        return
    if folder == "ollama":
        _preflight_ollama_campaign(campaign_path)
    if folder in _MANUAL_TARGETS:
        display_warning("This example needs its agent running first:")
        console.print(f"    {_MANUAL_TARGETS[folder]}", markup=False)

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
        display_success(f"{target.label} ready on port {port}")
        _run_campaign_file(campaign_path)
    finally:
        _stop_background_process(process, target.label)


def _explain_web_example() -> None:
    """How to red-team a website chatbot you are authorized to test."""
    console.print(
        "The web example attacks a live site, so it needs one you are "
        "authorized to test.\n"
        "  1. Copy it: [accent]hackagent examples copy web/tap-site-chatbot campaign.yaml[/accent]\n"
        "  2. Set [name]target.connection.endpoint[/name] and "
        "[name]target.options.url[/name] to that site\n"
        "  3. Run it: [accent]hackagent campaign run campaign.yaml[/accent]",
        highlight=False,
        # The path is copied from here; wrapping it would break it.
        soft_wrap=True,
    )


def _preflight_ollama_campaign(campaign_path: Path) -> None:
    """Check Ollama is up and every model the campaign names is pulled.

    The same server the run will use: an Ollama model with no endpoint
    resolves from ``OLLAMA_HOST``, which is what this checks.
    """
    display_info("Checking Ollama…")

    if shutil.which("ollama") is None:
        display_hint("Install it first", "https://ollama.ai")
        raise Failed("Ollama is not installed")

    endpoint = resolve_ollama_base_url()
    display_info(f"Checking the Ollama server at {endpoint}")
    if not _is_ollama_running(str(endpoint)):
        display_hint("Start it and retry", "ollama serve")
        raise Failed("Ollama server is not reachable")
    display_success("Ollama server is running")

    required = _ollama_models_in(campaign_path)
    display_info("Models this campaign needs:")
    for where, model_name in sorted(required.items()):
        console.print(f"   - {where}: {model_name}")
    _ensure_ollama_models(required)
    display_success("Ollama is ready")


@click.group()
def examples():
    """List, copy and run the example campaigns."""


@examples.command(name="list")
@handle_errors
def list_examples():
    """List every example campaign."""
    found = examples_catalog.campaign_files()
    if not found:
        raise Failed(f"No examples found under {examples_catalog.EXAMPLES_DIR}")

    from hackagent.interfaces.examples import example_rows

    console.print(f"[heading]{len(found)} examples[/heading]\n")
    # The tree the TUI's picker shows, line for line.
    for _, row in example_rows(found):
        console.print(row)
    console.print()
    display_hint("Run one", "hackagent examples run NAME")
    display_hint("Copy one here, to edit", "hackagent examples copy NAME campaign.yaml")
    display_info("  A name's last part is enough when it is unique.")


#: Where the docs site serves the campaign JSON Schema.
CAMPAIGN_SCHEMA_URL = "https://docs.hackagent.dev/schema/campaign.schema.json"

#: An editor schema hint pointing at a relative path, as the examples have.
_SCHEMA_HINT = re.compile(r"^(# yaml-language-server: \$schema=)(?!https?://)\S+", re.M)


@examples.command(name="copy")
@click.argument("name")
@click.argument("destination", required=False, type=click.Path(path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite a file that is already there.")
@handle_errors
def copy_example(name: str, destination: Optional[Path], force: bool):
    """Copy an example campaign here, to edit and run as your own.

    DESTINATION is a file or a folder, the current folder by default.
    """
    key, source = _resolve_example_name(name)
    target = destination or Path(".")
    if target.is_dir():
        target = target / source.name
    if target.exists() and not force:
        raise Failed(f"{target} already exists; use --force to replace it.")
    # Copied as it is, comments included: they explain the example. Only the
    # editor's schema hint changes, from a path inside this repository to the
    # schema the docs site publishes.
    text = source.read_text(encoding="utf-8")
    text = _SCHEMA_HINT.sub(rf"\g<1>{CAMPAIGN_SCHEMA_URL}", text, count=1)
    target.write_text(text, encoding="utf-8")

    display_success(f"Copied {escape(key)} → {escape(str(target))}")
    folder = key.rsplit("/", 1)[0] if "/" in key else ""
    if folder in _TARGETS or folder in _MANUAL_TARGETS:
        display_warning(
            "Its agent is not copied: start it the way "
            f"`hackagent examples run {escape(key)}` does, or point the target elsewhere."
        )
    display_hint("Check it", f"hackagent campaign validate {escape(str(target))}")
    display_hint("Run it", f"hackagent campaign run {escape(str(target))}")


@examples.command(name="run")
@click.argument("name")
@handle_errors
def run_example(name: str):
    """Run one example by name, starting its target if it has one."""
    _run_example(name)
