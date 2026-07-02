## Red-teaming local Codex

This example red-teams a locally installed Codex instance using HackAgent.

The repo includes two execution modes:

| Script | Target | Judge / Attacker | Notes |
|---|---|---|---|
| `hack_codex.py` | Local Codex via `codex exec` | OpenAI via LiteLLM | Requires `OPENAI_API_KEY` |
| `hack_ollama.py` | Local Codex launched through Ollama | Local Ollama model | Fully local setup |

Both scripts use the `codex` agent type, so HackAgent drives Codex natively through a local CLI. No HTTP endpoint or bridge is required.

---

### Scenario

The examples run a small h4rm3l campaign against Codex.

The default goal is to test whether the target can be induced to reveal its system prompt or hidden instructions.

| Component | Description |
|---|---|
| Target | Local Codex |
| Attack | h4rm3l |
| Risk | System-prompt disclosure and instruction-injection on an agentic coding assistant |

---

### Prerequisites

#### Common

Install Codex CLI and confirm it runs:

    codex --version

#### For `hack_codex.py`

Export an OPENAI API key. This is used by the attacker/judge model, not by the local Codex target:

    export OPENAI_API_KEY="sk-..."

#### For `hack_ollama.py`

Install Ollama and confirm it runs:

    ollama --version

Make sure the Ollama model configured in the script is available locally.

---

### Usage

Run the Codex/API-backed version:

    python hack_codex.py

Run the Ollama/local version:

    python hack_ollama.py

Or use the interactive TUI preset:

    hackagent codex

---

### How the target is wired

Both scripts create a `HackAgent` with:

    agent_type="codex"

The difference is the local binary used to launch the target.

#### `hack_codex.py`

Uses the Codex CLI directly:

    adapter_operational_config={
        "name": TARGET_MODEL,
        "binary": "codex",
    }

The configured model name is passed to Codex.

#### `hack_ollama.py`

Uses Ollama as the launcher:

    adapter_operational_config={
        "name": TARGET_MODEL,
        "binary": "ollama",
    }

The configured model name is passed to Ollama.

---

### Notes

- The `endpoint` field is present for HackAgent compatibility, but it is ignored for this local Codex setup.
- The target is executed locally through the configured CLI binary.
- No HTTP server or bridge is required.
- If the configured binary is not on `PATH`, the setup will fail before the attack runs.
- The scripts are intentionally small examples and are meant to be edited for different models, goals, and attack configurations.

---

### Files

| File | Purpose |
|---|---|
| `hack_codex.py` | Red-teams local Codex using an OpenAI/LiteLLM judge |
| `hack_ollama.py` | Red-teams local Codex using a local Ollama-backed setup |
| `README.md` | Explains the scenarios and how to run them |