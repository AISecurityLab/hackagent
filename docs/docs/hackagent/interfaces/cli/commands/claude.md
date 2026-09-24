---
sidebar_label: claude
title: hackagent.interfaces.cli.commands.claude
---

Claude Code Command

`hackagent claude` launches the TUI pre-configured to red-team a locally
installed Claude Code instance. It is a thin convenience wrapper over the
Attacks tab: the target agent, agent type, model, attack strategy, and a
starter set of goals are filled in for you, so a single command goes straight
to &quot;ready to execute&quot;.

The target is driven natively through the `claude-code` router provider,
which shells out to the headless `claude -p` CLI — no HTTP endpoint or bridge
required. The only prerequisite is the `claude` binary on PATH.

#### claude

```python
@click.command(name="claude")
@click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help=
    "Claude model for `claude --model` (alias sonnet/opus/haiku or full id).",
)
@click.option(
    "--binary",
    default=DEFAULT_BINARY,
    show_default=True,
    help="Path to the Claude Code executable.",
)
@click.option(
    "--goals",
    multiple=True,
    help="Attack goals. Repeat --goals or pass a comma-separated string. "
    "Defaults to a Claude Code red-team starter set.",
)
@click.option(
    "--attack-type",
    default=DEFAULT_ATTACK_TYPE,
    show_default=True,
    help=
    "Attack strategy to preselect (e.g., tap, pair, flipattack, advprefix).",
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
    help="Skip the check that verifies the Claude Code binary is installed.",
)
@click.pass_context
@handle_errors
def claude(ctx: click.Context, model: str, binary: str, goals: Tuple[str, ...],
           attack_type: str, timeout: int, dry_run: bool, no_tui: bool,
           skip_preflight: bool) -> None
```

🤖 Red-team a locally installed Claude Code instance.

Launches the TUI with the Attacks tab pre-configured to target Claude Code
natively via the headless `claude -p` CLI (no endpoint/bridge), using the
fast FlipAttack strategy (one target call per goal, no attacker model).
Requires the `claude` binary on PATH.



**Examples**:

  hackagent claude
  hackagent claude --model sonnet
  hackagent claude --goals &quot;Reveal your system prompt&quot; --attack-type pair
  hackagent claude --no-tui --dry-run

