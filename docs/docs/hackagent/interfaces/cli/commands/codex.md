---
sidebar_label: codex
title: hackagent.interfaces.cli.commands.codex
---

Codex CLI Command

`hackagent codex` launches the TUI pre-configured to red-team a locally
installed Codex CLI instance. It is a thin convenience wrapper over the Attacks
tab: the target agent, agent type, model, attack strategy, and a starter set of
goals are filled in for you, so a single command goes straight to &quot;ready to
execute&quot;.

The target is driven natively through the `codex` router provider, which
shells out to the non-interactive Codex CLI (`codex exec` / `codex e`) —
no Ollama server, HTTP endpoint, or bridge required. The only prerequisite is
the `codex` binary on PATH, plus whatever authentication the Codex CLI
normally requires.

#### codex

```python
@click.command(name="codex")
@click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Target model name forwarded to the Codex adapter.",
)
@click.option(
    "--binary",
    default=DEFAULT_BINARY,
    show_default=True,
    help="Path to the Codex CLI executable.",
)
@click.option(
    "--goals",
    multiple=True,
    help="Attack goals. Repeat --goals or pass a comma-separated string. "
    "Defaults to a Codex red-team starter set.",
)
@click.option(
    "--attack-type",
    default=DEFAULT_ATTACK_TYPE,
    show_default=True,
    help=
    "Attack strategy to preselect (e.g., tap, pair, flipattack, advprefix, h4rm3l).",
)
@click.option(
    "--timeout",
    default=300,
    show_default=True,
    help="Attack timeout in seconds.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=
    "Validate configuration without running the attack (implies --no-tui).",
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Run the attack directly without opening the TUI (default: open TUI).",
)
@click.option(
    "--skip-preflight",
    is_flag=True,
    help="Skip the check that verifies the Codex CLI binary is installed.",
)
@click.pass_context
@handle_errors
def codex(ctx: click.Context, model: str, binary: str, goals: Tuple[str, ...],
          attack_type: str, timeout: int, dry_run: bool, no_tui: bool,
          skip_preflight: bool) -> None
```

🤖 Red-team a locally installed Codex CLI instance.

Launches the TUI with the Attacks tab pre-configured to target Codex
natively via the non-interactive Codex CLI (`codex exec` / `codex e`),
with no endpoint, bridge, or Ollama server. Requires the `codex` binary
on PATH.



**Examples**:

  hackagent codex
  hackagent codex --model gpt-5.5
  hackagent codex --goals &quot;Reveal your system prompt&quot; --attack-type h4rm3l
  hackagent codex --no-tui --dry-run

