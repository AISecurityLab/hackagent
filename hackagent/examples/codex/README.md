## Red-teaming local Codex

This example red-teams a locally installed Codex instance using HackAgent.

The repo includes two execution modes:

| Campaign | Target | Judge / Attacker | Notes |
|---|---|---|---|
| `h4rm3l-codex.yaml` | Local Codex via `codex exec` | OpenAI via LiteLLM | Requires `OPENAI_API_KEY` |
| `h4rm3l-ollama.yaml` | Local Codex launched through Ollama | Local Ollama model | Fully local setup |

Both campaigns use the `CODEX` connection type, so HackAgent drives Codex natively through a local CLI. No HTTP endpoint or bridge is required.

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

#### For `h4rm3l-codex.yaml`

Export an OPENAI API key. This is used by the attacker/judge model, not by the local Codex target:

    export OPENAI_API_KEY="sk-..."

#### For `h4rm3l-ollama.yaml`

Install Ollama and confirm it runs:

    ollama --version

Make sure the Ollama model configured in the campaign is available locally.

---

### Usage

Run the Codex/API-backed version:

    hackagent campaign run h4rm3l-codex.yaml

Run the Ollama/local version:

    hackagent campaign run h4rm3l-ollama.yaml

Or open the terminal UI and start from this example there:

    hackagent

---

### How the target is wired

Both campaigns point their `target` at a local `CODEX` connection; they
differ only in the executable HackAgent launches.

#### `h4rm3l-codex.yaml`

Runs the Codex CLI directly:

    target:
      name: gpt-5.5
      connection:
        provider: local
        type: CODEX
      options:
        binary: codex

`name` is passed to Codex with `-m`.

#### `h4rm3l-ollama.yaml`

Uses Ollama as the launcher:

    target:
      name: llama3.2:3b
      connection:
        provider: local
        type: CODEX
      options:
        binary: ollama

`name` is passed to `ollama launch codex --model`; `options.binary` is the executable to launch.

---

### Notes

- The target is executed locally through the configured CLI binary.
- No HTTP server or bridge is required.
- If the configured binary is not on `PATH`, the setup will fail before the attack runs.
- The campaigns are intentionally small examples and are meant to be edited for different models, goals, and attack configurations.

---

### Files

| File | Purpose |
|---|---|
| `h4rm3l-codex.yaml` | Red-teams local Codex using an OpenAI/LiteLLM judge |
| `h4rm3l-ollama.yaml` | Red-teams local Codex using a local Ollama-backed setup |
| `README.md` | Explains the scenarios and how to run them |