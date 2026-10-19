## Red-teaming local Claude Code

This example red-teams a locally installed Claude Code instance using HackAgent.

The repo includes two execution modes:

| File | Target | Judge / Attacker | Notes |
|---|---|---|---|
| `flipattack-claude.yaml` | Local Claude Code via `claude -p` | Anthropic API via LiteLLM | Requires `ANTHROPIC_API_KEY` |
| `flipattack-ollama.yaml` | Local Claude Code launched through Ollama | Local Ollama model | Fully local setup |

Both use the `CLAUDE_CODE` agent type, so HackAgent drives Claude Code natively through a local CLI. No HTTP endpoint or bridge is required.

---

### Scenario

The examples run a small FlipAttack campaign against Claude Code.

The default goal is to test whether the target can be induced to reveal its system prompt or hidden instructions.

| Component | Description |
|---|---|
| Target | Local Claude Code |
| Attack | FlipAttack |
| Risk | System-prompt disclosure and instruction-injection on an agentic coding assistant |

---

### Prerequisites

#### Common

Install Claude Code and confirm it runs:

    claude --version

#### For `flipattack-claude.yaml`

Export an Anthropic API key. This is used by the attacker/judge model, not by the local Claude Code target:

    export ANTHROPIC_API_KEY="sk-ant-..."

#### For `flipattack-ollama.yaml`

Install Ollama and confirm it runs:

    ollama --version

Make sure the model named in the campaign file is available locally.

---

### Usage

Run the Claude/API-backed version:

    hackagent campaign run flipattack-claude.yaml

Run the Ollama/local version:

    hackagent campaign run flipattack-ollama.yaml

It is a campaign file, so you can read the whole attack without reading any
Python, and change the target, the goals or the judge by editing it. Check it
first with `hackagent campaign validate flipattack-ollama.yaml`.

Or use the interactive TUI preset:

    hackagent claude

---

### How the target is wired

Both scripts create a `HackAgent` with:

    agent_type="claude-code"

The difference is the local binary used to launch the target.

#### `flipattack-claude.yaml`

Uses the Claude Code CLI directly:

    adapter_operational_config={
        "name": TARGET_MODEL,
        "binary": "claude",
    }

The configured model name is passed to Claude Code.

#### `flipattack-ollama.yaml`

Uses Ollama as the launcher:

    target:
      name: llama3.2:3b
      connection:
        provider: local
        type: CLAUDE_CODE
      options:
        binary: ollama

`name` is passed to Ollama; `options.binary` is the executable to launch.

---

### Notes

- The `endpoint` field is present for HackAgent compatibility, but it is ignored for this local Claude Code setup.
- The target is executed locally through the configured CLI binary.
- No HTTP server or bridge is required.
- If the configured binary is not on `PATH`, the setup will fail before the attack runs.
- The scripts are intentionally small examples and are meant to be edited for different models, goals, and attack configurations.

---

### Files

| File | Purpose |
|---|---|
| `flipattack-claude.yaml` | Red-teams local Claude Code using an Anthropic/LiteLLM judge |
| `flipattack-ollama.yaml` | Red-teams local Claude Code using a local Ollama-backed setup |
| `README.md` | Explains the scenarios and how to run them |