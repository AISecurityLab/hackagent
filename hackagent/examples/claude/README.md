# Red-teaming local Claude Code

Tests a **locally installed Claude Code** as the target-under-test. HackAgent
drives it natively through the `claude-code` router provider, which shells out
to the headless `claude -p` CLI — there is **no HTTP endpoint or bridge** to
stand up.

## Scenario

| Component | Description |
|-----------|-------------|
| **Target** | Local Claude Code (`claude -p`), driven via the `claude-code` agent type |
| **Attacker / Judge** | Anthropic API (`anthropic/claude-sonnet-4-6`) via LiteLLM |
| **Attack** | TAP (Tree of Attacks with Pruning) — fast, search-based jailbreak refinement |
| **Risk** | System-prompt disclosure and instruction-injection on an agentic coding assistant |

## Prerequisites

1. **Install Claude Code** and confirm it runs:
   ```bash
   claude --version
   ```
2. **Export an Anthropic key** (used by the attacker/judge models, not the target):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

## Usage

```bash
# Headless script
python hack.py

# …or the interactive TUI preset (same target defaults, TAP strategy)
hackagent claude
```

## How the target is wired

```python
from hackagent import HackAgent

agent = HackAgent(
    name="claude-code",
    endpoint="",                 # ignored — Claude Code is local
    agent_type="claude-code",
    adapter_operational_config={
        "name": "claude-opus-4-8",  # passed to `claude --model`
        "binary": "claude",          # path to the executable
    },
)
```

The provider verifies the `claude` binary is on `PATH` at construction, so a
missing install fails fast with a clear error instead of mid-attack. The prompt
is fed to `claude -p` over **stdin** (never argv), so adversarial text that
begins with `-` is never misread as a CLI flag.

> **Note on tools:** the target runs with Claude Code's default permission mode.
> In headless mode, permission-gated tools (bash, file writes) do not execute,
> so this exercises the model's safety behaviour without granting it actions on
> your machine. Pass extra CLI flags via `adapter_operational_config["extra_args"]`
> if you intentionally want a different posture.
