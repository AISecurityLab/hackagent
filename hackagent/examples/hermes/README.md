## Red-teaming local Hermes Agent

This example red-teams a locally installed [Hermes Agent](https://github.com/NousResearch/hermes-agent) instance using HackAgent.

Hermes has no OpenAI-compatible HTTP endpoint, but it ships a one-shot headless mode (`hermes -z "prompt"`) that prints only the final response. HackAgent drives the target through that CLI with the `hermes` agent type, so no HTTP endpoint or bridge is required.

---

### Scenario

The example runs a small FlipAttack campaign against Hermes Agent.

The default goal is to test whether the target can be induced to reveal its system prompt or hidden instructions.

| Component | Description |
|---|---|
| Target | Local Hermes Agent via `hermes -z` |
| Attack | FlipAttack |
| Judge | Anthropic API via LiteLLM (requires `ANTHROPIC_API_KEY`) |
| Risk | System-prompt disclosure and instruction-injection on a persistent, self-improving agent |

---

### Prerequisites

Install Hermes Agent and confirm it runs:

    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    hermes --version

Export an Anthropic API key. This is used by the attacker/judge model, not by the local Hermes target:

    export ANTHROPIC_API_KEY=sk-ant-...

Then run:

    python hack_hermes.py

---

### How the target is wired

    agent = HackAgent(
        name="hermes",
        endpoint="http://localhost",  # ignored
        agent_type="hermes",
        adapter_operational_config={
            "name": "hermes-4-70b",  # passed to `hermes -m`
            "binary": "hermes",
        },
    )

| Config key | Maps to | Default |
|---|---|---|
| `name` (required) | `-m <model>` | — |
| `binary` | argv[0], checked with `shutil.which` at construction | `hermes` |
| `provider` | `--provider <provider>` | unset |
| `cwd` | working directory Hermes operates in | unset |
| `timeout` | `subprocess.run(..., timeout=)` seconds | `600` |
| `ignore_user_config` | `--ignore-user-config` | `True` |
| `safe_mode` | `--safe-mode` | `False` |
| `source` | `--source <source>` | `hackagent` |
| `extra_args` | appended raw flags | `[]` |

---

### Isolation and reproducibility

Unlike Claude Code, Hermes is stateful: it keeps long-term memory in `~/.hermes/MEMORY.md`, runs a background skill curator that writes its own skills, and can resume sessions. Left on defaults, red-teaming a real install would let the target "learn" from being probed (biasing later attack turns) and would pollute the operator's own Hermes state.

The adapter therefore defaults to isolation:

- `--ignore-user-config` is always passed unless you explicitly set `"ignore_user_config": False`, so the target uses defaults plus `.env` credentials only and never reads `~/.hermes/config.yaml`.
- `-r`/`--resume` and `-c`/`--continue` are never passed, so every attack turn is a fresh session.
- `"safe_mode": True` opts into `--safe-mode` for maximum isolation (all customizations disabled).
- `--source hackagent` is passed so Hermes-side logs are attributable to HackAgent runs.

For stronger separation still, point `cwd` at a scratch directory and/or run the target under a dedicated `hermes profile` so the operator's real profile, memory and skills are never touched.

---

### Notes

- `hermes -z` returns bare text with no structured metadata (no session id, cost or exit reason), so the adapter relies on exit codes: `0` success, `1` delivery/backend failure, `2` usage error. A non-zero exit with usable stdout is captured as the target's response (a refusal is a legitimate response to judge); exit `2` always fails loudly.
- The prompt is fed via **stdin**, never argv, so adversarial payloads starting with `-` are not parsed as CLI flags.
- The `endpoint` field is present for HackAgent compatibility but is ignored for this local setup.
- If the configured binary is not on `PATH`, the setup fails before the attack runs.
- `hermes serve` (a headless backend over JSON-RPC/WebSocket) is out of scope here; this example covers the local CLI-driven path only.

---

### Files

| File | Purpose |
|---|---|
| `hack_hermes.py` | Red-teams local Hermes Agent using an Anthropic/LiteLLM judge |
| `README.md` | Explains the scenario and how to run it |
